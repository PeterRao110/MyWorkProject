import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pymysql
from apscheduler.executors.pool import ThreadPoolExecutor as APSchedulerExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pymysql.cursors import DictCursor
from pymysql.err import MySQLError

from app.services import tushare_writer
from app.services.database_config import read_values
from app.services.tushare_client import TushareError, load_schema, query_api

TZ = ZoneInfo("Asia/Shanghai")
LOCK_NAME = "mywork_scheduler"
PAGE_SIZE = 5000
MAX_PAGES = 200
KEEP_RUNS = 200
RETRY_INTERVAL_SECONDS = 60
DAY_GAP_SECONDS = 3
_PLACEHOLDER = re.compile(r"\$\{(today|yesterday|trade_date|last_trade_date)\}")

_scheduler: BackgroundScheduler | None = None
_lock_conn: pymysql.Connection | None = None
_leader = False
_manual_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="schedule-manual")
_guards: dict[int, threading.Lock] = {}
_group_guards: dict[int, threading.Lock] = {}
_guards_lock = threading.Lock()


def connect_app() -> pymysql.Connection:
    values = read_values()
    return pymysql.connect(
        host=values["host"],
        port=int(values["port"]),
        user=values["user"],
        password=values["password"],
        database=values["database"],
        charset="utf8mb4",
        autocommit=True,
        cursorclass=DictCursor,
    )


def is_leader() -> bool:
    return _leader


