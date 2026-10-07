import json
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymysql.err import MySQLError

from app.services import scheduler

router = APIRouter()

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ORDER_TABLES = {"schedule_group", "schedule_job"}


class JobBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    docId: str = Field(pattern=r"^\d{1,10}$")
    apiName: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    source: str = Field(pattern=r"^(rds|promax)$")
    params: dict[str, str] = Field(default_factory=dict)
    fields: list[str] = Field(min_length=1, max_length=200)
    cron: str = Field(default="", max_length=64)
    targetTable: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    primaryKeys: list[str] = Field(default_factory=list, max_length=8)
    retry: int = Field(default=0, ge=0, le=5)
    timeout: int = Field(default=30, ge=1, le=300)
    groupId: int | None = None
    sortOrder: int = Field(default=0, ge=0, le=9999)
    enabled: bool = True


class GroupBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cron: str = Field(default="", max_length=64)
    followPrevious: bool = False
    stopOnFailure: bool = True
    enabled: bool = True


class ToggleBody(BaseModel):
    enabled: bool


class IdOrderBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class JobOrderBody(BaseModel):
    groupId: int
    ids: list[int] = Field(min_length=1, max_length=200)


class RunGroupBody(BaseModel):
    chain: bool = False


class RunStateBody(BaseModel):
    dateInterval: int = Field(ge=1, le=20000)
    nextStartDate: str = Field(default="", max_length=10)
    nextEndDate: str = Field(default="", max_length=10)
    lastSuccessStart: str = Field(default="", max_length=10)
    lastSuccessEnd: str = Field(default="", max_length=10)
    durationMs: int | None = Field(default=None, ge=0, le=7 * 24 * 3600 * 1000)
    lastRowCount: int | None = Field(default=None, ge=0, le=2_000_000_000)
    lastSuccessAt: str = Field(default="", max_length=19)


@router.get("/schedule/overview")
def get_overview() -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS c FROM schedule_job WHERE enabled=1")
                enabled = int(cursor.fetchone()["c"])
                cursor.execute("SELECT COUNT(*) AS c FROM schedule_group WHERE enabled=1")
                enabled_groups = int(cursor.fetchone()["c"])
                cursor.execute(
                    "SELECT status, COUNT(*) AS c FROM schedule_run "
                    "WHERE started_at >= CURDATE() GROUP BY status"
                )
                today = {row["status"]: int(row["c"]) for row in cursor.fetchall()}
                cursor.execute("SELECT COUNT(*) AS c FROM schedule_run WHERE status='running'")
                running = int(cursor.fetchone()["c"])
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    return {
        "leader": scheduler.is_leader(),
        "enabledJobs": enabled,
        "enabledGroups": enabled_groups,
        "todaySuccess": today.get("success", 0),
        "todayFailed": today.get("failed", 0),
        "running": running,
    }


@router.get("/schedule/groups")
def list_groups() -> list[dict]:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT g.*, (SELECT COUNT(*) FROM schedule_job j WHERE j.group_id = g.id) AS member_count "
                    "FROM schedule_group g ORDER BY g.sort_order, g.id"
                )
                rows = list(cursor.fetchall())
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    return [_group_out(row) for row in rows]


@router.post("/schedule/groups")
def create_group(body: GroupBody) -> dict:
    _validate_group(body)
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM schedule_group")
                sort_order = int(cursor.fetchone()["n"])
                cursor.execute(
                    "INSERT INTO schedule_group (name, cron, sort_order, follow_previous, stop_on_failure, enabled) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        body.name.strip(),
                        body.cron.strip(),
                        sort_order,
                        int(body.followPrevious),
                        int(body.stopOnFailure),
                        int(body.enabled),
                    ),
                )
                group_id = int(cursor.lastrowid)
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    scheduler.sync_group(group_id)
    return _fetch_group(group_id)


@router.put("/schedule/groups/order")
def reorder_groups(body: IdOrderBody) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM schedule_group")
                existing = {int(row["id"]) for row in cursor.fetchall()}
                if set(body.ids) != existing or len(body.ids) != len(set(body.ids)):
                    raise HTTPException(status_code=400, detail="请提交全部任务组的顺序")
                _write_order(cursor, "schedule_group", body.ids)
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    return {"ok": True}


@router.put("/schedule/groups/{group_id}")
def update_group(group_id: int, body: GroupBody) -> dict:
    _validate_group(body)
    _fetch_group(group_id)
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE schedule_group SET name=%s, cron=%s, follow_previous=%s, stop_on_failure=%s, enabled=%s "
                    "WHERE id=%s",
                    (
                        body.name.strip(),
                        body.cron.strip(),
                        int(body.followPrevious),
                        int(body.stopOnFailure),
                        int(body.enabled),
                        group_id,
                    ),
                )
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    scheduler.sync_group(group_id)
    return _fetch_group(group_id)


