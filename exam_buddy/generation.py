from __future__ import annotations

from dataclasses import dataclass
import json
import os
import random
import re
from typing import Any, TypeVar

from .models import Flashcard, PracticeQuestion, QuizQuestion, StudySet


QUESTION_TYPES = ("mcq", "fill_in", "rearrange", "math_problem")
T = TypeVar("T")


@dataclass(frozen=True)
class ConceptRecord:
    title: str
    explanation: str = ""
    source_sentence: str = ""
    items: tuple[str, ...] = ()
    block_type: str = "concept"


class LocalStudyGenerator:
    """Deterministic fallback generator that never calls the network."""

    def generate(
        self,
        concepts: list[Any],
        card_count: int = 10,
        quiz_count: int = 12,
        source_text: str = "",
    ) -> StudySet:
        concept_records = _prepare_concept_records(concepts, source_text)
        concept_titles = [concept.title for concept in concept_records]
        flashcard_total = _clamp(card_count, 5, max(5, len(concept_records)))
        quiz_total = _clamp(quiz_count, 10, 15)

        flashcards = [
            Flashcard(
                question=f"What does {concept.title} mean in this material?",
                answer=_compose_flashcard_answer(concept),
                concept=concept.title,
            )
            for concept in _cycle_take(concept_records, flashcard_total)
        ]

        practice_questions = [
            PracticeQuestion(
                prompt=_compose_practice_prompt(concept),
                answer=concept.title,
                concept=concept.title,
            )
            for concept in _cycle_take(concept_records, max(5, min(len(concept_records), 12)))
        ]

        quiz_questions = [
            self._build_quiz_question(index, concept, concept_titles)
            for index, concept in enumerate(_cycle_take(concept_records, quiz_total))
        ]

        return StudySet(flashcards, practice_questions, quiz_questions)

    def _build_quiz_question(self, index: int, concept: ConceptRecord, concepts: list[str]) -> QuizQuestion:
        question_type = QUESTION_TYPES[index % len(QUESTION_TYPES)]
        timer_seconds = 20 + (index % 5) * 10

        if question_type == "mcq":
            options = _make_options(concept.title, concepts, seed=index)
            clue = concept.source_sentence or concept.explanation or concept.title
            return QuizQuestion(
                prompt=f"Which concept is described by this source clue: {clue}",
                answer=concept.title,
                question_type=question_type,
                timer_seconds=timer_seconds,
                options=options,
            )

        if question_type == "fill_in":
            prompt = _fill_in_prompt(concept)
            return QuizQuestion(
                prompt=prompt,
                answer=concept.title,
                question_type=question_type,
                timer_seconds=timer_seconds,
            )

        if question_type == "rearrange":
            phrase = _rearrange_phrase(concept.title)
            scrambled = " / ".join(reversed(phrase.split()))
            return QuizQuestion(
                prompt=f"Rearrange these words into the correct phrase: {scrambled}",
                answer=phrase,
                question_type=question_type,
                timer_seconds=timer_seconds,
            )

        minutes_each = 5 + index
        concept_count = min(len(concepts), 6)
        return QuizQuestion(
            prompt=(
                f"Math problem: If you spend {minutes_each} minutes reviewing each of "
                f"{concept_count} concepts, how many minutes is that in total?"
            ),
            answer=str(minutes_each * concept_count),
            question_type="math_problem",
            timer_seconds=timer_seconds,
        )


class OpenAIStudyGenerator:
    """Optional generator that uses OpenAI only when credentials are configured."""

    def __init__(self, fallback: LocalStudyGenerator | None = None, model: str | None = None) -> None:
        self.fallback = fallback or LocalStudyGenerator()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    @property
    def is_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def generate(
        self,
        concepts: list[Any],
        card_count: int = 10,
        quiz_count: int = 12,
        source_text: str = "",
    ) -> StudySet:
        if not self.is_available:
            return self.fallback.generate(concepts, card_count, quiz_count, source_text)

        try:
            from openai import OpenAI

            client = OpenAI()
            response = client.responses.create(
                model=self.model,
                input=_build_ai_prompt(concepts, card_count, quiz_count, source_text),
                store=False,
            )
            return _study_set_from_ai_json(response.output_text, concepts, card_count, quiz_count, source_text)
        except Exception:
            return self.fallback.generate(concepts, card_count, quiz_count, source_text)