def start() -> None:
    global _scheduler, _lock_conn, _leader
    if _scheduler is not None:
        return
    try:
        _lock_conn = connect_app()
        with _lock_conn.cursor() as cursor:
            cursor.execute(f"SELECT GET_LOCK('{LOCK_NAME}', 0) AS got")
            acquired = bool(cursor.fetchone()["got"])
    except (MySQLError, OSError) as exc:
        print(f"调度器未启动：{exc}")
        _lock_conn = None
        _leader = False
        return
    if not acquired:
        _leader = False
        print("调度器未持有执行锁，本进程只提供接口，不触发定时执行")
        try:
            _lock_conn.close()
        except (MySQLError, OSError):
            pass
        _lock_conn = None
        return
    _leader = True
    _scheduler = BackgroundScheduler(
        timezone=TZ,
        executors={"default": APSchedulerExecutor(4)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
    )
    jobs = _enabled_jobs()
    groups = _enabled_groups()
    for job in jobs:
        _add_cron(job)
    for group in groups:
        _add_group_cron(group)
    _scheduler.start()
    print(f"调度器已启动，装载 {len(jobs)} 个单任务、{len(groups)} 个任务组")


def shutdown() -> None:
    global _scheduler, _lock_conn, _leader
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    if _lock_conn is not None:
        try:
            with _lock_conn.cursor() as cursor:
                cursor.execute(f"SELECT RELEASE_LOCK('{LOCK_NAME}')")
            _lock_conn.close()
        except (MySQLError, OSError):
            pass
        _lock_conn = None
    _leader = False


def sync_job(job_id: int) -> None:
    if not _leader or _scheduler is None:
        return
    try:
        _scheduler.remove_job(f"job-{job_id}")
    except LookupError:
        pass
    conn = connect_app()
    try:
        job = _load_job(conn, job_id)
        if job and job["enabled"] and not job.get("group_id"):
            _add_cron(job)
    finally:
        conn.close()


def remove_job(job_id: int) -> None:
    if not _leader or _scheduler is None:
        return
    try:
        _scheduler.remove_job(f"job-{job_id}")
    except LookupError:
        pass


def sync_group(group_id: int) -> None:
    if not _leader or _scheduler is None:
        return
    try:
        _scheduler.remove_job(f"group-{group_id}")
    except LookupError:
        pass
    conn = connect_app()
    try:
        group = _load_group(conn, group_id)
        if group and group["enabled"] and (group.get("cron") or "").strip():
            _add_group_cron(group)
    finally:
        conn.close()


def remove_group(group_id: int) -> None:
    if not _leader or _scheduler is None:
        return
    try:
        _scheduler.remove_job(f"group-{group_id}")
    except LookupError:
        pass


def next_run_time(job_id: int) -> str:
    return _scheduled_time(f"job-{job_id}")


def next_group_run_time(group_id: int) -> str:
    return _scheduled_time(f"group-{group_id}")


def _scheduled_time(scheduler_id: str) -> str:
    if not _leader or _scheduler is None:
        return ""
    job = _scheduler.get_job(scheduler_id)
    if job is None or job.next_run_time is None:
        return ""
    return job.next_run_time.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S")


def run_now(job_id: int, trigger_type: str = "manual", override_params: dict | None = None) -> None:
    _manual_pool.submit(execute_job, job_id, trigger_type, override_params)


def run_group(group_id: int, trigger_type: str = "manual", continue_chain: bool = False) -> None:
    _manual_pool.submit(execute_group, group_id, trigger_type, continue_chain)


def execute_job(
    job_id: int,
    trigger_type: str = "cron",
    override_params: dict | None = None,
    group_run_id: int | None = None,
) -> bool:
    guard = _guard_for(job_id)
    if not guard.acquire(blocking=False):
        if trigger_type != "cron":
            _record_skip(job_id, trigger_type, group_run_id)
        return False
    conn: pymysql.Connection | None = None
    try:
        conn = connect_app()
        job = _load_job(conn, job_id)
        if job is None:
            return False
        if _trade_window_job(job) and override_params is None:
            return _execute_daily_dates(conn, job, trigger_type, group_run_id)
        params = _resolve_params(job, override_params)
        snapshot = json.dumps(params, ensure_ascii=False)
        run_id = _insert_run(conn, job_id, trigger_type, snapshot, group_run_id)
        attempts = 1 + int(job.get("retry") or 0)
        error = ""
        for attempt in range(attempts):
            try:
                items = _fetch_all(job, params, _fields(job))
                count = tushare_writer.write_result(
                    conn,
                    job["target_table"],
                    _pks(job),
                    _fields(job),
                    items,
                    job["source"],
                    _field_types(job),
                )
                _finish_run(conn, run_id, "success", count, f"写入 {count} 行")
                _finish_job(conn, job_id, "success", _watermark(job, items))
                _cleanup_runs(conn, job_id)
                if not _trade_window_job(job):
                    _advance_window(conn, job_id, params, run_id, count)
                return True
            except Exception as exc:
                error = str(exc)[:500]
                if attempt + 1 < attempts:
                    time.sleep(RETRY_INTERVAL_SECONDS)
        _finish_run(conn, run_id, "failed", 0, error or "执行失败")
        _finish_job(conn, job_id, "failed", None)
        _cleanup_runs(conn, job_id)
        return False
    except Exception as exc:
        print(f"任务 {job_id} 执行异常：{exc}")
        return False
    finally:
        if conn is not None:
            conn.close()
        guard.release()


def _execute_daily_dates(
    conn: pymysql.Connection,
    job: dict,
    trigger_type: str,
    group_run_id: int | None,
) -> bool:
    job_id = int(job["id"])
    window = _next_trade_window(conn, job_id)
    if window is None:
        run_id = _insert_run(conn, job_id, trigger_type, "{}", group_run_id)
        _finish_run(conn, run_id, "failed", 0, "请先在调度运行监控中填写下次开始日期和下次结束日期")
        _finish_job(conn, job_id, "failed", None)
        _cleanup_runs(conn, job_id)
        return False
    start, end = window
    if start > _today_text():
        run_id = _insert_run(conn, job_id, trigger_type, "{}", group_run_id)
        _finish_run(conn, run_id, "failed", 0, "下次开始日期不能超过当天")
        _finish_job(conn, job_id, "failed", None)
        _cleanup_runs(conn, job_id)
        return False
    days = _inclusive_days(start, end)
    _finish_job(conn, job_id, "running", None)
    base = json.loads(job.get("params_json") or "{}")
    base.pop("start_date", None)
    base.pop("end_date", None)
    base.pop("trade_date", None)
    resolved = _resolve_params(job, base)
    total = 0
    watermark = None
    first_id = 0
    last_id = 0
    attempts = 1 + int(job.get("retry") or 0)
    for index, day in enumerate(days):
        params = {**resolved, "trade_date": day}
        snapshot = json.dumps(params, ensure_ascii=False)
        run_id = _insert_run(conn, job_id, trigger_type, snapshot, group_run_id)
        if not first_id:
            first_id = run_id
        last_id = run_id
        error = ""
        done = False
        for attempt in range(attempts):
            try:
                items = _fetch_all(job, params, _fields(job))
                count = tushare_writer.write_result(
                    conn,
                    job["target_table"],
                    _pks(job),
                    _fields(job),
                    items,
                    job["source"],
                    _field_types(job),
                )
                _finish_run(conn, run_id, "success", count, f"写入 {count} 行")
                total += count
                watermark = _watermark(job, items) or watermark
                done = True
                break
            except Exception as exc:
                error = str(exc)[:500]
                if attempt + 1 < attempts:
                    time.sleep(RETRY_INTERVAL_SECONDS)
        if not done:
            _finish_run(conn, run_id, "failed", 0, error or "执行失败")
            _finish_job(conn, job_id, "failed", None)
            _cleanup_runs(conn, job_id)
            return False
        if index + 1 < len(days):
            time.sleep(DAY_GAP_SECONDS)
    _finish_job(conn, job_id, "success", watermark)
    _cleanup_runs(conn, job_id)
    _advance_window(
        conn,
        job_id,
        {"trade_date": end},
        last_id,
        total,
        traded_window=(start, end),
        duration_ms=_window_duration(conn, first_id, last_id),
    )
    return True


def _next_trade_window(conn: pymysql.Connection, job_id: int) -> tuple[str, str] | None:
    state = _load_state(conn, job_id)
    if state is None:
        return None
    start = _date_text(state.get("next_start_date"))
    end = _date_text(state.get("next_end_date"))
    if not start or not end or end < start:
        return None
    return start, end


def _inclusive_days(start: str, end: str) -> list[str]:
    days = []
    day = start
    while day <= end:
        days.append(day)
        day = _add_days(day, 1)
    return days


def _window_duration(conn: pymysql.Connection, first_id: int, last_id: int) -> int | None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT started_at FROM schedule_run WHERE id=%s", (first_id,))
        first = cursor.fetchone()
        cursor.execute("SELECT finished_at FROM schedule_run WHERE id=%s", (last_id,))
        last = cursor.fetchone()
    if not first or not last:
        return None
    return _duration_ms(first["started_at"], last["finished_at"])


def execute_group(group_id: int, trigger_type: str = "cron", continue_chain: bool = True) -> bool:
    guard = _group_guard_for(group_id)
    if not guard.acquire(blocking=False):
        if trigger_type != "cron":
            _record_group_skip(group_id, trigger_type)
        return False
    conn: pymysql.Connection | None = None
    ok = False
    next_id: int | None = None
    run_id = 0
    try:
        conn = connect_app()
        group = _load_group(conn, group_id)
        if group is None:
            return False
        run_id = _insert_group_run(conn, group_id, trigger_type)
        _mark_group(conn, group_id, "running")
        jobs = _group_jobs(conn, group_id)
        failed = 0
        failed_name = ""
        if not jobs:
            ok = True
            message = "组内没有启用的任务"
        else:
            for job in jobs:
                success = execute_job(int(job["id"]), "group", None, run_id)
                if success:
                    continue
                failed += 1
                failed_name = str(job["name"])
                if group.get("stop_on_failure"):
                    break
            ok = failed == 0
            if ok:
                message = f"完成 {len(jobs)} 个任务"
            elif group.get("stop_on_failure"):
                message = f"任务「{failed_name}」未成功，已停止后续"
            else:
                message = f"完成 {len(jobs)} 个任务，其中 {failed} 个未成功"
        _finish_group_run(conn, run_id, "success" if ok else "failed", message)
        _finish_group(conn, group_id, "success" if ok else "failed")
        _cleanup_group_runs(conn, group_id)
        if ok and continue_chain:
            next_id = _next_follower_id(conn, group)
    except Exception as exc:
        print(f"任务组 {group_id} 执行异常：{exc}")
        ok = False
        if conn is not None and run_id:
            try:
                _finish_group_run(conn, run_id, "failed", str(exc)[:500] or "执行失败")
                _finish_group(conn, group_id, "failed")
            except Exception:
                pass
    finally:
        if conn is not None:
            conn.close()
        guard.release()
    if next_id is not None:
        execute_group(next_id, "chain", True)
    return ok


def _enabled_jobs() -> list[dict]:
    try:
        conn = connect_app()
    except (MySQLError, OSError) as exc:
        print(f"调度任务读取失败：{exc}")
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM schedule_job WHERE enabled=1 AND group_id IS NULL AND cron <> '' ORDER BY id"
            )
            return list(cursor.fetchall())
    except MySQLError:
        print("调度任务读取失败，请先执行 python -m app.db.migrate")
        return []
    finally:
        conn.close()


