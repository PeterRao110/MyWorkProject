from dataclasses import dataclass
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "versions"
DOCUMENT_PATH = Path(__file__).resolve().parents[3] / "docs" / "database" / "模型变更记录.md"

ACTION_LABELS = {
    "create": "新建",
    "alter": "修改",
    "drop": "删除",
}


@dataclass(frozen=True)
class ModelChange:
    seq: int
    model_name: str
    action: str
    summary: str
    ddl: str


@dataclass(frozen=True)
class SchemaVersion:
    version: str
    title: str
    changes: tuple[ModelChange, ...]


def load_versions() -> tuple[SchemaVersion, ...]:
    versions = tuple(parse_version(path.read_text(encoding="utf-8")) for path in sorted(VERSIONS_DIR.glob("*.sql")))
    if not versions:
        raise RuntimeError("没有找到数据库版本文件")
    return versions


def parse_version(text: str) -> SchemaVersion:
    version = ""
    title = ""
    meta: dict[str, str] = {}
    statement: list[str] = []
    changes: list[ModelChange] = []

    def flush() -> None:
        ddl = "\n".join(statement).strip()
        statement.clear()
        if not ddl:
            return
        missing = [key for key in ("seq", "model", "action", "summary") if key not in meta]
        if missing:
            raise RuntimeError(f"变更语句缺少标记：{', '.join(missing)}")
        changes.append(
            ModelChange(
                seq=int(meta["seq"]),
                model_name=meta["model"],
                action=meta["action"],
                summary=meta["summary"],
                ddl=ddl,
            )
        )
        meta.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("-- version:"):
            version = line.split(":", 1)[1].strip()
        elif line.startswith("-- title:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("-- seq:"):
            flush()
            meta["seq"] = line.split(":", 1)[1].strip()
        elif line.startswith("-- model:"):
            meta["model"] = line.split(":", 1)[1].strip()
        elif line.startswith("-- action:"):
            meta["action"] = line.split(":", 1)[1].strip()
        elif line.startswith("-- summary:"):
            meta["summary"] = line.split(":", 1)[1].strip()
        elif line.startswith("--"):
            continue
        elif line:
            statement.append(raw.rstrip())
    flush()
    if not version or not title or not changes:
        raise RuntimeError("版本文件缺少版本号、标题或变更")
    sequences = [change.seq for change in changes]
    if sequences != list(range(1, len(sequences) + 1)):
        raise RuntimeError(f"版本 {version} 的序号必须从 1 连续编号")
    return SchemaVersion(version=version, title=title, changes=tuple(changes))


def render_document(versions: tuple[SchemaVersion, ...] | None = None) -> str:
    versions = versions if versions is not None else load_versions()
    lines = [
        "# 数据库模型变更记录",
        "",
        "版本号使用 `主版本.次版本.修订号`。同一版本按序号执行。",
        "每条变更同时记在本文档和数据库表 `schema_model_change` 中。已经写入该表的序号不会重复执行。",
        "新增版本时，在 `backend/db/versions/` 增加对应的 SQL 文件，再执行 `python -m app.db.migrate`。",
        "",
    ]
    for item in versions:
        lines.extend(
            [
                f"## {item.version} {item.title}",
                "",
                "| 序号 | 模型 | 动作 | 变更说明 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for change in item.changes:
            action = ACTION_LABELS.get(change.action, change.action)
            lines.append(f"| {change.seq} | `{change.model_name}` | {action} | {change.summary} |")
        lines.extend(["", "```sql"])
        for change in item.changes:
            lines.append(f"-- {change.seq}. {change.model_name}")
            lines.append(change.ddl)
            lines.append("")
        lines.extend(["```", ""])
    return "\n".join(lines).rstrip() + "\n"


def write_document() -> Path:
    DOCUMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENT_PATH.write_text(render_document(), encoding="utf-8")
    return DOCUMENT_PATH