def check_answer(question: QuizQuestion | PracticeQuestion, response: str) -> bool:
    expected = _normalize_answer(question.answer)
    actual = _normalize_answer(response)
    if not actual:
        return False

    question_type = getattr(question, "question_type", "fill_in")
    options = getattr(question, "options", [])

    if question_type == "mcq" and len(actual) == 1 and actual in "abcd":
        option_index = ord(actual) - ord("a")
        if 0 <= option_index < len(options):
            actual = _normalize_answer(options[option_index])

    if question_type == "math_problem":
        return _numeric_value(actual) == _numeric_value(expected)

    if question_type == "rearrange":
        return actual == expected

    return actual == expected or expected in actual


def _build_ai_prompt(concepts: list[Any], card_count: int, quiz_count: int, source_text: str) -> str:
    concept_records = _prepare_concept_records(concepts, source_text)
    concept_text = "\n".join(
        f"- {concept.title} ({concept.block_type}): {concept.explanation} {'; '.join(concept.items)}"
        for concept in concept_records
    )
    excerpt = source_text[:6000]
    return f"""
Create an Exam Buddy study set as strict JSON only.

Concepts and source evidence:
{concept_text}
Source excerpt:
{excerpt}

Return this shape:
{{
  "flashcards": [{{"question": "...", "answer": "...", "concept": "..."}}],
  "practice_questions": [{{"prompt": "...", "answer": "...", "concept": "..."}}],
  "quiz_questions": [
    {{"prompt": "...", "answer": "...", "question_type": "mcq|fill_in|rearrange|math_problem", "timer_seconds": 20, "options": ["...", "...", "...", "..."]}}
  ]
}}

Rules:
- flashcards count: {max(5, card_count)}
- quiz question count: {_clamp(quiz_count, 10, 15)}
- include mcq, fill_in, rearrange, and math_problem quiz types
- each timer_seconds must be between 20 and 60
- answers must be short enough for automated checking
- flashcard answers must use the source evidence, not generic study advice
""".strip()


def _study_set_from_ai_json(
    payload: str,
    concepts: list[Any],
    card_count: int,
    quiz_count: int,
    source_text: str = "",
) -> StudySet:
    data = json.loads(_strip_code_fence(payload))
    flashcards = [
        Flashcard(
            question=str(item.get("question", "")).strip(),
            answer=str(item.get("answer", "")).strip(),
            concept=str(item.get("concept", "")).strip() or "concept",
        )
        for item in data.get("flashcards", [])
    ]
    practice_questions = [
        PracticeQuestion(
            prompt=str(item.get("prompt", "")).strip(),
            answer=str(item.get("answer", "")).strip(),
            concept=str(item.get("concept", "")).strip() or "concept",
        )
        for item in data.get("practice_questions", [])
    ]
    quiz_questions = []
    for item in data.get("quiz_questions", []):
        question_type = str(item.get("question_type", "fill_in")).strip()
        if question_type not in QUESTION_TYPES:
            question_type = "fill_in"
        timer = _clamp(int(item.get("timer_seconds", 30)), 20, 60)
        quiz_questions.append(
            QuizQuestion(
                prompt=str(item.get("prompt", "")).strip(),
                answer=str(item.get("answer", "")).strip(),
                question_type=question_type,
                timer_seconds=timer,
                options=[str(option).strip() for option in item.get("options", [])],
            )
        )

    if len(flashcards) < 5 or len(quiz_questions) < 10 or not practice_questions:
        return LocalStudyGenerator().generate(concepts, card_count, quiz_count, source_text)
    return StudySet(
        flashcards=flashcards[: max(5, card_count)],
        practice_questions=practice_questions,
        quiz_questions=quiz_questions[: _clamp(quiz_count, 10, 15)],
    )


def _prepare_concepts(concepts: list[Any]) -> list[str]:
    return [concept.title for concept in _prepare_concept_records(concepts)]


def _prepare_concept_records(concepts: list[Any], source_text: str = "") -> list[ConceptRecord]:
    clean: list[ConceptRecord] = []
    seen: set[str] = set()
    for concept in concepts:
        record = _coerce_concept_record(concept, source_text)
        key = record.title.lower()
        if record.title and key not in seen:
            clean.append(record)
            seen.add(key)
    return clean or [
        ConceptRecord("main idea", "Review the main idea from the source material."),
        ConceptRecord("definition", "Review the definition from the source material."),
        ConceptRecord("example", "Review an example from the source material."),
        ConceptRecord("process", "Review the process described in the source material."),
        ConceptRecord("application", "Review how the material can be applied."),
    ]


