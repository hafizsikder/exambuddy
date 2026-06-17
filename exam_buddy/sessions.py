from __future__ import annotations

from collections import deque

from .generation import check_answer
from .models import AnswerFeedback, PracticeQuestion, QuizQuestion, QuizSummary


class PracticeSession:
    def __init__(self, questions: list[PracticeQuestion], passing_score: int = 70):
        if not questions:
            raise ValueError("PracticeSession requires at least one question.")
        self.questions = questions
        self.passing_score = passing_score
        self._queue = deque(range(len(questions)))
        self._mastered = [False] * len(questions)
        self.mastery_percent = 0
        self.is_complete = False
        self.current_question = questions[self._queue[0]]

    def answer_current(self, response: str) -> AnswerFeedback:
        if self.is_complete:
            return AnswerFeedback(True, "", "Practice is already complete.")

        question_index = self._queue.popleft()
        question = self.questions[question_index]
        is_correct = check_answer(question, response)
        self._mastered[question_index] = is_correct

        if not is_correct:
            self._queue.append(question_index)

        self.mastery_percent = round(sum(self._mastered) / len(self._mastered) * 100)
        self.is_complete = self.mastery_percent >= self.passing_score and all(self._mastered)

        if not self.is_complete and self._queue:
            self.current_question = self.questions[self._queue[0]]

        message = "Correct." if is_correct else f"Review this again. Expected: {question.answer}"
        return AnswerFeedback(is_correct, question.answer, message)


class TimedQuizSession:
    def __init__(self, questions: list[QuizQuestion]):
        if not questions:
            raise ValueError("TimedQuizSession requires at least one question.")
        self.questions = questions
        self.current_index = 0
        self.answers: list[tuple[QuizQuestion, str, bool, int]] = []

    @property
    def current_question(self) -> QuizQuestion | None:
        if self.current_index >= len(self.questions):
            return None
        return self.questions[self.current_index]

    @property
    def is_complete(self) -> bool:
        return self.current_index >= len(self.questions)

    def answer_current(self, response: str, elapsed_seconds: int) -> AnswerFeedback:
        question = self.current_question
        if question is None:
            return AnswerFeedback(True, "", "Quiz is already complete.")

        is_correct = bool(response.strip()) and check_answer(question, response)
        self.answers.append((question, response, is_correct, max(0, int(elapsed_seconds))))
        self.current_index += 1

        message = "Correct." if is_correct else f"Incorrect. Expected: {question.answer}"
        return AnswerFeedback(is_correct, question.answer, message)

    def summary(self) -> QuizSummary:
        correct = sum(1 for _, _, is_correct, _ in self.answers if is_correct)
        total = len(self.questions)
        score_percent = round(correct / total * 100)
        elapsed_seconds = sum(elapsed for _, _, _, elapsed in self.answers)
        return QuizSummary(
            correct_count=correct,
            total_count=total,
            score_percent=score_percent,
            mastery_percent=score_percent,
            elapsed_seconds=elapsed_seconds,
        )
