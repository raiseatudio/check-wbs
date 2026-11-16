"""Đọc WBS và GDD, gọi OpenAI theo SKILL.md, rồi ghi nhận xét lên pull request."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

MAX_CHARS = 120_000
MAX_COMMENT = 65_000
MARKER = "<!-- check-wbs -->"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1"
SUPPORTED_EXT = {".csv", ".tsv"}
SPREADSHEET_EXT = SUPPORTED_EXT | {".xlsx", ".xls", ".xlsm", ".ods"}
SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".venv", "venv"}
SYSTEM_PROMPT = (
    "Bạn là người review WBS. Tuân thủ đúng SKILL.md trong phần người dùng. "
    "Trả lời bằng tiếng Việt, đúng khuôn báo cáo trong SKILL.md. "
    "Không thêm luật nghiệp vụ ngoài SKILL.md. "
    "Không bịa dòng không có trong bảng."
)


def classify_path(path: str) -> str | None:
    """Phân loại đường dẫn tương đối.

    Trả về "wbs", "gdd", "ambiguous", "unsupported", hoặc None nếu không phải file cần xét.
    Thư mục phải đúng tên "wbs" hoặc "gdd". Tên file khớp khi token đứng riêng,
    ví dụ WBS_export.csv hoặc my-gdd.tsv. mywbs.csv không khớp.
    """
    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.endswith("/"):
        return None
    parts = [part for part in normalized.split("/") if part and part not in {".", ".."}]
    if not parts:
        return None
    filename = parts[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in SPREADSHEET_EXT:
        return None

    kinds: set[str] = set()
    for segment in parts[:-1]:
        lower = segment.lower()
        if lower == "wbs":
            kinds.add("wbs")
        elif lower == "gdd":
            kinds.add("gdd")
    stem_and_suffix = filename.lower()
    if _has_token(stem_and_suffix, "wbs"):
        kinds.add("wbs")
    if _has_token(stem_and_suffix, "gdd"):
        kinds.add("gdd")
    if not kinds:
        return None
    if len(kinds) > 1:
        return "ambiguous"
    if suffix not in SUPPORTED_EXT:
        return "unsupported"
    return "wbs" if "wbs" in kinds else "gdd"


def _has_token(filename: str, token: str) -> bool:
    start = 0
    while True:
        index = filename.find(token, start)
        if index < 0:
            return False
        before_ok = index == 0 or not filename[index - 1].isalpha()
        after = index + len(token)
        after_ok = after == len(filename) or not filename[after].isalpha()
        if before_ok and after_ok:
            return True
        start = index + 1


@dataclass(frozen=True)
class Inventory:
    wbs: list[Path]
    gdd: list[Path]
    ambiguous: list[Path]
    unsupported: list[Path]


def collect(root: Path) -> Inventory:
    wbs: list[Path] = []
    gdd: list[Path] = []
    ambiguous: list[Path] = []
    unsupported: list[Path] = []
    buckets = {
        "wbs": wbs,
        "gdd": gdd,
        "ambiguous": ambiguous,
        "unsupported": unsupported,
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in SKIP_DIRS and not name.startswith(".")
        )
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            kind = classify_path(relative)
            if kind is None:
                continue
            buckets[kind].append(path)
    return Inventory(wbs, gdd, ambiguous, unsupported)


def read_limited(path: Path) -> tuple[str, int, bool]:
    kept: list[str] = []
    kept_len = 0
    line_count = 0
    truncated = False
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            line_count += 1
            if kept_len >= MAX_CHARS:
                truncated = True
                continue
            room = MAX_CHARS - kept_len
            if len(line) > room:
                kept.append(line[:room])
                kept_len += room
                truncated = True
                continue
            kept.append(line)
            kept_len += len(line)
    return "".join(kept), line_count, truncated


def fence_for(text: str) -> str:
    longest = 0
    current = 0
    for char in text:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * max(3, longest + 1)


def render_file(root: Path, path: Path, kind: str) -> str:
    text, line_count, truncated = read_limited(path)
    relative = path.relative_to(root).as_posix()
    label = "WBS" if kind == "wbs" else "GDD"
    note = f"{line_count} dòng"
    if truncated:
        note += f", nội dung đã cắt còn {MAX_CHARS} ký tự"
    fence = fence_for(text)
    return f"## `{relative}` ({label}, {note})\n\n{fence}\n{text}\n{fence}\n"


def build_user_prompt(skill: str, root: Path, inventory: Inventory) -> str:
    parts = ["# SKILL.md", "", skill.strip(), "", "# Bảng WBS", ""]
    for path in inventory.wbs:
        parts.append(render_file(root, path, "wbs"))
    parts.append("# Bảng GDD")
    parts.append("")
    for path in inventory.gdd:
        parts.append(render_file(root, path, "gdd"))
    parts.append("Hãy viết báo cáo theo đúng khuôn trong SKILL.md.")
    return "\n".join(parts)


def skipped_section(root: Path, inventory: Inventory) -> str:
    lines: list[str] = []
    if inventory.ambiguous:
        lines.append("### File bị bỏ qua vì tên vừa là WBS vừa là GDD")
        lines.append("")
        for path in inventory.ambiguous:
            lines.append(f"- `{path.relative_to(root).as_posix()}`")
        lines.append("")
    if inventory.unsupported:
        lines.append("### File không đọc được")
        lines.append("")
        lines.append("Chỉ nhận CSV hoặc TSV. Hãy export từ Google Sheet.")
        lines.append("")
        for path in inventory.unsupported:
            lines.append(f"- `{path.relative_to(root).as_posix()}`")
        lines.append("")
    return "\n".join(lines).rstrip()


def guidance(inventory: Inventory) -> str:
    missing = []
    if not inventory.wbs:
        missing.append("WBS")
    if not inventory.gdd:
        missing.append("GDD")
    joined = " và ".join(missing)
    return (
        f"Thiếu file {joined} trên commit này.\n\n"
        "Cần ít nhất một file WBS và một file GDD dạng CSV hoặc TSV:\n"
        "- Đặt trong thư mục `wbs/` hoặc `gdd/`, hoặc\n"
        "- Đặt tên file có token `wbs` / `gdd` "
        "(ví dụ `WBS_export.csv`, `my-gdd.tsv`).\n\n"
        "File Excel không được đọc. Hãy export CSV hoặc TSV từ Google Sheet."
    )


def compose_comment(body: str, root: Path, inventory: Inventory) -> str:
    skipped = skipped_section(root, inventory)
    text = body.strip()
    if skipped:
        text = f"{text}\n\n{skipped}"
    comment = f"{MARKER}\n\n{text}\n"
    if len(comment) <= MAX_COMMENT:
        return comment
    notice = "\n\nBáo cáo bị cắt vì vượt quá độ dài comment của GitHub.\n"
    keep = MAX_COMMENT - len(notice) - len(MARKER) - 4
    return f"{MARKER}\n\n{text[:keep].rstrip()}{notice}"


def resolve_pr_number() -> str:
    explicit = os.environ.get("PR_NUMBER", "").strip()
    if explicit:
        return explicit
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return ""
    path = Path(event_path)
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    number = data.get("pull_request", {}).get("number") if isinstance(data, dict) else None
    if isinstance(number, int):
        return str(number)
    return ""


def write_summary(text: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary:
        print(text)
        return
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def github_json(token: str, method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "check-wbs",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"GitHub trả về HTTP {exc.code}: {detail}") from exc
    if not raw:
        return None
    return json.loads(raw)


def upsert_comment(token: str, repository: str, pr_number: str, comment: str) -> None:
    page = 1
    existing_id = None
    while True:
        url = (
            f"https://api.github.com/repos/{repository}/issues/{pr_number}/comments"
            f"?per_page=100&page={page}"
        )
        batch = github_json(token, "GET", url)
        if not isinstance(batch, list):
            raise RuntimeError("GitHub không trả về danh sách comment.")
        for item in batch:
            body = item.get("body") or ""
            if MARKER in body:
                existing_id = item.get("id")
                break
        if existing_id is not None or len(batch) < 100:
            break
        page += 1
    payload = {"body": comment}
    if existing_id is None:
        github_json(
            token,
            "POST",
            f"https://api.github.com/repos/{repository}/issues/{pr_number}/comments",
            payload,
        )
        return
    github_json(
        token,
        "PATCH",
        f"https://api.github.com/repos/{repository}/issues/comments/{existing_id}",
        payload,
    )


def publish(body: str, root: Path, inventory: Inventory) -> None:
    comment = compose_comment(body, root, inventory)
    write_summary(comment)
    pr_number = resolve_pr_number()
    if not pr_number:
        return
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repository:
        raise RuntimeError("Thiếu GITHUB_TOKEN hoặc GITHUB_REPOSITORY để ghi comment.")
    upsert_comment(token, repository, pr_number, comment)


def call_openai(api_key: str, model: str, user_prompt: str) -> str:
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    request = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"OpenAI trả về HTTP {exc.code}: {detail}") from exc
    data = json.loads(raw)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("OpenAI không trả về nội dung review.") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenAI trả về nội dung review rỗng.")
    return content.strip()


def repo_root() -> Path:
    workspace = os.environ.get("GITHUB_WORKSPACE", "").strip()
    if workspace:
        return Path(workspace)
    return Path.cwd()


def run() -> int:
    root = repo_root()
    inventory = collect(root)
    if not inventory.wbs or not inventory.gdd:
        publish(guidance(inventory), root, inventory)
        return 0

    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        publish(
            "Thiếu SKILL.md ở thư mục gốc của repo. Action cần file này làm bộ luật review.",
            root,
            inventory,
        )
        return 1
    skill = skill_path.read_text(encoding="utf-8-sig", errors="replace").strip()
    if not skill:
        publish("SKILL.md đang trống. Hãy điền bộ luật review trước khi chạy.", root, inventory)
        return 1

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        publish("Thiếu secret OPENAI_API_KEY. Không gọi OpenAI.", root, inventory)
        return 1
    model = os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
    report = call_openai(api_key, model, build_user_prompt(skill, root, inventory))
    publish(report, root, inventory)
    return 0


def main() -> int:
    try:
        return run()
    except Exception as exc:
        message = f"Kiểm tra WBS thất bại: {exc}"
        print(message, file=sys.stderr)
        try:
            publish(message, repo_root(), collect(repo_root()))
        except Exception as publish_error:
            print(f"Không ghi được báo cáo: {publish_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
