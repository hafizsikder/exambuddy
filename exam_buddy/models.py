from dataclasses import dataclass, field


@dataclass
class Flashcard:
    question: str
    answer: str
    concept: str


@dataclass
class PracticeQuestion:
    prompt: str
    answer: str
    concept: str


@dataclass
class QuizQuestion:
    prompt: str
    answer: str
    question_type: str
    timer_seconds: int
    options: list[str] = field(default_factory=list)


@dataclass
class StudySet:
    flashcards: list[Flashcard]
    practice_questions: list[PracticeQuestion]
    quiz_questions: list[QuizQuestion]


@dataclass
class AnswerFeedback:
    is_correct: bool
    expected_answer: str
    message: str


@dataclass
class QuizSummary:
    correct_count: int
    total_count: int
    score_percent: int
    mastery_percent: int
    elapsed_seconds: int
