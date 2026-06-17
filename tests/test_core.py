import unittest

from exam_buddy.generation import LocalStudyGenerator, check_answer
from exam_buddy.models import PracticeQuestion, QuizQuestion
from exam_buddy.parser import extract_key_concept_details, extract_key_concepts
from exam_buddy.sessions import PracticeSession, TimedQuizSession


class ParserTests(unittest.TestCase):
    def test_extract_key_concepts_returns_source_backed_study_ideas(self):
        text = """
        Photosynthesis converts light energy into chemical energy. Chlorophyll
        absorbs sunlight inside chloroplasts. Photosynthesis supports glucose
        production, oxygen release, and plant growth. Cellular respiration uses
        glucose inside mitochondria to release ATP energy for cells.
        """

        concepts = extract_key_concepts(text, minimum=5, maximum=8)

        self.assertGreaterEqual(len(concepts), 5)
        self.assertLessEqual(len(concepts), 8)
        self.assertIn("photosynthesis", [item.lower() for item in concepts])
        self.assertIn("light energy", [item.lower() for item in concepts])
        self.assertIn("glucose production", [item.lower() for item in concepts])
        self.assertIn("cellular respiration", [item.lower() for item in concepts])
        self.assertNotIn("energy", [item.lower() for item in concepts])
        self.assertNotIn("release", [item.lower() for item in concepts])

    def test_extract_key_concept_details_include_evidence_sentences(self):
        text = """
        Photosynthesis converts light energy into chemical energy. Chlorophyll
        absorbs sunlight inside chloroplasts. Photosynthesis supports glucose
        production, oxygen release, and plant growth.
        """

        details = extract_key_concept_details(text, minimum=5, maximum=8)

        self.assertGreaterEqual(len(details), 5)
        first_titles = [detail.title.lower() for detail in details]
        self.assertIn("light energy", first_titles)
        light_energy = next(detail for detail in details if detail.title.lower() == "light energy")
        self.assertIn("Photosynthesis converts light energy", light_energy.source_sentence)
        self.assertIn("light energy", light_energy.explanation.lower())


class GenerationTests(unittest.TestCase):
    def test_local_generator_creates_required_study_modes(self):
        concepts = [
            "photosynthesis",
            "chlorophyll",
            "chloroplasts",
            "glucose production",
            "oxygen release",
            "cellular respiration",
            "mitochondria",
            "ATP energy",
            "plant growth",
            "light energy",
        ]

        study_set = LocalStudyGenerator().generate(concepts, card_count=7, quiz_count=12)

        self.assertEqual(len(study_set.flashcards), 7)
        self.assertGreaterEqual(len(study_set.practice_questions), 5)
        self.assertEqual(len(study_set.quiz_questions), 12)
        self.assertTrue(all(card.question and card.answer for card in study_set.flashcards))
        self.assertTrue(all(20 <= question.timer_seconds <= 60 for question in study_set.quiz_questions))
        self.assertEqual(
            {"mcq", "fill_in", "rearrange", "math_problem"},
            {question.question_type for question in study_set.quiz_questions},
        )

    def test_local_generator_builds_flashcards_from_source_evidence(self):
        text = """
        Photosynthesis converts light energy into chemical energy. Chlorophyll
        absorbs sunlight inside chloroplasts. Photosynthesis supports glucose
        production, oxygen release, and plant growth.
        """
        details = extract_key_concept_details(text, minimum=5, maximum=8)

        study_set = LocalStudyGenerator().generate(details, card_count=5, quiz_count=10, source_text=text)

        answers = "\n".join(card.answer for card in study_set.flashcards)
        self.assertIn("Photosynthesis converts light energy into chemical energy", answers)
        self.assertIn("glucose production", answers.lower())
        self.assertNotIn("is a key concept from the source", answers)
        self.assertNotIn("Explain its definition", answers)

    def test_check_answer_handles_case_spacing_and_mcq_options(self):
        fill = QuizQuestion(
            prompt="Which process converts light energy?",
            answer="photosynthesis",
            question_type="fill_in",
            timer_seconds=30,
        )
        mcq = QuizQuestion(
            prompt="Pick the organelle.",
            answer="mitochondria",
            question_type="mcq",
            timer_seconds=30,
            options=["chlorophyll", "mitochondria", "oxygen", "glucose"],
        )

        self.assertTrue(check_answer(fill, "  Photosynthesis "))
        self.assertTrue(check_answer(mcq, "B"))
        self.assertTrue(check_answer(mcq, "mitochondria"))
        self.assertFalse(check_answer(mcq, "A"))


class SessionTests(unittest.TestCase):
    def test_practice_session_retries_missed_questions_until_mastery_threshold(self):
        questions = [
            PracticeQuestion(prompt="Define photosynthesis.", answer="photosynthesis", concept="photosynthesis"),
            PracticeQuestion(prompt="Define chlorophyll.", answer="chlorophyll", concept="chlorophyll"),
            PracticeQuestion(prompt="Define mitochondria.", answer="mitochondria", concept="mitochondria"),
        ]
        session = PracticeSession(questions, passing_score=70)

        self.assertTrue(session.answer_current("photosynthesis").is_correct)
        self.assertFalse(session.answer_current("wrong").is_correct)
        self.assertTrue(session.answer_current("mitochondria").is_correct)

        self.assertEqual(session.mastery_percent, 67)
        self.assertFalse(session.is_complete)
        self.assertEqual(session.current_question.concept, "chlorophyll")

        self.assertTrue(session.answer_current("chlorophyll").is_correct)
        self.assertEqual(session.mastery_percent, 100)
        self.assertTrue(session.is_complete)

    def test_timed_quiz_summary_reports_score_mastery_and_timing(self):
        quiz = TimedQuizSession(
            [
                QuizQuestion("Q1", "alpha", "fill_in", 20),
                QuizQuestion("Q2", "beta", "fill_in", 20),
            ]
        )

        quiz.answer_current("alpha", elapsed_seconds=8)
        quiz.answer_current("wrong", elapsed_seconds=21)
        summary = quiz.summary()

        self.assertEqual(summary.correct_count, 1)
        self.assertEqual(summary.total_count, 2)
        self.assertEqual(summary.score_percent, 50)
        self.assertEqual(summary.mastery_percent, 50)
        self.assertEqual(summary.elapsed_seconds, 29)


if __name__ == "__main__":
    unittest.main()