def _enabled_groups() -> list[dict]:
    try:
        conn = connect_app()
    except (MySQLError, OSError) as exc:
        print(f"任务组读取失败：{exc}")
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM schedule_group WHERE enabled=1 AND cron <> '' ORDER BY sort_order, id"
            )
            return list(cursor.fetchall())
    except MySQLError:
        print("任务组读取失败，请先执行 python -m app.db.migrate")
        return []
    finally:
        conn.close()


def _add_cron(job: dict) -> None:
    if _scheduler is None or not (job.get("cron") or "").strip():
        return
    _scheduler.add_job(
        execute_job,
        apscheduler_cron(job["cron"]),
        id=f"job-{job['id']}",
        args=[job["id"], "cron", None],
        replace_existing=True,
    )


def _add_group_cron(group: dict) -> None:
    if _scheduler is None or not (group.get("cron") or "").strip():
        return
    _scheduler.add_job(
        execute_group,
        apscheduler_cron(group["cron"]),
        id=f"group-{group['id']}",
        args=[group["id"], "cron", True],
        replace_existing=True,
    )


def apscheduler_cron(expr: str) -> CronTrigger:
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("cron 表达式需要 5 段")
    minute, hour, day_of_month, month, day_of_week = fields
    converted = f"{minute} {hour} {day_of_month} {month} {_convert_day_of_week(day_of_week)}"
    return CronTrigger.from_crontab(converted, timezone=TZ)


def _convert_day_of_week(field: str) -> str:
    parts = []
    for token in field.split(","):
        step = ""
        if "/" in token:
            token, step = token.split("/", 1)
            step = "/" + step
        if token in ("*", "?"):
            parts.append(token + step)
        elif "-" in token:
            start, end = token.split("-", 1)
            parts.append(f"{_day_number(start)}-{_day_number(end)}{step}")
        else:
            parts.append(_day_number(token) + step)
    return ",".join(parts)


