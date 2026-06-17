from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen


STOP_WORDS = {
    "about",
    "above",
    "after",
    "again",
    "against",
    "also",
    "because",
    "before",
    "being",
    "below",
    "between",
    "could",
    "during",
    "each",
    "from",
    "have",
    "into",
    "inside",
    "more",
    "most",
    "other",
    "over",
    "should",
    "some",
    "such",
    "than",
    "that",
    "their",
    "then",
    "there",
    "these",
    "they",
    "this",
    "through",
    "under",
    "uses",
    "using",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
}


@dataclass(frozen=True)
class ParsedContent:
    title: str
    source_type: str
    text: str
    concepts: list[str]


class ParseError(RuntimeError):
    """Raised when a source cannot be parsed into usable study text."""


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self._parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "br", "li", "div", "section", "article", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        if self._in_title:
            self.title = f"{self.title} {clean}".strip()
        self._parts.append(clean)

    @property
    def text(self) -> str:
        return "\n".join(part for part in self._parts if part.strip())


def parse_text(raw_text: str, title: str = "Pasted text") -> ParsedContent:
    text = _clean_text(raw_text)
    if not text:
        raise ParseError("No readable text was found.")
    return ParsedContent(title=title, source_type="text", text=text, concepts=extract_key_concepts(text))


def parse_file(path: str | Path) -> ParsedContent:
    file_path = Path(path)
    if not file_path.exists():
        raise ParseError(f"File not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(file_path)
        source_type = "pdf"
    elif suffix == ".pptx":
        text = _extract_pptx_text(file_path)
        source_type = "pptx"
    elif suffix in {".txt", ".md"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        source_type = "text"
    else:
        raise ParseError("Supported files are PDF, PPTX, TXT, and MD.")

    text = _clean_text(text)
    if not text:
        raise ParseError("No readable text was found in the selected file.")
    return ParsedContent(
        title=file_path.name,
        source_type=source_type,
        text=text,
        concepts=extract_key_concepts(text),
    )


def parse_url(url: str, timeout: int = 15) -> ParsedContent:
    if not url.lower().startswith(("http://", "https://")):
        raise ParseError("Enter a full http:// or https:// web link.")

    request = Request(url, headers={"User-Agent": "ExamBuddy/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read(2_000_000)
    except Exception as exc:  # pragma: no cover - network failures vary by platform
        raise ParseError(f"Could not fetch the web link: {exc}") from exc

    if "html" not in content_type and b"<html" not in payload[:500].lower():
        text = payload.decode(charset, errors="ignore")
        title = url
    else:
        parser = _HTMLTextParser()
        parser.feed(payload.decode(charset, errors="ignore"))
        text = parser.text
        title = parser.title or url

    text = _clean_text(text)
    if not text:
        raise ParseError("No readable text was found at the web link.")
    return ParsedContent(title=title, source_type="web", text=text, concepts=extract_key_concepts(text))


def extract_key_concepts(text: str, minimum: int = 5, maximum: int = 24) -> list[str]:
    cleaned = _clean_text(text).lower()
    if not cleaned:
        return []

    words = [
        word
        for word in re.findall(r"[a-z][a-z0-9'-]{2,}", cleaned)
        if word not in STOP_WORDS and not word.isdigit()
    ]
    if not words:
        return []

    word_counts = Counter(words)
    first_seen: dict[str, int] = {}
    for index, word in enumerate(words):
        first_seen.setdefault(word, index)

    candidates: dict[str, float] = {}
    for word, count in word_counts.items():
        candidates[word] = count * 10 + min(len(word), 16) / 4

    phrase_counts: Counter[str] = Counter()
    for size in (2, 3):
        for index in range(len(words) - size + 1):
            phrase_words = words[index : index + size]
            if len(set(phrase_words)) == 1:
                continue
            phrase = " ".join(phrase_words)
            phrase_counts[phrase] += 1
            first_seen.setdefault(phrase, index)

    for phrase, count in phrase_counts.items():
        phrase_score = count * 7 + len(phrase.split()) * 2
        if count > 1 or any(word_counts[word] > 1 for word in phrase.split()):
            candidates[phrase] = phrase_score

    ranked = sorted(candidates, key=lambda item: (-candidates[item], first_seen[item], item))
    results: list[str] = []
    used_words: set[str] = set()
    for candidate in ranked:
        parts = candidate.split()
        if len(parts) > 1 and any(part in used_words for part in parts):
            continue
        results.append(candidate)
        used_words.update(parts)
        if len(results) >= maximum:
            break

    if len(results) < minimum:
        for word in sorted(word_counts, key=lambda item: (-word_counts[item], first_seen[item], item)):
            if word not in results:
                results.append(word)
            if len(results) >= min(minimum, maximum):
                break

    return results[:maximum]


def _extract_pdf_text(path: Path) -> str:
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader  # type: ignore
    except ImportError as exc:
        raise ParseError("PDF parsing requires pypdf. Install it with: pip install -r requirements.txt") from exc

    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ParseError(f"Could not parse PDF: {exc}") from exc


def _extract_pptx_text(path: Path) -> str:
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise ParseError("PPTX parsing requires python-pptx. Install it with: pip install -r requirements.txt") from exc

    try:
        presentation = Presentation(str(path))
        chunks: list[str] = []
        for slide_number, slide in enumerate(presentation.slides, start=1):
            chunks.append(f"Slide {slide_number}")
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    chunks.append(shape.text)
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        chunks.append(" ".join(cell.text for cell in row.cells))
        return "\n".join(chunks)
    except Exception as exc:
        raise ParseError(f"Could not parse PPTX: {exc}") from exc


def _clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
