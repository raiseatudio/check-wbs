"""Đọc WBS và GDD, gọi Gemini theo SKILL.md, rồi gửi báo cáo vào Discord."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

MAX_CHARS = 120_000
DISCORD_BODY_LIMIT = 1_800
MAX_DISCORD_MESSAGES = 8
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
DEFAULT_MODEL = "gemini-2.5-flash"
WBS_TABLE_EXT = {".csv", ".tsv"}
WBS_UNSUPPORTED_EXT = {".xlsx", ".xls", ".xlsm", ".ods"}
GDD_TEXT_EXT = {".txt", ".text", ".md", ".markdown", ".docx", ".rtf"}
GDD_UNSUPPORTED_EXT = WBS_UNSUPPORTED_EXT | {".doc", ".pdf"}
SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".venv", "venv"}
DOCX_PARAGRAPH = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
DOCX_TEXT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
SYSTEM_PROMPT = (
    "Bạn là người review WBS. Tuân thủ đúng SKILL.md trong phần người dùng. "
    "Trả lời bằng tiếng Việt, đúng khuôn báo cáo trong SKILL.md. "
    "Không thêm luật nghiệp vụ ngoài SKILL.md. "
    "Không bịa nội dung không có trong file được gửi."
)


def classify_path(path: str) -> str | None:
    """Phân loại đường dẫn tương đối.

    Trả về "wbs", "gdd", "ambiguous", "unsupported", hoặc None nếu không phải file cần xét.
    Thư mục phải đúng tên "wbs" hoặc "gdd". Tên file khớp khi token đứng riêng,
    ví dụ WBS_export.csv hoặc my-gdd.docx. mywbs.csv không khớp.
    WBS chỉ nhận CSV/TSV. GDD nhận thêm TXT, MD, DOCX và RTF.
    """
    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.endswith("/"):
        return None
    parts = [part for part in normalized.split("/") if part and part not in {".", ".."}]
    if not parts:
        return None
    filename = parts[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in _known_extensions():
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
    if "wbs" in kinds:
        if suffix in WBS_TABLE_EXT:
            return "wbs"
        if suffix in WBS_UNSUPPORTED_EXT:
            return "unsupported"
        return None
    if suffix in WBS_TABLE_EXT or suffix in GDD_TEXT_EXT:
        return "gdd"
    if suffix in GDD_UNSUPPORTED_EXT:
        return "unsupported"
    return None


def _known_extensions() -> set[str]:
    return WBS_TABLE_EXT | WBS_UNSUPPORTED_EXT | GDD_TEXT_EXT | GDD_UNSUPPORTED_EXT


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
    text = extract_text(path)
    kept: list[str] = []
    kept_len = 0
    line_count = 0
    truncated = False
    lines = text.splitlines(keepends=True)
    if text and not lines:
        lines = [text]
    for line in lines:
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


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return docx_to_text(path)
    if suffix == ".rtf":
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        return rtf_to_text(raw)
    return path.read_text(encoding="utf-8-sig", errors="replace")


def docx_to_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            try:
                payload = archive.read("word/document.xml")
            except KeyError as exc:
                raise RuntimeError(f"Không đọc được {path.name}: thiếu nội dung Word.") from exc
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"Không đọc được {path.name}: file docx hỏng.") from exc
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise RuntimeError(f"Không đọc được {path.name}: XML hỏng.") from exc
    paragraphs = []
    for paragraph in root.iter(DOCX_PARAGRAPH):
        paragraphs.append("".join(node.text or "" for node in paragraph.iter(DOCX_TEXT)))
    return "\n".join(paragraphs)


def rtf_to_text(raw: str) -> str:
    out: list[str] = []
    index = 0
    length = len(raw)
    while index < length:
        char = raw[index]
        if char in "{}":
            index += 1
            continue
        if char != "\\":
            if char not in "\r\n":
                out.append(char)
            index += 1
            continue
        nxt = raw[index + 1] if index + 1 < length else ""
        if nxt in "\\{}":
            out.append(nxt)
            index += 2
            continue
        if nxt == "u" and index + 2 < length and raw[index + 2] in "-0123456789":
            index += 2
            sign = 1
            if raw[index] == "-":
                sign = -1
                index += 1
            number = 0
            while index < length and raw[index].isdigit():
                number = number * 10 + int(raw[index])
                index += 1
            code = sign * number
            if code < 0:
                code += 65536
            out.append(chr(code))
            if index < length and raw[index] not in "\\{}":
                index += 1
            continue
        word, index = _rtf_control_word(raw, index)
        if word in {"par", "line"}:
            out.append("\n")
    return "".join(out).strip("\n")


def _rtf_control_word(raw: str, index: int) -> tuple[str, int]:
    cursor = index + 1
    while cursor < len(raw) and raw[cursor].isalpha():
        cursor += 1
    word = raw[index + 1 : cursor]
    if cursor < len(raw) and raw[cursor] == "-":
        cursor += 1
    while cursor < len(raw) and raw[cursor].isdigit():
        cursor += 1
    if cursor < len(raw) and raw[cursor] == " ":
        cursor += 1
    return word, cursor


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
    parts.append("# GDD")
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
        lines.append(
            "WBS chỉ nhận CSV hoặc TSV. GDD nhận CSV, TSV, TXT, MD, DOCX hoặc RTF. "
            "File Excel, PDF, hoặc Word cũ (.doc) hãy export sang các định dạng đó."
        )
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
        "Cần ít nhất một file WBS và một file GDD.\n"
        "- WBS là CSV hoặc TSV, đặt trong thư mục `wbs/` hoặc tên file có token `wbs` "
        "(ví dụ `WBS_export.csv`).\n"
        "- GDD là CSV, TSV, TXT, MD, DOCX hoặc RTF, đặt trong thư mục `gdd/` "
        "hoặc tên file có token `gdd` (ví dụ `my-gdd.docx`, `GDD.txt`).\n\n"
        "File Excel, PDF, hoặc Word cũ (.doc) không được đọc. "
        "Hãy export WBS sang CSV hoặc TSV, và GDD sang DOCX hoặc TXT."
    )


def compose_report(body: str, root: Path, inventory: Inventory) -> str:
    skipped = skipped_section(root, inventory)
    text = body.strip()
    if skipped:
        text = f"{text}\n\n{skipped}"
    return f"{report_header()}\n\n{text}\n"


def report_header() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    pr_number = resolve_pr_number()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    lines = ["**Check WBS**"]
    if repo and pr_number:
        lines.append(f"Pull request: {server}/{repo}/pull/{pr_number}")
    elif repo and run_id:
        lines.append(f"Lần chạy: {server}/{repo}/actions/runs/{run_id}")
    return "\n".join(lines)


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


def is_discord_webhook(url: str) -> bool:
    prefixes = (
        "https://discord.com/api/webhooks/",
        "https://discordapp.com/api/webhooks/",
    )
    return url.startswith(prefixes) and " " not in url


def discord_chunks(text: str) -> list[str]:
    rest = text.strip()
    if not rest:
        rest = "(báo cáo trống)"
    pieces: list[str] = []
    while rest and len(pieces) < MAX_DISCORD_MESSAGES:
        if len(rest) <= DISCORD_BODY_LIMIT:
            pieces.append(rest)
            rest = ""
            break
        cut = rest.rfind("\n", 0, DISCORD_BODY_LIMIT)
        if cut < 400:
            cut = DISCORD_BODY_LIMIT
        pieces.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip("\n")
    if rest and pieces:
        note = "\n\nBáo cáo còn phần chưa gửi vì quá dài."
        room = DISCORD_BODY_LIMIT - len(note)
        pieces[-1] = pieces[-1][:room].rstrip() + note
    if len(pieces) <= 1:
        return pieces
    total = len(pieces)
    numbered: list[str] = []
    for index, piece in enumerate(pieces, start=1):
        prefix = f"({index}/{total})\n"
        numbered.append(prefix + piece[: DISCORD_BODY_LIMIT - len(prefix)])
    return numbered


def post_discord(webhook: str, text: str) -> None:
    if not is_discord_webhook(webhook):
        raise RuntimeError("DISCORD_WEBHOOK_URL không phải webhook Discord.")
    for chunk in discord_chunks(text):
        request = urllib.request.Request(
            webhook,
            data=json.dumps({"content": chunk}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "check-wbs",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Discord trả về HTTP {exc.code}: {detail}") from None


def publish(body: str, root: Path, inventory: Inventory) -> None:
    report = compose_report(body, root, inventory)
    write_summary(report)
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        raise RuntimeError("Thiếu secret DISCORD_WEBHOOK_URL. Không gửi Discord.")
    post_discord(webhook, report)


def call_gemini(api_key: str, model: str, user_prompt: str) -> str:
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
    if not model or any(char not in allowed for char in model):
        raise RuntimeError(f"Tên model Gemini không hợp lệ: {model}")
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    request = urllib.request.Request(
        GEMINI_URL.format(model=model),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"Gemini trả về HTTP {exc.code}: {detail}") from exc
    data = json.loads(raw)
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not candidates:
        raise RuntimeError("Gemini không trả về nội dung review.")
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    content = "".join(texts).strip()
    if not content:
        raise RuntimeError("Gemini trả về nội dung review rỗng.")
    return content


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

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        publish("Thiếu secret GEMINI_API_KEY. Không gọi Gemini.", root, inventory)
        return 1
    model = os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
    report = call_gemini(api_key, model, build_user_prompt(skill, root, inventory))
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