def _day_number(value: str) -> str:
    if not value.isdigit():
        return value
    number = int(value)
    if number == 7:
        number = 0
    if not 0 <= number <= 6:
        raise ValueError("cron 星期段超出范围")
    return str((number + 6) % 7)


def _guard_for(job_id: int) -> threading.Lock:
    with _guards_lock:
        guard = _guards.get(job_id)
        if guard is None:
            guard = threading.Lock()
            _guards[job_id] = guard
        return guard


def _group_guard_for(group_id: int) -> threading.Lock:
    with _guards_lock:
        guard = _group_guards.get(group_id)
        if guard is None:
            guard = threading.Lock()
            _group_guards[group_id] = guard
        return guard


def _load_group(conn: pymysql.Connection, group_id: int) -> dict | None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM schedule_group WHERE id=%s", (group_id,))
        return cursor.fetchone()


def _group_jobs(conn: pymysql.Connection, group_id: int) -> list[dict]:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM schedule_job WHERE group_id=%s AND enabled=1 ORDER BY sort_order, id",
            (group_id,),
        )
        return list(cursor.fetchall())


def _next_follower_id(conn: pymysql.Connection, group: dict) -> int | None:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, follow_previous FROM schedule_group "
            "WHERE enabled=1 AND (sort_order > %s OR (sort_order = %s AND id > %s)) "
            "ORDER BY sort_order, id LIMIT 1",
            (group["sort_order"], group["sort_order"], group["id"]),
        )
        row = cursor.fetchone()
    if row is None or not row["follow_previous"]:
        return None
    return int(row["id"])


def _load_job(conn: pymysql.Connection, job_id: int) -> dict | None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM schedule_job WHERE id=%s", (job_id,))
        return cursor.fetchone()


def _fields(job: dict) -> list[str]:
    return json.loads(job.get("fields_json") or "[]")


def _pks(job: dict) -> list[str]:
    return [part.strip() for part in (job.get("primary_keys") or "").split(",") if part.strip()]


def _field_types(job: dict) -> dict[str, str]:
    try:
        schema = load_schema(str(job["doc_id"]))
    except TushareError:
        return {}
    return {field["name"]: field["type"] for field in schema["fields"]}


def _resolve_params(job: dict, override_params: dict | None) -> dict[str, str]:
    raw = override_params if override_params is not None else json.loads(job.get("params_json") or "{}")
    return {
        key: _PLACEHOLDER.sub(lambda match: _placeholder_value(match.group(1), job), str(value))
        for key, value in raw.items()
    }


def _placeholder_value(name: str, job: dict) -> str:
    today = datetime.now(TZ).date()
    if name == "today":
        return today.strftime("%Y%m%d")
    if name == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y%m%d")
    if name == "trade_date":
        return _latest_trade_date(today)
    return job.get("watermark") or (today - timedelta(days=1)).strftime("%Y%m%d")


def _latest_trade_date(today) -> str:
    try:
        conn = tushare_writer.connect_data()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT MAX(cal_date) FROM fut_trade_cal WHERE is_open=1 AND cal_date <= %s",
                    (today.strftime("%Y%m%d"),),
                )
                row = cursor.fetchone()
            if row and row[0]:
                return str(row[0])
        finally:
            conn.close()
    except Exception:
        pass
    return today.strftime("%Y%m%d")


def _expand(params: dict[str, str]) -> list[dict[str, str]]:
    combos = [params]
    for key, value in params.items():
        options = [part.strip() for part in value.split(",") if part.strip()]
        if len(options) > 1:
            combos = [{**base, key: option} for base in combos for option in options]
    return combos


def _fetch_all(job: dict, params: dict[str, str], fields: list[str]) -> list[list]:
    items: list[list] = []
    for combo in _expand(params):
        offset = 0
        for _ in range(MAX_PAGES):
            page = {**combo, "limit": str(PAGE_SIZE), "offset": str(offset)}
            result = query_api(job["source"], job["api_name"], page, fields)
            batch = result["items"]
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    return items


def _watermark(job: dict, items: list[list]) -> str | None:
    fields = _fields(job)
    if "trade_date" not in fields or not items:
        return None
    index = fields.index("trade_date")
    values = [str(row[index]) for row in items if index < len(row) and row[index] not in (None, "")]
    if not values:
        return None
    newest = max(values)
    current = job.get("watermark") or ""
    return max(newest, current) if current else newest


def _insert_run(
    conn: pymysql.Connection,
    job_id: int,
    trigger_type: str,
    snapshot: str,
    group_run_id: int | None = None,
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO schedule_run (job_id, group_run_id, trigger_type, started_at, status, params_snapshot) "
            "VALUES (%s, %s, %s, NOW(), 'running', %s)",
            (job_id, group_run_id, trigger_type, snapshot),
        )
        return int(cursor.lastrowid)