@router.post("/schedule/groups/{group_id}/toggle")
def toggle_group(group_id: int, body: ToggleBody) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE schedule_group SET enabled=%s WHERE id=%s",
                    (int(body.enabled), group_id),
                )
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="任务组不存在")
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    scheduler.sync_group(group_id)
    return {"ok": True}


@router.delete("/schedule/groups/{group_id}")
def delete_group(group_id: int) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS c FROM schedule_job WHERE group_id=%s", (group_id,))
                if int(cursor.fetchone()["c"]):
                    raise HTTPException(status_code=400, detail="组内还有任务，请先改为单独调度或移到其他任务组")
                cursor.execute("DELETE FROM schedule_group_run WHERE group_id=%s", (group_id,))
                cursor.execute("DELETE FROM schedule_group WHERE id=%s", (group_id,))
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="任务组不存在")
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    scheduler.remove_group(group_id)
    return {"ok": True}


@router.post("/schedule/groups/{group_id}/run")
def run_group_now(group_id: int, body: RunGroupBody | None = None) -> dict:
    _fetch_group(group_id)
    chain = bool(body and body.chain)
    scheduler.run_group(group_id, "manual", chain)
    return {"ok": True, "message": "已从本组开始按顺序运行" if chain else "已触发运行"}


@router.get("/schedule/groups/{group_id}/runs")
def list_group_runs(group_id: int) -> list[dict]:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM schedule_group_run WHERE group_id=%s ORDER BY id DESC LIMIT 50",
                    (group_id,),
                )
                rows = list(cursor.fetchall())
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    return [_group_run_out(row) for row in rows]


@router.get("/schedule/jobs")
def list_jobs() -> list[dict]:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM schedule_job ORDER BY id")
                rows = list(cursor.fetchall())
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    return [_job_out(row) for row in rows]


@router.put("/schedule/jobs/order")
def reorder_jobs(body: JobOrderBody) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM schedule_job WHERE group_id=%s", (body.groupId,))
                existing = {int(row["id"]) for row in cursor.fetchall()}
                if not existing:
                    raise HTTPException(status_code=400, detail="这个任务组里没有任务")
                if set(body.ids) != existing or len(body.ids) != len(set(body.ids)):
                    raise HTTPException(status_code=400, detail="请提交该任务组内全部任务的顺序")
                _write_order(cursor, "schedule_job", body.ids)
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    return {"ok": True}


@router.post("/schedule/jobs")
def create_job(body: JobBody) -> dict:
    _validate(body)
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                if body.groupId is not None:
                    _ensure_group(cursor, body.groupId)
                sort_order = _job_sort(cursor, body, None)
                cursor.execute(
                    "INSERT INTO schedule_job (name, doc_id, api_name, source, params_json, fields_json, "
                    "cron, target_table, primary_keys, retry, timeout, group_id, sort_order, enabled) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        body.name,
                        body.docId,
                        body.apiName,
                        body.source,
                        json.dumps(body.params, ensure_ascii=False),
                        json.dumps(body.fields, ensure_ascii=False),
                        body.cron.strip(),
                        body.targetTable,
                        ",".join(body.primaryKeys),
                        body.retry,
                        body.timeout,
                        body.groupId,
                        sort_order,
                        int(body.enabled),
                    ),
                )
                job_id = int(cursor.lastrowid)
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    scheduler.refresh_job_window(job_id)
    scheduler.sync_job(job_id)
    return _fetch_job(job_id)


@router.put("/schedule/jobs/{job_id}")
def update_job(job_id: int, body: JobBody) -> dict:
    _validate(body)
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                if body.groupId is not None:
                    _ensure_group(cursor, body.groupId)
                cursor.execute("SELECT id FROM schedule_job WHERE id=%s", (job_id,))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=404, detail="任务不存在")
                sort_order = _job_sort(cursor, body, job_id)
                cursor.execute(
                    "UPDATE schedule_job SET name=%s, doc_id=%s, api_name=%s, source=%s, params_json=%s, "
                    "fields_json=%s, cron=%s, target_table=%s, primary_keys=%s, retry=%s, timeout=%s, "
                    "group_id=%s, sort_order=%s, enabled=%s WHERE id=%s",
                    (
                        body.name,
                        body.docId,
                        body.apiName,
                        body.source,
                        json.dumps(body.params, ensure_ascii=False),
                        json.dumps(body.fields, ensure_ascii=False),
                        body.cron.strip(),
                        body.targetTable,
                        ",".join(body.primaryKeys),
                        body.retry,
                        body.timeout,
                        body.groupId,
                        sort_order,
                        int(body.enabled),
                        job_id,
                    ),
                )
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    scheduler.refresh_job_window(job_id)
    scheduler.sync_job(job_id)
    return _fetch_job(job_id)


