from __future__ import annotations

import json
import os
import random
import re
from typing import Any

from .models import Flashcard, PracticeQuestion, QuizQuestion, StudySet


QUESTION_TYPES = ("mcq", "fill_in", "rearrange", "math_problem")


class LocalStudyGenerator:
    """Deterministic fallback generator that never calls the network."""

    def generate(
        self,
        concepts: list[str],
        card_count: int = 10,
        quiz_count: int = 12,
        source_text: str = "",
    ) -> StudySet:
        clean_concepts = _prepare_concepts(concepts)
        flashcard_total = _clamp(card_count, 5, max(5, len(clean_concepts)))
        quiz_total = _clamp(quiz_count, 10, 15)

        flashcards = [
            Flashcard(
                question=f"What is the key idea behind {concept}?",
                answer=f"{concept} is a key concept from the source. Explain its definition, purpose, and one example.",
                concept=concept,
            )
            for concept in _cycle_take(clean_concepts, flashcard_total)
        ]

        practice_questions = [
            PracticeQuestion(
                prompt=f"In your own words, explain {concept}.",
                answer=concept,
                concept=concept,
            )
            for concept in _cycle_take(clean_concepts, max(5, min(len(clean_concepts), 12)))
        ]

        quiz_questions = [
            self._build_quiz_question(index, concept, clean_concepts)
            for index, concept in enumerate(_cycle_take(clean_concepts, quiz_total))
        ]

        return StudySet(flashcards, practice_questions, quiz_questions)

    def _build_quiz_question(self, index: int, concept: str, concepts: list[str]) -> QuizQuestion:
        question_type = QUESTION_TYPES[index % len(QUESTION_TYPES)]
        timer_seconds = 20 + (index % 5) * 10

        if question_type == "mcq":
            options = _make_options(concept, concepts, seed=index)
            return QuizQuestion(
                prompt=f"Which option best matches this study concept: {concept}?",
                answer=concept,
                question_type=question_type,
                timer_seconds=timer_seconds,
                options=options,
            )

        if question_type == "fill_in":
            return QuizQuestion(
                prompt=f"Fill in the blank: _____ is one of the key concepts from this material.",
                answer=concept,
                question_type=question_type,
                timer_seconds=timer_seconds,
            )

        if question_type == "rearrange":
            phrase = _rearrange_phrase(concept)
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
        concepts: list[str],
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
            return _study_set_from_ai_json(response.output_text, concepts, card_count, quiz_count)
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


def _build_ai_prompt(concepts: list[str], card_count: int, quiz_count: int, source_text: str) -> str:
    concept_text = ", ".join(_prepare_concepts(concepts))
    excerpt = source_text[:6000]
    return f"""
Create an Exam Buddy study set as strict JSON only.

Concepts: {concept_text}
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
""".strip()


def _study_set_from_ai_json(payload: str, concepts: list[str], card_count: int, quiz_count: int) -> StudySet:
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
        return LocalStudyGenerator().generate(concepts, card_count, quiz_count)
    return StudySet(
        flashcards=flashcards[: max(5, card_count)],
        practice_questions=practice_questions,
        quiz_questions=quiz_questions[: _clamp(quiz_count, 10, 15)],
    )


def _prepare_concepts(concepts: list[str]) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for concept in concepts:
        item = " ".join(str(concept).split()).strip(" .,:;")
        key = item.lower()
        if item and key not in seen:
            clean.append(item)
            seen.add(key)
    return clean or ["main idea", "definition", "example", "process", "application"]


def _cycle_take(items: list[str], count: int) -> list[str]:
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
