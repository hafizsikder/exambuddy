from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
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
    "and",
    "are",
    "but",
    "because",
    "before",
    "being",
    "below",
    "between",
    "could",
    "during",
    "each",
    "for",
    "from",
    "have",
    "has",
    "how",
    "its",
    "into",
    "is",
    "inside",
    "not",
    "of",
    "on",
    "or",
    "more",
    "most",
    "other",
    "over",
    "should",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "they",
    "this",
    "through",
    "to",
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

BOUNDARY_WORDS = STOP_WORDS | {
    "absorbs",
    "allows",
    "can",
    "causes",
    "convert",
    "converts",
    "create",
    "creates",
    "describe",
    "describes",
    "explain",
    "explains",
    "include",
    "includes",
    "make",
    "makes",
    "mean",
    "means",
    "provide",
    "provides",
    "show",
    "shows",
    "support",
    "supports",
    "use",
    "used",
}

WEAK_SINGLE_WORDS = {
    "application",
    "cells",
    "concept",
    "concepts",
    "definition",
    "energy",
    "example",
    "growth",
    "idea",
    "ideas",
    "material",
    "method",
    "notes",
    "process",
    "production",
    "purpose",
    "release",
    "source",
    "study",
    "system",
    "term",
    "terms",
    "thing",
    "things",
    "topic",
    "topics",
}

ACRONYMS = {"atp", "dna", "rna", "html", "css", "api", "cpu", "gpu", "pdf"}


@dataclass(frozen=True)
class KeyConcept:
    title: str
    explanation: str
    source_sentence: str


@dataclass(frozen=True)
class ParsedContent:
    title: str
    source_type: str
    text: str
    concepts: list[str]
    concept_details: list[KeyConcept] = field(default_factory=list)


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
    concept_details = extract_key_concept_details(text)
    return ParsedContent(
        title=title,
        source_type="text",
        text=text,
        concepts=[concept.title for concept in concept_details],
        concept_details=concept_details,
    )


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
    concept_details = extract_key_concept_details(text)
    return ParsedContent(
        title=file_path.name,
        source_type=source_type,
        text=text,
        concepts=[concept.title for concept in concept_details],
        concept_details=concept_details,
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
    concept_details = extract_key_concept_details(text)
    return ParsedContent(
        title=title,
        source_type="web",
        text=text,
        concepts=[concept.title for concept in concept_details],
        concept_details=concept_details,
    )


def extract_key_concepts(text: str, minimum: int = 5, maximum: int = 24) -> list[str]:
    return [concept.title for concept in extract_key_concept_details(text, minimum=minimum, maximum=maximum)]


def extract_key_concept_details(text: str, minimum: int = 5, maximum: int = 24) -> list[KeyConcept]:
    cleaned_text = _clean_text(text)
    cleaned = cleaned_text.lower()
    if not cleaned:
        return []

    sentences = _split_sentences(cleaned_text)
    if not sentences:
        return []

    all_words: list[str] = []
    candidate_sentence: dict[str, str] = {}
    first_seen: dict[str, int] = {}
    candidates: dict[str, float] = {}

    for sentence in sentences:
        words = re.findall(r"[a-z][a-z0-9'-]{1,}", sentence.lower())
        words = [word for word in words if not word.isdigit()]
        all_words.extend(word for word in words if word not in STOP_WORDS)

    if not all_words:
        return []

    word_counts = Counter(all_words)

    for sentence_index, sentence in enumerate(sentences):
        fragments = re.split(r"[,;:()]|\b(?:and|or)\b", sentence, flags=re.IGNORECASE)
        for fragment in fragments:
            words = re.findall(r"[a-z][a-z0-9'-]{1,}", fragment.lower())
            segments: list[list[str]] = []
            current: list[str] = []
            for word in words:
                if word in BOUNDARY_WORDS:
                    if current:
                        segments.append(current)
                        current = []
                    continue
                current.append(word)
            if current:
                segments.append(current)

            for segment in segments:
                _add_candidates_from_segment(segment, sentence_index, sentences, word_counts, first_seen, candidate_sentence, candidates)

    ranked = sorted(candidates, key=lambda item: (-candidates[item], first_seen[item], item))
    multiword_candidate_parts = {
        part
        for candidate in ranked
        if len(candidate.split()) > 1
        for part in candidate.split()
    }
    selected: list[str] = []
    for candidate in ranked:
        if len(candidate.split()) == 1 and candidate in multiword_candidate_parts:
            continue
        if _is_redundant(candidate, selected):
            continue
        selected.append(candidate)
        if len(selected) >= maximum:
            break

    if len(selected) < minimum:
        fallback_words = [
            word
            for word in sorted(word_counts, key=lambda item: (-word_counts[item], item))
            if _valid_candidate([word]) and word not in selected
        ]
        for word in fallback_words:
            selected.append(word)
            if len(selected) >= min(minimum, maximum):
                break

    return [
        KeyConcept(
            title=_format_concept_title(candidate),
            explanation=_build_explanation(candidate, candidate_sentence.get(candidate, "")),
            source_sentence=candidate_sentence.get(candidate, ""),
        )
        for candidate in selected[:maximum]
    ]


def _add_candidates_from_segment(
    segment: list[str],
    sentence_index: int,
    sentences: list[str],
    word_counts: Counter[str],
    first_seen: dict[str, int],
    candidate_sentence: dict[str, str],
    candidates: dict[str, float],
) -> None:
    for start in range(len(segment)):
        for size in range(1, min(4, len(segment) - start) + 1):
            parts = segment[start : start + size]
            if not _valid_candidate(parts):
                continue
            key = " ".join(parts)
            first_seen.setdefault(key, len(first_seen))
            candidate_sentence.setdefault(key, sentences[sentence_index])
            score = _candidate_score(parts, word_counts, start == 0)
            candidates[key] = candidates[key] + 3 if key in candidates else score


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


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if len(sentence.strip()) >= 8
    ]


def _valid_candidate(parts: list[str]) -> bool:
    if not parts or len(set(parts)) != len(parts):
        return False
    if any(part in STOP_WORDS for part in parts):
        return False
    if len(parts) == 1:
        word = parts[0]
        return word not in WEAK_SINGLE_WORDS and len(word) >= 4
    if parts[0] in WEAK_SINGLE_WORDS:
        return False
    return not all(part in WEAK_SINGLE_WORDS for part in parts)


def _candidate_score(parts: list[str], word_counts: Counter[str], starts_segment: bool) -> float:
    if len(parts) == 1:
        word = parts[0]
        return word_counts[word] * 12 + min(len(word), 18) / 2 + (8 if starts_segment else 0)

    repeated_word_bonus = sum(2 for word in parts if word_counts[word] > 1)
    acronym_bonus = 4 if any(word in ACRONYMS for word in parts) else 0
    return 16 + len(parts) * 5 + repeated_word_bonus + acronym_bonus + (4 if starts_segment else 0)


def _is_redundant(candidate: str, selected: list[str]) -> bool:
    candidate_parts = set(candidate.split())
    for existing in selected:
        existing_parts = set(existing.split())
        if candidate_parts == existing_parts:
            return True
        if len(candidate_parts) == 1 and candidate_parts.issubset(existing_parts):
            return True
    return False


def _format_concept_title(candidate: str) -> str:
    return " ".join(word.upper() if word in ACRONYMS else word for word in candidate.split())


def _build_explanation(candidate: str, sentence: str) -> str:
    title = _format_concept_title(candidate)
    if sentence:
        return f"{title}: {sentence.rstrip('.!?')}."
    return f"{title}: review this concept in the source material."