@router.post("/schedule/jobs/{job_id}/toggle")
def toggle_job(job_id: int, body: ToggleBody) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE schedule_job SET enabled=%s WHERE id=%s", (int(body.enabled), job_id))
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="任务不存在")
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    scheduler.sync_job(job_id)
    return {"ok": True}


@router.delete("/schedule/jobs/{job_id}")
def delete_job(job_id: int) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM schedule_run_state WHERE job_id=%s", (job_id,))
                cursor.execute("DELETE FROM schedule_run WHERE job_id=%s", (job_id,))
                cursor.execute("DELETE FROM schedule_job WHERE id=%s", (job_id,))
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="任务不存在")
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    scheduler.remove_job(job_id)
    return {"ok": True}


@router.post("/schedule/jobs/{job_id}/run")
def run_job(job_id: int) -> dict:
    _fetch_job(job_id)
    scheduler.run_now(job_id, "manual", None)
    return {"ok": True, "message": "已触发运行"}


@router.get("/schedule/jobs/{job_id}/runs")
def list_runs(job_id: int) -> list[dict]:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT r.*, j.name AS job_name, j.api_name, j.source, j.fields_json "
                    "FROM schedule_run r LEFT JOIN schedule_job j ON j.id=r.job_id "
                    "WHERE r.job_id=%s ORDER BY r.id DESC LIMIT 50",
                    (job_id,),
                )
                rows = list(cursor.fetchall())
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    return [_run_out(row) for row in rows]


@router.get("/schedule/group-runs/{group_run_id}/calls")
def list_group_run_calls(group_run_id: int) -> list[dict]:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT r.*, j.name AS job_name, j.api_name, j.source, j.fields_json "
                    "FROM schedule_run r LEFT JOIN schedule_job j ON j.id=r.job_id "
                    "WHERE r.group_run_id=%s ORDER BY r.id",
                    (group_run_id,),
                )
                rows = list(cursor.fetchall())
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    return [_run_out(row) for row in rows]


@router.get("/schedule/run-states")
def list_run_states() -> list[dict]:
    try:
        return scheduler.list_run_states()
    except MySQLError as exc:
        raise _guard(exc) from exc


@router.put("/schedule/run-states/{job_id}")
def update_run_state(job_id: int, body: RunStateBody) -> dict:
    try:
        saved = scheduler.save_run_state(job_id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MySQLError as exc:
        raise _guard(exc) from exc
    if saved is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return saved


@router.post("/schedule/runs/{run_id}/retry")
def retry_run(run_id: int) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM schedule_run WHERE id=%s", (run_id,))
                run = cursor.fetchone()
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    snapshot = run.get("params_snapshot")
    params = json.loads(snapshot) if snapshot else None
    scheduler.run_now(int(run["job_id"]), "retry", params)
    return {"ok": True, "message": "已按原入参重跑"}


def _fetch_job(job_id: int) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM schedule_job WHERE id=%s", (job_id,))
                row = cursor.fetchone()
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _job_out(row)


def _fetch_group(group_id: int) -> dict:
    try:
        conn = scheduler.connect_app()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT g.*, (SELECT COUNT(*) FROM schedule_job j WHERE j.group_id = g.id) AS member_count "
                    "FROM schedule_group g WHERE g.id=%s",
                    (group_id,),
                )
                row = cursor.fetchone()
        finally:
            conn.close()
    except MySQLError as exc:
        raise _guard(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="任务组不存在")
    return _group_out(row)


def _ensure_group(cursor, group_id: int) -> None:
    cursor.execute("SELECT id FROM schedule_group WHERE id=%s", (group_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="任务组不存在")


def _job_sort(cursor, body: JobBody, job_id: int | None) -> int:
    if body.groupId is None:
        return 0
    if body.sortOrder > 0:
        return body.sortOrder
    if job_id is not None:
        cursor.execute("SELECT group_id, sort_order FROM schedule_job WHERE id=%s", (job_id,))
        current = cursor.fetchone()
        if current and current["group_id"] == body.groupId:
            return int(current["sort_order"])
    cursor.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM schedule_job WHERE group_id=%s",
        (body.groupId,),
    )
    return int(cursor.fetchone()["n"])