def _finish_run(conn: pymysql.Connection, run_id: int, status: str, count: int, message: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE schedule_run SET status=%s, finished_at=NOW(), row_count=%s, message=%s WHERE id=%s",
            (status, count, message[:500], run_id),
        )


def _finish_job(conn: pymysql.Connection, job_id: int, status: str, watermark: str | None) -> None:
    with conn.cursor() as cursor:
        if watermark:
            cursor.execute(
                "UPDATE schedule_job SET last_status=%s, last_run_at=NOW(), watermark=%s WHERE id=%s",
                (status, watermark, job_id),
            )
        else:
            cursor.execute(
                "UPDATE schedule_job SET last_status=%s, last_run_at=NOW() WHERE id=%s",
                (status, job_id),
            )


def _record_skip(job_id: int, trigger_type: str, group_run_id: int | None = None) -> None:
    try:
        conn = connect_app()
    except (MySQLError, OSError):
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO schedule_run (job_id, group_run_id, trigger_type, started_at, finished_at, status, message) "
                "VALUES (%s, %s, %s, NOW(), NOW(), 'failed', '上一次运行尚未结束，本次跳过')",
                (job_id, group_run_id, trigger_type),
            )
    finally:
        conn.close()


def _insert_group_run(conn: pymysql.Connection, group_id: int, trigger_type: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO schedule_group_run (group_id, trigger_type, started_at, status) "
            "VALUES (%s, %s, NOW(), 'running')",
            (group_id, trigger_type),
        )
        return int(cursor.lastrowid)


def _finish_group_run(conn: pymysql.Connection, run_id: int, status: str, message: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE schedule_group_run SET status=%s, finished_at=NOW(), message=%s WHERE id=%s",
            (status, message[:500], run_id),
        )


def _mark_group(conn: pymysql.Connection, group_id: int, status: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute("UPDATE schedule_group SET last_status=%s WHERE id=%s", (status, group_id))


def _finish_group(conn: pymysql.Connection, group_id: int, status: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE schedule_group SET last_status=%s, last_run_at=NOW() WHERE id=%s",
            (status, group_id),
        )


def _record_group_skip(group_id: int, trigger_type: str) -> None:
    try:
        conn = connect_app()
    except (MySQLError, OSError):
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO schedule_group_run (group_id, trigger_type, started_at, finished_at, status, message) "
                "VALUES (%s, %s, NOW(), NOW(), 'failed', '上一次运行尚未结束，本次跳过')",
                (group_id, trigger_type),
            )
    finally:
        conn.close()


def _cleanup_group_runs(conn: pymysql.Connection, group_id: int) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM schedule_group_run WHERE group_id=%s AND id NOT IN ("
            "SELECT id FROM (SELECT id FROM schedule_group_run WHERE group_id=%s ORDER BY id DESC LIMIT %s) keep"
            ")",
            (group_id, group_id, KEEP_RUNS),
        )


def _cleanup_runs(conn: pymysql.Connection, job_id: int) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM schedule_run WHERE job_id=%s AND id NOT IN ("
            "SELECT id FROM (SELECT id FROM schedule_run WHERE job_id=%s ORDER BY id DESC LIMIT %s) keep"
            ")",
            (job_id, job_id, KEEP_RUNS),
        )


_DATE_TEXT = re.compile(r"^\d{8}$")
_MAX_INTERVAL = 20000
_STATE_SQL = (
    "SELECT s.job_id, s.date_interval, s.next_start_date, s.next_end_date, "
    "s.last_success_start, s.last_success_end, s.last_duration_ms, s.last_row_count, s.last_success_at, "
    "j.name AS job_name, j.last_status, g.name AS group_name "
    "FROM schedule_run_state s "
    "JOIN schedule_job j ON j.id = s.job_id "
    "LEFT JOIN schedule_group g ON g.id = j.group_id "
)


def list_run_states() -> list[dict]:
    conn = connect_app()
    try:
        _ensure_run_states(conn)
        _sync_param_dates(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                _STATE_SQL + "ORDER BY (j.group_id IS NULL), IFNULL(g.sort_order, 0), IFNULL(g.id, 0), "
                "j.sort_order, j.id"
            )
            rows = list(cursor.fetchall())
        return [_state_out(row) for row in rows]
    finally:
        conn.close()


