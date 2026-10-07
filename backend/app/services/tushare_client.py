import json
import re
from urllib import error, parse, request
from urllib.parse import urlparse

from app.services.source_config import _stored

DOC_URL = "https://tushare.pro/wctapi/documents/{doc_id}.md"
DEFAULT_API = "http://api.tushare.pro"
SOURCES = {"rds": "TUSHARE_RDS", "promax": "TUSHARE_PROMAX"}
SOURCE_LABELS = {"rds": "Tushare测试接口", "promax": "Tushare接口"}
_CACHE: dict[str, dict] = {}


class TushareError(Exception):
    pass


def load_schema(doc_id: str) -> dict:
    cached = _CACHE.get(doc_id)
    if cached:
        return cached
    schema = _parse_document(doc_id, _fetch_text(DOC_URL.format(doc_id=doc_id)))
    _CACHE[doc_id] = schema
    return schema


def query_api(source: str, api_name: str, params: dict[str, str], fields: list[str]) -> dict:
    prefix = SOURCES.get(source)
    if prefix is None:
        raise TushareError("请选择 Tushare接口或 Tushare测试接口")
    stored = _stored()
    token = stored.get(f"{prefix}_TOKEN", "").strip()
    if not token:
        label = SOURCE_LABELS[source]
        raise TushareError(f"请先在系统设置中保存{label}的 Token")
    base_url = (stored.get(f"{prefix}_BASE_URL") or DEFAULT_API).strip() or DEFAULT_API
    timeout = _number(stored.get(f"{prefix}_TIMEOUT"), 30, 1, 120)
    retry = _number(stored.get(f"{prefix}_RETRY"), 1, 0, 5)
    clean = {key: value for key, value in params.items() if value != ""}
    if urlparse(base_url).path.strip("/"):
        return _query_relay(base_url, token, api_name, clean, fields, timeout, retry, fallback=True)
    return _query_classic(base_url, token, api_name, clean, fields, timeout, retry)


def _query_classic(
    base_url: str,
    token: str,
    api_name: str,
    params: dict[str, str],
    fields: list[str],
    timeout: int,
    retry: int,
) -> dict:
    body = json.dumps(
        {"api_name": api_name, "token": token, "params": params, "fields": ",".join(fields)}
    ).encode("utf-8")
    payload = _read_json(
        request.Request(base_url, data=body, headers={"Content-Type": "application/json"}, method="POST"),
        timeout,
        retry,
    )
    return _rows(payload, fields)


def _query_relay(
    base_url: str,
    token: str,
    api_name: str,
    params: dict[str, str],
    fields: list[str],
    timeout: int,
    retry: int,
    fallback: bool,
) -> dict:
    endpoint = base_url.rstrip("/") + "/" + parse.quote(api_name)
    headers = {"X-API-Key": token, "Accept": "application/json"}
    method = "GET"
    last_error = "接口请求失败"
    for _ in range(retry + 1):
        try:
            status, payload = _send(method, endpoint, headers, params, fields, timeout)
        except (error.URLError, TimeoutError):
            last_error = "连接 Tushare 接口失败"
            continue
        if status == 405:
            allowed = _allowed_method(payload)
            if allowed and allowed != method:
                method = allowed
                try:
                    status, payload = _send(method, endpoint, headers, params, fields, timeout)
                except (error.URLError, TimeoutError):
                    last_error = "连接 Tushare 接口失败"
                    continue
        message = _message(payload)
        if status == 400 and fallback and api_name == "fut_trade_cal" and "unknown api_name" in message:
            return _query_relay(base_url, token, "trade_cal", params, fields, timeout, retry, fallback=False)
        if status >= 400:
            raise TushareError(message or f"接口返回 HTTP {status}")
        return _rows(payload, fields)
    raise TushareError(last_error)