def _write_order(cursor, table: str, ids: list[int]) -> None:
    if table not in _ORDER_TABLES:
        raise HTTPException(status_code=500, detail="无法保存顺序")
    cases = " ".join(["WHEN %s THEN %s"] * len(ids))
    params: list[int] = []
    for index, item_id in enumerate(ids, start=1):
        params.extend([item_id, index])
    placeholders = ", ".join(["%s"] * len(ids))
    params.extend(ids)
    cursor.execute(
        f"UPDATE {table} SET sort_order = CASE id {cases} END WHERE id IN ({placeholders})",
        params,
    )


def _validate(body: JobBody) -> None:
    cron = body.cron.strip()
    if body.groupId is None:
        if not cron:
            raise HTTPException(status_code=400, detail="单独调度需要填写 cron 表达式")
        _check_cron(cron)
    elif cron:
        _check_cron(cron)
    names = list(body.params) + body.fields + body.primaryKeys
    if any(not _IDENT.fullmatch(name) for name in names):
        raise HTTPException(status_code=400, detail="字段或参数名不正确")
    if any(len(value) > 500 for value in body.params.values()):
        raise HTTPException(status_code=400, detail="入参内容过长")
    unknown = [key for key in body.primaryKeys if key not in body.fields]
    if unknown:
        raise HTTPException(status_code=400, detail=f"主键必须包含在勾选字段中：{', '.join(unknown)}")


def _validate_group(body: GroupBody) -> None:
    cron = body.cron.strip()
    if cron:
        _check_cron(cron)
    elif not body.followPrevious:
        raise HTTPException(status_code=400, detail="请填写执行频率，或勾选上一组成功后接着运行")


def _check_cron(cron: str) -> None:
    try:
        scheduler.apscheduler_cron(cron)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail="cron 表达式不正确") from exc


def _job_out(row: dict) -> dict:
    group_id = row.get("group_id")
    next_at = (
        scheduler.next_group_run_time(int(group_id))
        if group_id
        else scheduler.next_run_time(int(row["id"]))
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "docId": row["doc_id"],
        "apiName": row["api_name"],
        "source": row["source"],
        "params": json.loads(row["params_json"] or "{}"),
        "fields": json.loads(row["fields_json"] or "[]"),
        "cron": row["cron"] or "",
        "targetTable": row["target_table"],
        "primaryKeys": [part for part in (row["primary_keys"] or "").split(",") if part],
        "retry": row["retry"],
        "timeout": row["timeout"],
        "groupId": int(group_id) if group_id else None,
        "sortOrder": int(row.get("sort_order") or 0),
        "watermark": row["watermark"] or "",
        "enabled": bool(row["enabled"]),
        "lastStatus": row["last_status"] or "",
        "lastRunAt": _fmt(row["last_run_at"]),
        "nextRunAt": next_at,
    }


def _group_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "cron": row["cron"] or "",
        "sortOrder": int(row["sort_order"]),
        "followPrevious": bool(row["follow_previous"]),
        "stopOnFailure": bool(row["stop_on_failure"]),
        "enabled": bool(row["enabled"]),
        "lastStatus": row["last_status"] or "",
        "lastRunAt": _fmt(row["last_run_at"]),
        "nextRunAt": scheduler.next_group_run_time(int(row["id"])),
        "memberCount": int(row.get("member_count") or 0),
    }


def _snapshot_params(raw) -> dict:
    if isinstance(raw, dict):
        data = raw
    elif not raw:
        return {}
    else:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): "" if value is None else str(value) for key, value in data.items()}


def _field_names(raw) -> list[str]:
    if isinstance(raw, list):
        data = raw
    elif not raw:
        return []
    else:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def _run_out(row: dict) -> dict:
    group_run_id = row.get("group_run_id")
    return {
        "id": row["id"],
        "jobId": row["job_id"],
        "jobName": row.get("job_name") or "",
        "apiName": row.get("api_name") or "",
        "source": row.get("source") or "",
        "fields": _field_names(row.get("fields_json")),
        "params": _snapshot_params(row.get("params_snapshot")),
        "groupRunId": int(group_run_id) if group_run_id else None,
        "triggerType": row["trigger_type"],
        "startedAt": _fmt(row["started_at"]),
        "finishedAt": _fmt(row["finished_at"]),
        "status": row["status"],
        "rowCount": row["row_count"],
        "message": row["message"] or "",
    }


def _group_run_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "groupId": row["group_id"],
        "triggerType": row["trigger_type"],
        "startedAt": _fmt(row["started_at"]),
        "finishedAt": _fmt(row["finished_at"]),
        "status": row["status"],
        "message": row["message"] or "",
    }


def _fmt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def _guard(exc: MySQLError) -> HTTPException:
    if exc.args and exc.args[0] == 1146:
        return HTTPException(status_code=500, detail="调度表不存在，请先执行 python -m app.db.migrate")
    return HTTPException(status_code=500, detail="调度数据读取失败")