def save_run_state(job_id: int, payload: dict) -> dict | None:
    conn = connect_app()
    try:
        job = _load_job(conn, job_id)
        if job is None:
            return None
        _insert_state_if_missing(conn, job)
        interval = int(payload["dateInterval"])
        if not 1 <= interval <= _MAX_INTERVAL:
            raise ValueError("日期间隔需要在 1 到 20000 天之间")
        next_start = _normalize_date(payload.get("nextStartDate") or "", "下次开始日期")
        next_end = _normalize_date(payload.get("nextEndDate") or "", "下次结束日期")
        last_start = _normalize_date(payload.get("lastSuccessStart") or "", "上次成功开始日期")
        last_end = _normalize_date(payload.get("lastSuccessEnd") or "", "上次成功结束日期")
        if next_start and not next_end:
            next_end = _add_days(next_start, interval - 1)
        if not next_start and not next_end and last_end:
            next_start = _add_days(last_end, 1)
            next_end = _add_days(next_start, interval - 1)
        if _trade_window_job(job) and next_start and next_start > _today_text():
            raise ValueError("下次开始日期不能超过当天")
        if next_start and next_end and next_end < next_start:
            raise ValueError("下次结束日期不能早于开始日期")
        if last_start and last_end and last_end < last_start:
            raise ValueError("上次成功结束日期不能早于开始日期")
        success_at = _normalize_time(payload.get("lastSuccessAt") or "")
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE schedule_run_state SET date_interval=%s, next_start_date=%s, next_end_date=%s, "
                "last_success_start=%s, last_success_end=%s, last_duration_ms=%s, last_row_count=%s, "
                "last_success_at=%s WHERE job_id=%s",
                (
                    interval,
                    next_start,
                    next_end,
                    last_start,
                    last_end,
                    payload.get("durationMs"),
                    payload.get("lastRowCount"),
                    success_at,
                    job_id,
                ),
            )
        if not _clock_window_job(job):
            _write_window_params(conn, job_id, next_start, next_end)
        return _load_state_view(conn, job_id)
    finally:
        conn.close()


def refresh_job_window(job_id: int) -> None:
    try:
        conn = connect_app()
    except (MySQLError, OSError):
        return
    try:
        job = _load_job(conn, job_id)
        if job is None:
            return
        if _insert_state_if_missing(conn, job):
            return
        _copy_literal_params(conn, job)
    except MySQLError as exc:
        if not (exc.args and exc.args[0] == 1146):
            print(f"任务 {job_id} 运行状态未同步：{exc}")
    finally:
        conn.close()


def _advance_window(
    conn: pymysql.Connection,
    job_id: int,
    params: dict[str, str],
    run_id: int,
    count: int,
    traded_window: tuple[str, str] | None = None,
    duration_ms: int | None = None,
) -> None:
    try:
        job = _load_job(conn, job_id)
        if job is None:
            return
        _insert_state_if_missing(conn, job)
        state = _load_state(conn, job_id)
        if state is None:
            return
        with conn.cursor() as cursor:
            cursor.execute("SELECT started_at, finished_at FROM schedule_run WHERE id=%s", (run_id,))
            run = cursor.fetchone()
        if duration_ms is None:
            duration_ms = _duration_ms(run["started_at"], run["finished_at"]) if run else None
        success_at = (run or {}).get("finished_at") or (run or {}).get("started_at")
        raw = json.loads(job.get("params_json") or "{}")
        kind, start_key, _end_key = _date_binding(raw, job)
        if kind == "range":
            start = _date_text(params.get("start_date"))
            end = _date_text(params.get("end_date"))
            linked = bool(_date_text(raw.get("start_date")) and _date_text(raw.get("end_date")))
        elif kind == "single":
            start = _date_text(params.get(start_key))
            end = start
            linked = bool(_date_text(raw.get(start_key)))
        else:
            start, end, linked = "", "", False
        last_end = _date_text(state["last_success_end"])
        interval = int(state["date_interval"] or 1)
        moved = bool(linked and start and end and (not last_end or end > last_end))
        next_start = state["next_start_date"]
        next_end = state["next_end_date"]
        last_start = state["last_success_start"]
        stored_end = last_end
        if start and end and (not last_end or end >= last_end):
            last_start = start
            stored_end = end
        if traded_window and _trade_window_job(job):
            start, end = traded_window
            last_start = start
            stored_end = end
            moved = True
        if _clock_window_job(job):
            run_day = _run_day(success_at)
            last_start = run_day
            stored_end = run_day
            next_start = _add_days(run_day, 1)
            next_end = next_start
        elif moved:
            next_start = _add_days(end, 1)
            next_end = _add_days(next_start, max(interval, 1) - 1)
            if _trade_window_job(job) and next_start > _today_text():
                next_start = _today_text()
                next_end = _add_days(next_start, max(interval, 1) - 1)
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE schedule_run_state SET next_start_date=%s, next_end_date=%s, last_success_start=%s, "
                "last_success_end=%s, last_duration_ms=%s, last_row_count=%s, last_success_at=%s WHERE job_id=%s",
                (next_start, next_end, last_start, stored_end, duration_ms, count, success_at, job_id),
            )
        if moved and not _clock_window_job(job):
            _write_window_params(conn, job_id, next_start, next_end)
    except MySQLError as exc:
        if not (exc.args and exc.args[0] == 1146):
            print(f"任务 {job_id} 运行状态未更新：{exc}")
    except Exception as exc:
        print(f"任务 {job_id} 运行状态未更新：{exc}")


