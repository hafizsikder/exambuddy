import unittest

from exam_buddy.generation import LocalStudyGenerator, check_answer
from exam_buddy.models import PracticeQuestion, QuizQuestion
from exam_buddy.parser import extract_key_concept_details, extract_key_concepts, extract_study_blocks
from exam_buddy.sessions import PracticeSession, TimedQuizSession


class ParserTests(unittest.TestCase):
    SDS_EXCERPT = """
    Definition of Data Science: Data science may be defined as an interdisciplinary field
    that combines scientific methods, algorithms, and systems to extract knowledge and
    insights from structured and unstructured data. It encompasses various techniques
    such as data mining, machine learning, and statistical analysis to uncover patterns,
    trends, and correlations within data.

    Importance of Statistics in Data Science: The importance of statistics for data science
    and statistics for data analytics is immense. Exploring it through the below-mentioned
    points:
    • For description and quantification of data
    • For data identification and conversion of data patterns into usable format
    • Contributes to probability distribution and estimation
    • Enhance the data visualization and reduce the assumptions

    Lecture 2:
    Population: A well define group or sector or area about that you want to draw your
    conclusion or decision then the entire group is known as population.
    Finite Population: If the population unit of a population is countable or a finite
    number then this type of population is known as finite population.
    Infinite Population: If the population unit of a population is not countable or not a
    finite number then this type of population is known as infinite population.
    Sample: A representative part of population is known as sample.
    Sampling Frame: The entire list of population units is known as sampling frame.
    """

    SDS_SLIDE_STYLE_EXCERPT = """
    Definitions of Data Science
    Data Science -> Interdisciplinary field using methods, algorithms, and systems to extract knowledge from structured/unstructured data.
    Techniques: Data mining, Machine learning, Statistical analysis.

    Importance of Statistics in Data Science
    Description & quantification of data.
    Pattern identification and conversion.
    Probability distribution and estimation.
    Data visualization enhancement.

    Population & Sampling
    Population -> Entire group under study.
    Finite population -> Countable units (e.g., JU students).
    Infinite population -> Uncountable units (e.g., fish in a river).
    Sample -> Representative part of population.
    Sampling frame -> List of all population units.
    """

    def test_extract_study_blocks_groups_sds_lecture_content(self):
        blocks = extract_study_blocks(self.SDS_EXCERPT, minimum=3, maximum=8)
        titles = [block.title for block in blocks]

        self.assertIn("Definitions of Data Science", titles)
        self.assertIn("Importance of Statistics in Data Science", titles)
        self.assertIn("Population & Sampling", titles)

        data_science = next(block for block in blocks if block.title == "Definitions of Data Science")
        self.assertEqual(data_science.block_type, "definition")
        self.assertIn("Interdisciplinary field", data_science.summary)
        self.assertIn("Data mining", "\n".join(data_science.items))
        self.assertIn("Machine learning", "\n".join(data_science.items))
        self.assertIn("Statistical analysis", "\n".join(data_science.items))

        population = next(block for block in blocks if block.title == "Population & Sampling")
        joined_items = "\n".join(population.items)
        self.assertIn("Population -> Entire group under study.", joined_items)
        self.assertIn("Finite population -> Countable units.", joined_items)
        self.assertIn("Infinite population -> Uncountable units.", joined_items)
        self.assertIn("Sample -> Representative part of population.", joined_items)
        self.assertIn("Sampling frame -> List of all population units.", joined_items)

    def test_extract_study_blocks_groups_slide_style_sds_content(self):
        blocks = extract_study_blocks(self.SDS_SLIDE_STYLE_EXCERPT, minimum=3, maximum=8)
        titles = [block.title for block in blocks]

        self.assertEqual(
            ["Definitions of Data Science", "Importance of Statistics in Data Science", "Population & Sampling"],
            titles[:3],
        )

        data_science = next(block for block in blocks if block.title == "Definitions of Data Science")
        self.assertIn("Interdisciplinary field", data_science.summary)
        self.assertIn("Data mining", "\n".join(data_science.items))

        statistics = next(block for block in blocks if block.title == "Importance of Statistics in Data Science")
        statistics_items = "\n".join(statistics.items)
        self.assertIn("Description & quantification of data.", statistics_items)
        self.assertIn("Probability distribution and estimation.", statistics_items)

        population = next(block for block in blocks if block.title == "Population & Sampling")
        population_items = "\n".join(population.items)
        self.assertIn("Finite population -> Countable units (e.g., JU students).", population_items)
        self.assertIn("Sampling frame -> List of all population units.", population_items)

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
    def test_local_generator_builds_cards_from_study_blocks(self):
        blocks = extract_study_blocks(ParserTests.SDS_EXCERPT, minimum=3, maximum=8)

        study_set = LocalStudyGenerator().generate(blocks, card_count=5, quiz_count=10, source_text=ParserTests.SDS_EXCERPT)

        cards = {card.concept: card for card in study_set.flashcards}
        self.assertIn("Definitions of Data Science", cards)
        self.assertIn("Importance of Statistics in Data Science", cards)
        self.assertIn("Population & Sampling", cards)

        data_science_answer = cards["Definitions of Data Science"].answer
        self.assertIn("Interdisciplinary field", data_science_answer)
        self.assertIn("Data mining", data_science_answer)
        self.assertIn("Machine learning", data_science_answer)

        population_answer = cards["Population & Sampling"].answer
        self.assertIn("Population -> Entire group under study.", population_answer)
        self.assertIn("Sampling frame -> List of all population units.", population_answer)
        self.assertNotIn("review this concept in the source material", population_answer)

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