def _coerce_concept_record(concept: Any, source_text: str = "") -> ConceptRecord:
    if isinstance(concept, dict):
        title = _clean_concept_title(concept.get("title") or concept.get("concept") or concept.get("name"))
        source_sentence = str(concept.get("source_sentence") or concept.get("sourceSentence") or "").strip()
        explanation = str(concept.get("summary") or concept.get("explanation") or "").strip()
        items = tuple(str(item).strip() for item in concept.get("items", []) if str(item).strip())
        block_type = str(concept.get("block_type") or concept.get("type") or "concept").strip() or "concept"
    else:
        title = _clean_concept_title(getattr(concept, "title", concept))
        source_sentence = str(
            getattr(concept, "source_excerpt", "")
            or getattr(concept, "source_sentence", "")
            or getattr(concept, "sourceSentence", "")
        ).strip()
        explanation = str(getattr(concept, "summary", "") or getattr(concept, "explanation", "") or "").strip()
        items = tuple(str(item).strip() for item in getattr(concept, "items", ()) if str(item).strip())
        block_type = str(getattr(concept, "block_type", "concept") or "concept").strip()

    if not source_sentence and source_text and title:
        source_sentence = _find_source_sentence(title, source_text)
    if not explanation and source_sentence:
        explanation = f"{title}: {source_sentence.rstrip('.!?')}."
    if not explanation and title:
        explanation = f"{title}: review this concept in the source material."
    return ConceptRecord(title=title, explanation=explanation, source_sentence=source_sentence, items=items, block_type=block_type)


def _clean_concept_title(value: Any) -> str:
    return " ".join(str(value or "").split()).strip(" .,:;")


def _compose_flashcard_answer(concept: ConceptRecord) -> str:
    if concept.items:
        summary = concept.explanation.rstrip(".")
        lines = [summary] if summary and len(summary) <= 220 else []
        lines.extend(concept.items)
        unique_lines: list[str] = []
        seen: set[str] = set()
        for line in lines:
            normalized = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_lines.append(line)
        unique_lines = unique_lines[:6]
        return "\n".join(line if line.endswith((".", "!", "?")) else f"{line}." for line in unique_lines)
    if concept.source_sentence:
        source = concept.source_sentence.rstrip(".!?")
        if _same_title_prefix(source, concept.title):
            return f"{source}."
        return f"{concept.title}: {source}."
    return concept.explanation or f"{concept.title}: review this concept in the source material."


def _same_title_prefix(text: str, title: str) -> bool:
    def normalize(value: str) -> str:
        value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        return re.sub(r"\bdefinitions?\b", "definition", value)

    normalized_text = normalize(text)
    normalized_title = normalize(title)
    return normalized_text.startswith(normalized_title) or normalized_text.startswith(normalized_title.rstrip("s"))


def _compose_practice_prompt(concept: ConceptRecord) -> str:
    if concept.source_sentence:
        return f"In your own words, explain {concept.title} using this source clue: {concept.source_sentence}"
    return f"In your own words, explain {concept.title}."


def _fill_in_prompt(concept: ConceptRecord) -> str:
    if concept.source_sentence:
        pattern = re.compile(re.escape(concept.title), re.IGNORECASE)
        clue = pattern.sub("_____", concept.source_sentence, count=1)
        if clue != concept.source_sentence:
            return f"Fill in the blank from the source: {clue}"
    return "Fill in the blank: _____ is one of the key concepts from this material."


def _find_source_sentence(title: str, source_text: str) -> str:
    words = [re.escape(word) for word in title.lower().split() if word]
    if not words:
        return ""
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", source_text).strip())
        if sentence.strip()
    ]
    phrase_pattern = re.compile(r"\b" + re.escape(title.lower()) + r"\b", re.IGNORECASE)
    for sentence in sentences:
        if phrase_pattern.search(sentence):
            return sentence
    for sentence in sentences:
        lowered = sentence.lower()
        if all(re.search(r"\b" + word + r"\b", lowered) for word in words):
            return sentence
    return ""


def _cycle_take(items: list[T], count: int) -> list[T]:
    return [items[index % len(items)] for index in range(count)]


def _make_options(answer: str, concepts: list[str], seed: int) -> list[str]:
    distractors = [concept for concept in concepts if concept.lower() != answer.lower()]
    while len(distractors) < 3:
        distractors.append(f"related idea {len(distractors) + 1}")
    options = [answer] + distractors[:3]
    random.Random(seed).shuffle(options)
    return options


def _rearrange_phrase(concept: str) -> str:
    words = concept.split()
    if len(words) >= 2:
        return concept
    return f"key idea {concept}"


def _normalize_answer(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9.\- ]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _numeric_value(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group(0)) if match else None


def _strip_code_fence(payload: str) -> str:
    payload = payload.strip()
    if payload.startswith("```"):
        payload = re.sub(r"^```(?:json)?", "", payload).strip()
        payload = re.sub(r"```$", "", payload).strip()
    return payload


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))