def _ensure_run_states(conn: pymysql.Connection) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT j.* FROM schedule_job j "
            "LEFT JOIN schedule_run_state s ON s.job_id = j.id WHERE s.id IS NULL"
        )
        missing = list(cursor.fetchall())
        cursor.execute(
            "DELETE s FROM schedule_run_state s LEFT JOIN schedule_job j ON j.id = s.job_id WHERE j.id IS NULL"
        )
    for job in missing:
        _insert_state_if_missing(conn, job)


def _insert_state_if_missing(conn: pymysql.Connection, job: dict) -> bool:
    job_id = int(job["id"])
    if _load_state(conn, job_id) is not None:
        return False
    seeded = _seed_state(conn, job)
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO schedule_run_state (job_id, date_interval, next_start_date, next_end_date, "
            "last_success_start, last_success_end, last_duration_ms, last_row_count, last_success_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                job_id,
                seeded["interval"],
                seeded["next_start"],
                seeded["next_end"],
                seeded["last_start"],
                seeded["last_end"],
                seeded["duration_ms"],
                seeded["row_count"],
                seeded["success_at"],
            ),
        )
    return True


def _seed_state(conn: pymysql.Connection, job: dict) -> dict:
    params = json.loads(job.get("params_json") or "{}")
    kind, start_key, end_key = _date_binding(params, job)
    if kind == "range":
        param_start = _date_text(params.get(start_key))
        param_end = _date_text(params.get(end_key))
    elif kind == "single":
        param_start = _date_text(params.get(start_key))
        param_end = ""
    else:
        param_start, param_end = "", ""
    last = _latest_success(conn, int(job["id"]))
    last_start = ""
    last_end = ""
    duration_ms = None
    row_count = None
    success_at = None
    if last is not None:
        snapshot = json.loads(last.get("params_snapshot") or "{}")
        last_start = _date_text(snapshot.get("start_date"))
        last_end = _date_text(snapshot.get("end_date"))
        duration_ms = _duration_ms(last.get("started_at"), last.get("finished_at"))
        row_count = int(last.get("row_count") or 0)
        success_at = last.get("finished_at") or last.get("started_at")
    interval = 1
    if param_start and param_end:
        interval = min(_span_days(param_start, param_end) or 1, _MAX_INTERVAL)
    elif last_start and last_end:
        interval = min(_span_days(last_start, last_end) or 1, _MAX_INTERVAL)
    if last_end:
        next_start = _add_days(last_end, 1)
        next_end = _add_days(next_start, interval - 1)
    elif param_start and param_end:
        next_start, next_end = param_start, param_end
    elif param_start:
        next_start = param_start
        next_end = _add_days(param_start, interval - 1)
    else:
        next_start, next_end = "", ""
    return {
        "interval": interval,
        "next_start": next_start,
        "next_end": next_end,
        "last_start": last_start,
        "last_end": last_end,
        "duration_ms": duration_ms,
        "row_count": row_count,
        "success_at": success_at,
    }


def _copy_literal_params(conn: pymysql.Connection, job: dict) -> None:
    _apply_param_dates(conn, job)


def _sync_param_dates(conn: pymysql.Connection) -> None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM schedule_job")
        jobs = list(cursor.fetchall())
    for job in jobs:
        _apply_param_dates(conn, job)


def _apply_param_dates(conn: pymysql.Connection, job: dict) -> None:
    if _clock_window_job(job) or _trade_window_job(job):
        return
    state = _load_state(conn, int(job["id"]))
    if state is None:
        return
    params = json.loads(job.get("params_json") or "{}")
    kind, start_key, end_key = _date_binding(params, job)
    interval = int(state["date_interval"] or 1)
    if kind == "range":
        start = _date_text(params.get(start_key))
        end = _date_text(params.get(end_key))
        if not start or not end or end < start:
            return
        if start == _date_text(state["next_start_date"]) and end == _date_text(state["next_end_date"]):
            return
        span = _span_days(start, end)
        if span:
            interval = min(span, _MAX_INTERVAL)
        next_start, next_end = start, end
    elif kind == "single":
        start = _date_text(params.get(start_key))
        if not start or start == _date_text(state["next_start_date"]):
            return
        next_start = start
        next_end = _add_days(start, max(interval, 1) - 1)
    else:
        return
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE schedule_run_state SET date_interval=%s, next_start_date=%s, next_end_date=%s WHERE job_id=%s",
            (interval, next_start, next_end, job["id"]),
        )


_DATE_PARAM_KEYS = ("trade_date", "date", "cal_date", "ann_date", "list_date")


def _clock_window_job(job: dict | None) -> bool:
    if not job:
        return False
    if job.get("api_name") == "fut_trade_cal" or job.get("name") == "期货交易日历":
        return True
    return job.get("name") == "期货合约信息"


def _manual_end_date(job: dict | None) -> bool:
    if not job:
        return False
    return job.get("api_name") == "fut_trade_cal" or job.get("name") == "期货交易日历"


def _today_text() -> str:
    return datetime.now(TZ).strftime("%Y%m%d")