def _send(
    method: str,
    endpoint: str,
    headers: dict[str, str],
    params: dict[str, str],
    fields: list[str],
    timeout: int,
) -> tuple[int, dict]:
    if method == "GET":
        query = dict(params)
        if fields:
            query["fields"] = ",".join(fields)
        url = endpoint + ("?" + parse.urlencode(query) if query else "")
        req = request.Request(url, headers=headers, method="GET")
    else:
        body = json.dumps({"params": params, "fields": ",".join(fields)}).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return response.status, _decode(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        return exc.code, _decode(exc.read().decode("utf-8", errors="replace"))


def _read_json(req: request.Request, timeout: int, retry: int) -> dict:
    last_error = "接口请求失败"
    for _ in range(retry + 1):
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return _decode(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            payload = _decode(exc.read().decode("utf-8", errors="replace"))
            raise TushareError(_message(payload) or f"接口返回 HTTP {exc.code}") from exc
        except (error.URLError, TimeoutError):
            last_error = "连接 Tushare 接口失败"
    raise TushareError(last_error)


def _rows(payload: dict, fields: list[str]) -> dict:
    if payload.get("ok") is False or payload.get("code") not in (None, 0, "0"):
        raise TushareError(_message(payload) or "查询失败")
    table = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    items = table.get("items") or []
    columns = table.get("fields") or fields
    message = "查询成功" if items else "没有查询到相关数据"
    if len(items) > 8000:
        items = items[:8000]
        message = "结果较多，仅显示前 8000 行"
    return {"fields": columns, "items": items, "message": message}


def _decode(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _message(payload: dict) -> str:
    for key in ("message", "msg", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip() and value.strip().lower() not in {"ok", "null"}:
            if value.lstrip().startswith("<"):
                continue
            return value.strip()
    return ""


def _allowed_method(payload: dict) -> str:
    match = re.search(r"only supports:\s*([A-Z]+)", _message(payload))
    return match.group(1) if match else ""


def _fetch_text(url: str) -> str:
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with request.urlopen(req, timeout=20) as response:
            return response.read().decode("utf-8")
    except (error.URLError, TimeoutError) as exc:
        raise TushareError("读取接口说明失败") from exc


def _parse_document(doc_id: str, text: str) -> dict:
    if text.lstrip().startswith("{"):
        raise TushareError("读取接口说明失败")
    title = _first(r"^##\s+(.+)$", text) or "接口说明"
    api_name = _first(r"接口[：:]\s*([A-Za-z_][A-Za-z0-9_]*)", text)
    desc = _first(r"描述[：:]\s*(.+)", text)
    params = _table(_section(text, ("**输入参数**", "输入参数"), ("**输出参数**", "输出参数")), kind="param")
    fields = _table(_section(text, ("**输出参数**", "输出参数"), ("**接口示例**", "**数据示例**", "接口示例")), kind="field")
    if api_name:
        _with_tool_params(doc_id, params)
    return {
        "docId": doc_id,
        "title": title,
        "apiName": api_name,
        "desc": desc,
        "params": params,
        "fields": fields,
    }


def _with_tool_params(doc_id: str, params: list[dict]) -> None:
    names = {item["name"] for item in params}
    if doc_id == "135" and "ts_code" not in names:
        index = next((i + 1 for i, item in enumerate(params) if item["name"] == "fut_type"), len(params))
        params.insert(index, {"name": "ts_code", "type": "str", "required": False, "desc": "合约代码"})
    if "limit" not in names:
        params.append({"name": "limit", "type": "int", "required": False, "desc": "单次返回数据长度"})
    if "offset" not in names:
        params.append({"name": "offset", "type": "int", "required": False, "desc": "请求数据的开始位移量"})


def _section(text: str, starts: tuple[str, ...], ends: tuple[str, ...]) -> str:
    start = _locate(text, starts)
    if start < 0:
        return ""
    end = _locate(text, ends, start)
    return text[start:end if end >= 0 else None]


def _locate(text: str, marks: tuple[str, ...], offset: int = 0) -> int:
    found = [text.find(mark, offset) for mark in marks]
    found = [item for item in found if item >= 0]
    return min(found) if found else -1


def _table(block: str, kind: str) -> list[dict]:
    rows: list[dict] = []
    for line in block.splitlines():
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in {"名称", ""} or set(cells[0]) <= {"-", ":"}:
            continue
        desc = " | ".join(cells[3:]).strip()
        if kind == "param":
            rows.append(
                {
                    "name": cells[0],
                    "type": cells[1],
                    "required": cells[2].upper() in {"Y", "是"},
                    "desc": desc,
                }
            )
        else:
            rows.append(
                {
                    "name": cells[0],
                    "type": cells[1],
                    "desc": desc,
                    "shown": cells[2].upper() in {"Y", "是"},
                }
            )
    return rows


def _first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.M)
    return match.group(1).strip() if match else ""


def _number(value: str | None, default: int, low: int, high: int) -> int:
    try:
        number = int(value or default)
    except ValueError:
        number = default
    return max(low, min(high, number))
