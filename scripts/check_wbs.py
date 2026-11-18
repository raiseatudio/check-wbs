"""Đọc WBS và GDD, gọi Gemini theo skill_check_wbs.md, rồi gửi báo cáo vào Discord."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
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
GEMINI_MODELS = (
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)
RETRYABLE_GEMINI_STATUS = {404, 429, 500, 502, 503, 504}
WBS_TABLE_EXT = {".csv", ".tsv"}
WBS_UNSUPPORTED_EXT = {".xlsx", ".xls", ".xlsm", ".ods"}
GDD_TEXT_EXT = {".txt", ".text", ".md", ".markdown", ".docx", ".rtf"}
GDD_UNSUPPORTED_EXT = WBS_UNSUPPORTED_EXT | {".doc", ".pdf"}
SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".venv", "venv"}
DOCX_PARAGRAPH = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
DOCX_TEXT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
SYSTEM_PROMPT = (
    "Bạn là người review WBS. Tuân thủ đúng skill_check_wbs.md trong phần người dùng. "
    "Trả lời bằng tiếng Việt, đúng khuôn báo cáo trong skill_check_wbs.md. "
    "Không thêm luật nghiệp vụ ngoài skill_check_wbs.md. "
    "Không bịa nội dung không có trong file được gửi."
)
SYSTEM_PROMPT_GDD = (
    "Bạn là người review GDD. Tuân thủ đúng skill_check_gdd.md trong phần người dùng. "
    "Trả lời bằng tiếng Việt, đúng khuôn báo cáo trong skill_check_gdd.md. "
    "Không thêm luật nghiệp vụ ngoài skill_check_gdd.md. "
    "Không bịa ô hoặc câu không có trong nội dung được gửi."
)
TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
COMMIT_MARKER = re.compile(r"\[(check-wbs|check-gdd|check)\]")
SHEET_LABEL_URL = re.compile(
    r"(?i)(?<![A-Za-z0-9])(wbs|gdd)\s*[:=]\s*"
    r"(https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]+[^\s]*)"
)
GAME_LABEL = re.compile(r"(?i)(?<![A-Za-z0-9])game\s*[:=]\s*([A-Za-z0-9_-]+)")
GAME_CODE = re.compile(r"\bgsc\d+\b", re.IGNORECASE)
BRACKET_NAME = re.compile(r"\[([^\[\]]+)\]")
WBS_URL_HELP = (
    "Commit [check-wbs] cần cả hai URL Google Sheet có nhãn.\n"
    "Ví dụ: [check-wbs] wbs: https://docs.google.com/spreadsheets/d/.../edit#gid=0 "
    "gdd: https://docs.google.com/spreadsheets/d/.../edit#gid=0"
)
GDD_URL_HELP = (
    "Commit [check-gdd] cần một URL Google Sheet có nhãn gdd:.\n"
    "Ví dụ: [check-gdd] gdd: https://docs.google.com/spreadsheets/d/.../edit#gid=0"
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


EMPTY_INVENTORY = Inventory([], [], [], [])


@dataclass(frozen=True)
class SheetLink:
    url: str
    spreadsheet_id: str
    gid: str | None


@dataclass(frozen=True)
class CommitRequest:
    files: bool
    wbs: bool
    gdd: bool
    wbs_link: SheetLink | None
    wbs_gdd_link: SheetLink | None
    gdd_link: SheetLink | None
    wbs_error: str
    gdd_error: str

    @property
    def requested(self) -> bool:
        return self.files or self.wbs or self.gdd


@dataclass(frozen=True)
class SourceDoc:
    name: str
    kind: str
    text: str
    line_count: int
    truncated: bool


@dataclass(frozen=True)
class SheetBundle:
    spreadsheet_title: str
    docs: list[SourceDoc]


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


def limit_text(text: str) -> tuple[str, int, bool]:
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


def read_limited(path: Path) -> tuple[str, int, bool]:
    return limit_text(extract_text(path))


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


def source_from_path(root: Path, path: Path, kind: str) -> SourceDoc:
    text, line_count, truncated = read_limited(path)
    return SourceDoc(path.relative_to(root).as_posix(), kind, text, line_count, truncated)


def render_source(doc: SourceDoc) -> str:
    label = "WBS" if doc.kind == "wbs" else "GDD"
    note = f"{doc.line_count} dòng"
    if doc.truncated:
        note += f", nội dung đã cắt còn {MAX_CHARS} ký tự"
    fence = fence_for(doc.text)
    return f"## `{doc.name}` ({label}, {note})\n\n{fence}\n{doc.text}\n{fence}\n"


def prompt_from_sources(
    skill_heading: str,
    skill: str,
    sections: list[tuple[str, list[SourceDoc]]],
    closing: str,
) -> str:
    parts = [f"# {skill_heading}", "", skill.strip(), ""]
    for heading, docs in sections:
        parts.append(f"# {heading}")
        parts.append("")
        for doc in docs:
            parts.append(render_source(doc))
    parts.append(closing)
    return "\n".join(parts)


def build_user_prompt(skill: str, root: Path, inventory: Inventory) -> str:
    wbs_docs = [source_from_path(root, path, "wbs") for path in inventory.wbs]
    gdd_docs = [source_from_path(root, path, "gdd") for path in inventory.gdd]
    return prompt_from_sources(
        "skill_check_wbs.md",
        skill,
        [("Bảng WBS", wbs_docs), ("GDD", gdd_docs)],
        "Hãy viết báo cáo theo đúng khuôn trong skill_check_wbs.md.",
    )


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


def game_id_in(text: str) -> str:
    if not text:
        return ""
    labeled = GAME_LABEL.search(text)
    if labeled:
        return labeled.group(1)
    code = GAME_CODE.search(text)
    if code:
        return code.group(0)
    for match in BRACKET_NAME.finditer(text):
        inside = match.group(1).strip()
        if inside.lower() in {"check", "check-wbs", "check-gdd"}:
            continue
        if not re.fullmatch(r"[A-Za-z0-9]+(?:\s*-\s*[A-Za-z0-9]+)?", inside):
            continue
        parts = [part.strip() for part in re.split(r"\s*-\s*", inside) if part.strip()]
        for part in parts:
            if any(char.isdigit() for char in part):
                return part
        if parts:
            return parts[-1]
    return ""


def find_game_id(*texts: str) -> str:
    for text in texts:
        found = game_id_in(text)
        if found:
            return found
    return ""


def inventory_game_id(inventory: Inventory) -> str:
    names = [
        path.as_posix()
        for path in (
            *inventory.wbs,
            *inventory.gdd,
            *inventory.ambiguous,
            *inventory.unsupported,
        )
    ]
    return find_game_id(current_commit_message(), *names)


def compose_report(
    body: str,
    root: Path,
    inventory: Inventory,
    title: str = "Check WBS",
    game_id: str = "",
) -> str:
    skipped = skipped_section(root, inventory)
    text = body.strip()
    if skipped:
        text = f"{text}\n\n{skipped}"
    return f"{report_header(title, game_id)}\n\n{text}\n"


def report_header(title: str = "Check WBS", game_id: str = "") -> str:
    if game_id:
        return f"[{title} - {game_id}]"
    return f"[{title}]"


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


def publish(
    body: str,
    root: Path,
    inventory: Inventory,
    title: str = "Check WBS",
    game_id: str = "",
) -> None:
    if not game_id:
        game_id = find_game_id(current_commit_message())
    report = compose_report(body, root, inventory, title, game_id)
    write_summary(report)
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        raise RuntimeError("Thiếu secret DISCORD_WEBHOOK_URL. Không gửi Discord.")
    post_discord(webhook, report)


class GeminiHTTPError(RuntimeError):
    def __init__(self, status: int, detail: str, retryable: bool):
        super().__init__(f"Gemini trả về HTTP {status}: {detail}")
        self.status = status
        self.retryable = retryable


def call_gemini(
    api_key: str,
    model: str,
    user_prompt: str,
    system_prompt: str = SYSTEM_PROMPT,
) -> str:
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
    if not model or any(char not in allowed for char in model):
        raise RuntimeError(f"Tên model Gemini không hợp lệ: {model}")
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
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
        raise GeminiHTTPError(exc.code, detail, exc.code in RETRYABLE_GEMINI_STATUS) from None
    data = json.loads(raw)
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not candidates:
        raise GeminiHTTPError(503, "không trả về nội dung review.", True)
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    content = "".join(texts).strip()
    if not content:
        raise GeminiHTTPError(503, "nội dung review rỗng.", True)
    return content


def gemini_model_order() -> list[str]:
    models: list[str] = []
    pinned = os.environ.get("GEMINI_MODEL", "").strip()
    if pinned:
        models.append(pinned)
    for model in GEMINI_MODELS:
        if model not in models:
            models.append(model)
    return models


def review_with_gemini(
    api_key: str,
    user_prompt: str,
    system_prompt: str = SYSTEM_PROMPT,
) -> str:
    errors: list[str] = []
    models = gemini_model_order()
    for index, model in enumerate(models):
        try:
            report = call_gemini(api_key, model, user_prompt, system_prompt)
        except GeminiHTTPError as exc:
            errors.append(f"{model}: {exc}")
            print(f"Gemini {model} không dùng được: {exc}", file=sys.stderr)
            if not exc.retryable:
                raise
            continue
        except urllib.error.URLError as exc:
            errors.append(f"{model}: không kết nối được ({exc.reason})")
            print(f"Gemini {model} không kết nối được: {exc.reason}", file=sys.stderr)
            continue
        if index == 0:
            return report
        skipped = ", ".join(models[:index])
        return f"Đã dùng Gemini `{model}` vì model cao hơn không phản hồi ({skipped}).\n\n{report}"
    joined = "; ".join(errors)
    raise RuntimeError(f"Gemini không gọi được với các model đã thử. {joined}")


def parse_sheet_url(raw: str) -> SheetLink:
    cleaned = raw.strip().rstrip(".,);>\"'")
    parsed = urllib.parse.urlparse(cleaned)
    parts = [part for part in parsed.path.split("/") if part]
    try:
        spreadsheet_id = parts[parts.index("d") + 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("URL Google Sheet không có spreadsheet id.") from exc
    allowed_id = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    if not spreadsheet_id or any(char not in allowed_id for char in spreadsheet_id):
        raise ValueError("URL Google Sheet không có spreadsheet id.")
    query_gid = urllib.parse.parse_qs(parsed.query).get("gid", [])
    fragment_gid = urllib.parse.parse_qs(parsed.fragment).get("gid", [])
    gid = fragment_gid[0] if fragment_gid else (query_gid[0] if query_gid else None)
    if gid is not None and not gid.isdigit():
        gid = None
    return SheetLink(cleaned, spreadsheet_id, gid)


def labeled_links(body: str) -> tuple[dict[str, SheetLink], str]:
    found: dict[str, list[SheetLink]] = {"wbs": [], "gdd": []}
    for match in SHEET_LABEL_URL.finditer(body):
        label = match.group(1).lower()
        try:
            link = parse_sheet_url(match.group(2))
        except ValueError:
            return {}, "URL Google Sheet không đúng dạng docs.google.com/spreadsheets/d/..."
        found[label].append(link)
    picked: dict[str, SheetLink] = {}
    for label, links in found.items():
        if len(links) > 1:
            return {}, f"Nhãn {label}: chỉ được một URL."
        if links:
            picked[label] = links[0]
    return picked, ""


def parse_commit_message(message: str) -> CommitRequest:
    matches = list(COMMIT_MARKER.finditer(message))
    files = False
    wbs = False
    gdd = False
    wbs_link = None
    wbs_gdd_link = None
    gdd_link = None
    wbs_error = ""
    gdd_error = ""
    for index, match in enumerate(matches):
        kind = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(message)
        body = message[match.end() : end]
        if kind == "check":
            files = True
            continue
        links, error = labeled_links(body)
        if kind == "check-wbs":
            if wbs:
                wbs_error = "Commit có hơn một lệnh [check-wbs]."
                wbs_link = None
                wbs_gdd_link = None
                continue
            wbs = True
            if error:
                wbs_error = error
            elif "wbs" not in links or "gdd" not in links:
                wbs_error = WBS_URL_HELP
            else:
                wbs_link = links["wbs"]
                wbs_gdd_link = links["gdd"]
            continue
        if gdd:
            gdd_error = "Commit có hơn một lệnh [check-gdd]."
            gdd_link = None
            continue
        gdd = True
        if error:
            gdd_error = error
        elif "gdd" not in links:
            gdd_error = GDD_URL_HELP
        else:
            gdd_link = links["gdd"]
    return CommitRequest(
        files,
        wbs,
        gdd,
        wbs_link,
        wbs_gdd_link,
        gdd_link,
        wbs_error,
        gdd_error,
    )


def current_commit_message() -> str:
    if "COMMIT_MESSAGE" in os.environ:
        return os.environ["COMMIT_MESSAGE"]
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return result.stdout


def write_gate(message: str) -> CommitRequest:
    request = parse_commit_message(message)
    values = {
        "run": "true" if request.requested else "false",
        "files": "true" if request.files else "false",
        "wbs": "true" if request.wbs else "false",
        "gdd": "true" if request.gdd else "false",
    }
    lines = [f"{key}={value}" for key, value in values.items()]
    path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))
    if not request.requested:
        write_summary(
            "Commit mới nhất không chứa [check], [check-wbs] hoặc [check-gdd]. "
            "Bỏ qua test và review."
        )
    return request


def oauth_refresh_form(client_id: str, client_secret: str, refresh_token: str) -> str:
    return urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    )


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    request = urllib.request.Request(
        TOKEN_URL,
        data=oauth_refresh_form(client_id, client_secret, refresh_token).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "check-wbs",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            "Google từ chối refresh token. Đăng nhập lại bằng scripts/google_login.py. "
            "Nếu app OAuth còn ở chế độ Testing thì token hết hạn sau 7 ngày. "
            f"(HTTP {exc.code})"
        ) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Không kết nối được Google để làm mới token ({exc.reason}).") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise RuntimeError(
            "Google từ chối refresh token. Đăng nhập lại bằng scripts/google_login.py. "
            "Nếu app OAuth còn ở chế độ Testing thì token hết hạn sau 7 ngày."
        )
    return payload["access_token"]


def access_token_from_env() -> str:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", "").strip()
    if not client_id or not client_secret or not refresh_token:
        raise RuntimeError(
            "Thiếu secret GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET "
            "hoặc GOOGLE_OAUTH_REFRESH_TOKEN."
        )
    return refresh_access_token(client_id, client_secret, refresh_token)


def google_json(url: str, access_token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "check-wbs",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise RuntimeError("Tài khoản Google không có quyền xem sheet này.") from None
        if exc.code == 404:
            raise RuntimeError(
                "Không đọc được Google Sheet. Kiểm tra URL và quyền của tài khoản đã đăng nhập."
            ) from None
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Google Sheets trả về HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Không kết nối được Google Sheets ({exc.reason}).") from None
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Google Sheets trả về dữ liệu không đọc được.")
    return data


def rows_to_csv(rows: list) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    normalized: list[list[str]] = []
    width = 0
    for row in rows:
        if not isinstance(row, list):
            continue
        cells = ["" if cell is None else str(cell) for cell in row]
        width = max(width, len(cells))
        normalized.append(cells)
    for cells in normalized:
        if len(cells) < width:
            cells = cells + [""] * (width - len(cells))
        writer.writerow(cells)
    return buffer.getvalue()


def sheet_range(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def fetch_sheet_docs(access_token: str, link: SheetLink, kind: str) -> SheetBundle:
    meta_url = (
        f"{SHEETS_API}/{urllib.parse.quote(link.spreadsheet_id, safe='')}"
        + "?"
        + urllib.parse.urlencode(
            {"fields": "properties.title,sheets.properties(sheetId,title)"}
        )
    )
    meta = google_json(meta_url, access_token)
    properties = meta.get("properties")
    spreadsheet_title = ""
    if isinstance(properties, dict) and isinstance(properties.get("title"), str):
        spreadsheet_title = properties["title"]
    sheets = meta.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        raise RuntimeError("Google Sheet không có tab nào.")
    chosen: list[str] = []
    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        props = sheet.get("properties")
        if not isinstance(props, dict):
            continue
        title = props.get("title")
        sheet_id = props.get("sheetId")
        if not isinstance(title, str) or not isinstance(sheet_id, int):
            continue
        if link.gid is None or str(sheet_id) == link.gid:
            chosen.append(title)
    if not chosen:
        raise RuntimeError(f"Không thấy tab gid={link.gid} trong Google Sheet.")
    docs: list[SourceDoc] = []
    for title in chosen:
        values_url = (
            f"{SHEETS_API}/{urllib.parse.quote(link.spreadsheet_id, safe='')}/values/"
            + urllib.parse.quote(sheet_range(title), safe="")
        )
        payload = google_json(values_url, access_token)
        rows = payload.get("values", [])
        if not isinstance(rows, list):
            rows = []
        text, line_count, truncated = limit_text(rows_to_csv(rows))
        docs.append(SourceDoc(f"{link.spreadsheet_id}/{title}", kind, text, line_count, truncated))
    return SheetBundle(spreadsheet_title, docs)


def repo_root() -> Path:
    workspace = os.environ.get("GITHUB_WORKSPACE", "").strip()
    if workspace:
        return Path(workspace)
    return Path.cwd()


def read_skill_file(root: Path, filename: str) -> tuple[str, str]:
    path = root / filename
    if not path.is_file():
        return "", (
            f"Thiếu {filename} ở thư mục gốc của repo. Action cần file này làm bộ luật review."
        )
    skill = path.read_text(encoding="utf-8-sig", errors="replace").strip()
    if not skill:
        return "", f"{filename} đang trống. Hãy điền bộ luật review trước khi chạy."
    return skill, ""


def require_gemini() -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Thiếu secret GEMINI_API_KEY. Không gọi Gemini.")
    return api_key


def review_files() -> int:
    root = repo_root()
    inventory = collect(root)
    if not inventory.wbs or not inventory.gdd:
        publish(guidance(inventory), root, inventory, title="Check WBS", game_id=inventory_game_id(inventory))
        return 0
    skill, error = read_skill_file(root, "skill_check_wbs.md")
    if error:
        publish(error, root, inventory, title="Check WBS", game_id=inventory_game_id(inventory))
        return 1
    report = review_with_gemini(
        require_gemini(),
        build_user_prompt(skill, root, inventory),
        SYSTEM_PROMPT,
    )
    publish(report, root, inventory, title="Check WBS", game_id=inventory_game_id(inventory))
    return 0


def review_wbs_sheet(request: CommitRequest) -> int:
    root = repo_root()
    if request.wbs_error or request.wbs_link is None or request.wbs_gdd_link is None:
        publish(request.wbs_error or WBS_URL_HELP, root, EMPTY_INVENTORY, title="Check WBS")
        return 1
    skill, error = read_skill_file(root, "skill_check_wbs.md")
    if error:
        publish(error, root, EMPTY_INVENTORY, title="Check WBS")
        return 1
    api_key = require_gemini()
    access_token = access_token_from_env()
    wbs_sheet = fetch_sheet_docs(access_token, request.wbs_link, "wbs")
    gdd_sheet = fetch_sheet_docs(access_token, request.wbs_gdd_link, "gdd")
    prompt = prompt_from_sources(
        "skill_check_wbs.md",
        skill,
        [("Bảng WBS", wbs_sheet.docs), ("GDD", gdd_sheet.docs)],
        "Hãy viết báo cáo theo đúng khuôn trong skill_check_wbs.md.",
    )
    report = review_with_gemini(api_key, prompt, SYSTEM_PROMPT)
    publish(
        report,
        root,
        EMPTY_INVENTORY,
        title="Check WBS",
        game_id=find_game_id(
            current_commit_message(),
            wbs_sheet.spreadsheet_title,
            gdd_sheet.spreadsheet_title,
        ),
    )
    return 0


def review_gdd_sheet(request: CommitRequest) -> int:
    root = repo_root()
    if request.gdd_error or request.gdd_link is None:
        publish(request.gdd_error or GDD_URL_HELP, root, EMPTY_INVENTORY, title="Check GDD")
        return 1
    skill, error = read_skill_file(root, "skill_check_gdd.md")
    if error:
        publish(error, root, EMPTY_INVENTORY, title="Check GDD")
        return 1
    api_key = require_gemini()
    access_token = access_token_from_env()
    gdd_sheet = fetch_sheet_docs(access_token, request.gdd_link, "gdd")
    prompt = prompt_from_sources(
        "skill_check_gdd.md",
        skill,
        [("GDD", gdd_sheet.docs)],
        "Hãy viết báo cáo theo đúng khuôn trong skill_check_gdd.md.",
    )
    report = review_with_gemini(api_key, prompt, SYSTEM_PROMPT_GDD)
    publish(
        report,
        root,
        EMPTY_INVENTORY,
        title="Check GDD",
        game_id=find_game_id(current_commit_message(), gdd_sheet.spreadsheet_title),
    )
    return 0


def execute_check(label: str, action) -> int:
    try:
        return action()
    except Exception as exc:
        message = f"{label} thất bại: {exc}"
        print(message, file=sys.stderr)
        try:
            title = "Check GDD" if label.endswith("GDD") else "Check WBS"
            publish(message, repo_root(), EMPTY_INVENTORY, title=title)
        except Exception as publish_error:
            print(f"Không ghi được báo cáo: {publish_error}", file=sys.stderr)
        return 1


def run() -> int:
    request = parse_commit_message(current_commit_message())
    if not request.requested:
        if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
            return 0
        return review_files()
    status = 0
    if request.files:
        status = max(status, execute_check("Kiểm tra WBS", review_files))
    if request.wbs:
        status = max(status, execute_check("Kiểm tra WBS", lambda: review_wbs_sheet(request)))
    if request.gdd:
        status = max(status, execute_check("Kiểm tra GDD", lambda: review_gdd_sheet(request)))
    return status


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if "--gate" in args:
            write_gate(current_commit_message())
            return 0
        return run()
    except Exception as exc:
        message = f"Kiểm tra thất bại: {exc}"
        print(message, file=sys.stderr)
        try:
            publish(message, repo_root(), EMPTY_INVENTORY, title="Check WBS")
        except Exception as publish_error:
            print(f"Không ghi được báo cáo: {publish_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