def _run_day(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    text = str(value or "").strip().replace("T", " ")
    if len(text) >= 10 and text[4] == "-":
        return text[:10].replace("-", "")
    parsed = _date_text(text)
    return parsed or datetime.now(TZ).strftime("%Y%m%d")


def _trade_window_job(job: dict | None) -> bool:
    return bool(job) and job.get("name") in ("期货日线行情", "期货复权行情", "每日结算参数")


def _date_binding(params: dict, job: dict | None = None) -> tuple[str, str, str]:
    if _manual_end_date(job):
        params = {key: value for key, value in params.items() if key != "end_date"}
    if "start_date" in params and "end_date" in params:
        return "range", "start_date", "end_date"
    for key in _DATE_PARAM_KEYS:
        if key in params:
            return "single", key, ""
    for key in params:
        if str(key).endswith("_date") and key not in ("start_date", "end_date"):
            return "single", str(key), ""
    if "start_date" in params:
        return "single", "start_date", ""
    if "end_date" in params:
        return "single", "end_date", ""
    return "none", "", ""


def _write_window_params(conn: pymysql.Connection, job_id: int, start: str, end: str) -> None:
    job = _load_job(conn, job_id)
    if job is None or _clock_window_job(job):
        return
    params = json.loads(job.get("params_json") or "{}")
    if _trade_window_job(job):
        params.pop("start_date", None)
        params.pop("end_date", None)
        _assign_bound_date(params, "trade_date", start)
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE schedule_job SET params_json=%s WHERE id=%s",
                (json.dumps(params, ensure_ascii=False), job_id),
            )
        return
    kind, start_key, end_key = _date_binding(params, job)
    if kind == "range":
        _assign_bound_date(params, start_key, start)
        _assign_bound_date(params, end_key, end)
    elif kind == "single":
        _assign_bound_date(params, start_key, start)
    else:
        return
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE schedule_job SET params_json=%s WHERE id=%s",
            (json.dumps(params, ensure_ascii=False), job_id),
        )


def _assign_bound_date(params: dict, key: str, value: str) -> None:
    if value:
        params[key] = value
    elif _date_text(params.get(key)):
        params.pop(key, None)


def _latest_success(conn: pymysql.Connection, job_id: int) -> dict | None:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT params_snapshot, started_at, finished_at, row_count FROM schedule_run "
            "WHERE job_id=%s AND status='success' ORDER BY id DESC LIMIT 1",
            (job_id,),
        )
        return cursor.fetchone()


def _load_state(conn: pymysql.Connection, job_id: int) -> dict | None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM schedule_run_state WHERE job_id=%s", (job_id,))
        return cursor.fetchone()


def _load_state_view(conn: pymysql.Connection, job_id: int) -> dict | None:
    with conn.cursor() as cursor:
        cursor.execute(_STATE_SQL + "WHERE j.id=%s", (job_id,))
        row = cursor.fetchone()
    return _state_out(row) if row else None


def _state_out(row: dict) -> dict:
    duration = row["last_duration_ms"]
    return {
        "jobId": int(row["job_id"]),
        "groupName": row["group_name"] or "",
        "jobName": row["job_name"],
        "dateInterval": int(row["date_interval"] or 1),
        "nextStartDate": row["next_start_date"] or "",
        "nextEndDate": row["next_end_date"] or "",
        "lastSuccessStart": row["last_success_start"] or "",
        "lastSuccessEnd": row["last_success_end"] or "",
        "durationMs": int(duration) if duration is not None else None,
        "lastRowCount": int(row["last_row_count"]) if row["last_row_count"] is not None else None,
        "lastSuccessAt": row["last_success_at"].strftime("%Y-%m-%d %H:%M:%S") if row["last_success_at"] else "",
        "lastStatus": row["last_status"] or "",
    }


def _normalize_date(value: str, label: str) -> str:
    text = str(value).strip().replace("-", "")
    if not text:
        return ""
    if not _date_text(text):
        raise ValueError(f"{label}需要是 8 位日期，例如 20261004")
    return text


def _normalize_time(value: str) -> datetime | None:
    text = str(value).strip().replace("T", " ")
    if not text:
        return None
    if len(text) == 16:
        text += ":00"
    try:
        return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError("最近成功时间格式应为 2026-10-04 17:46:16") from exc


def _date_text(value) -> str:
    text = str(value or "").strip()
    if not _DATE_TEXT.fullmatch(text):
        return ""
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError:
        return ""
    return text


def _add_days(text: str, days: int) -> str:
    return (datetime.strptime(text, "%Y%m%d").date() + timedelta(days=days)).strftime("%Y%m%d")


def _span_days(start: str, end: str) -> int | None:
    if end < start:
        return None
    return (datetime.strptime(end, "%Y%m%d").date() - datetime.strptime(start, "%Y%m%d").date()).days + 1


def _duration_ms(started, finished) -> int | None:
    if not started or not finished:
        return None
    millis = int((finished - started).total_seconds() * 1000)
    return millis if millis >= 0 else None
