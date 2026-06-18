import { describe, expect, it } from 'vitest';
import {
  answerMatches,
  createPracticeSession,
  createTimedQuizSession,
  extractKeyConceptDetails,
  extractKeyConcepts,
  extractStudyBlocks,
  generateStudySet,
} from './study.js';

const sdsExcerpt = `
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
`;

const sdsSlideStyleExcerpt = `
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
`;

describe('web study engine', () => {
  it('extracts grouped study blocks from SDS lecture content', () => {
    const blocks = extractStudyBlocks(sdsExcerpt, { minimum: 3, maximum: 8 });
    const titles = blocks.map((block) => block.title);

    expect(titles).toContain('Definitions of Data Science');
    expect(titles).toContain('Importance of Statistics in Data Science');
    expect(titles).toContain('Population & Sampling');

    const dataScience = blocks.find((block) => block.title === 'Definitions of Data Science');
    expect(dataScience.type).toBe('definition');
    expect(dataScience.summary).toContain('Interdisciplinary field');
    expect(dataScience.items.join('\n')).toContain('Data mining');
    expect(dataScience.items.join('\n')).toContain('Machine learning');
    expect(dataScience.items.join('\n')).toContain('Statistical analysis');

    const population = blocks.find((block) => block.title === 'Population & Sampling');
    expect(population.items.join('\n')).toContain('Population -> Entire group under study.');
    expect(population.items.join('\n')).toContain('Finite population -> Countable units.');
    expect(population.items.join('\n')).toContain('Infinite population -> Uncountable units.');
    expect(population.items.join('\n')).toContain('Sample -> Representative part of population.');
    expect(population.items.join('\n')).toContain('Sampling frame -> List of all population units.');
  });

  it('extracts grouped study blocks from slide-style SDS headings', () => {
    const blocks = extractStudyBlocks(sdsSlideStyleExcerpt, { minimum: 3, maximum: 8 });
    const titles = blocks.map((block) => block.title);

    expect(titles.slice(0, 3)).toEqual([
      'Definitions of Data Science',
      'Importance of Statistics in Data Science',
      'Population & Sampling',
    ]);

    const dataScience = blocks.find((block) => block.title === 'Definitions of Data Science');
    expect(dataScience.summary).toContain('Interdisciplinary field');
    expect(dataScience.items.join('\n')).toContain('Data mining');

    const statistics = blocks.find((block) => block.title === 'Importance of Statistics in Data Science');
    expect(statistics.items.join('\n')).toContain('Description & quantification of data.');
    expect(statistics.items.join('\n')).toContain('Probability distribution and estimation.');

    const population = blocks.find((block) => block.title === 'Population & Sampling');
    expect(population.items.join('\n')).toContain('Finite population -> Countable units (e.g., JU students).');
    expect(population.items.join('\n')).toContain('Sampling frame -> List of all population units.');
  });

  it('extracts source-backed study ideas from source text', () => {
    const text = `
      Photosynthesis converts light energy into chemical energy. Chlorophyll
      absorbs sunlight inside chloroplasts. Photosynthesis supports glucose
      production, oxygen release, and plant growth. Cellular respiration uses
      glucose inside mitochondria to release ATP energy for cells.
    `;

    const concepts = extractKeyConcepts(text, { minimum: 5, maximum: 8 });

    expect(concepts.length).toBeGreaterThanOrEqual(5);
    expect(concepts.length).toBeLessThanOrEqual(8);
    expect(concepts.map((item) => item.toLowerCase())).toContain('photosynthesis');
    expect(concepts.map((item) => item.toLowerCase())).toContain('light energy');
    expect(concepts.map((item) => item.toLowerCase())).toContain('glucose production');
    expect(concepts.map((item) => item.toLowerCase())).toContain('cellular respiration');
    expect(concepts.map((item) => item.toLowerCase())).not.toContain('energy');
    expect(concepts.map((item) => item.toLowerCase())).not.toContain('release');
  });

  it('returns concept details with source evidence sentences', () => {
    const text = `
      Photosynthesis converts light energy into chemical energy. Chlorophyll
      absorbs sunlight inside chloroplasts. Photosynthesis supports glucose
      production, oxygen release, and plant growth.
    `;

    const details = extractKeyConceptDetails(text, { minimum: 5, maximum: 8 });
    const lightEnergy = details.find((detail) => detail.title.toLowerCase() === 'light energy');

    expect(details.length).toBeGreaterThanOrEqual(5);
    expect(lightEnergy?.sourceSentence).toContain('Photosynthesis converts light energy');
    expect(lightEnergy?.explanation.toLowerCase()).toContain('light energy');
  });

  it('excludes common connector words from concepts', () => {
    const concepts = extractKeyConcepts(
      'and and and for for the the photosynthesis photosynthesis mitochondria chlorophyll glucose oxygen plant energy',
      { minimum: 5, maximum: 8 },
    );

    expect(concepts).not.toContain('and');
    expect(concepts).not.toContain('for');
    expect(concepts).not.toContain('the');
  });

  it('generates flashcards, practice questions, and mixed timed quiz questions', () => {
    const concepts = [
      'photosynthesis',
      'chlorophyll',
      'chloroplasts',
      'glucose production',
      'oxygen release',
      'cellular respiration',
      'mitochondria',
      'ATP energy',
      'plant growth',
      'light energy',
    ];

    const studySet = generateStudySet(concepts, { cardCount: 7, quizCount: 12 });

    expect(studySet.flashcards).toHaveLength(7);
    expect(studySet.practiceQuestions.length).toBeGreaterThanOrEqual(5);
    expect(studySet.quizQuestions).toHaveLength(12);
    expect(new Set(studySet.quizQuestions.map((question) => question.type))).toEqual(
      new Set(['mcq', 'fill_in', 'rearrange', 'math_problem']),
    );
    expect(studySet.quizQuestions.every((question) => question.timerSeconds >= 20 && question.timerSeconds <= 60)).toBe(true);
  });

  it('builds flashcards directly from grouped study blocks', () => {
    const blocks = extractStudyBlocks(sdsExcerpt, { minimum: 3, maximum: 8 });

    const studySet = generateStudySet(blocks, { cardCount: 5, quizCount: 10, sourceText: sdsExcerpt });
    const cards = Object.fromEntries(studySet.flashcards.map((card) => [card.concept, card]));

    expect(cards['Definitions of Data Science'].answer).toContain('Interdisciplinary field');
    expect(cards['Definitions of Data Science'].answer).toContain('Data mining');
    expect(cards['Definitions of Data Science'].answer).toContain('Machine learning');
    expect(cards['Population & Sampling'].answer).toContain('Population -> Entire group under study.');
    expect(cards['Population & Sampling'].answer).toContain('Sampling frame -> List of all population units.');
    expect(cards['Population & Sampling'].answer).not.toContain('review this concept in the source material');
  });

  it('builds flashcards from source evidence instead of generic filler', () => {
    const text = `
      Photosynthesis converts light energy into chemical energy. Chlorophyll
      absorbs sunlight inside chloroplasts. Photosynthesis supports glucose
      production, oxygen release, and plant growth.
    `;
    const details = extractKeyConceptDetails(text, { minimum: 5, maximum: 8 });

    const studySet = generateStudySet(details, { cardCount: 5, quizCount: 10, sourceText: text });
    const answers = studySet.flashcards.map((card) => card.answer).join('\n');

    expect(answers).toContain('Photosynthesis converts light energy into chemical energy');
    expect(answers.toLowerCase()).toContain('glucose production');
    expect(answers).not.toContain('is a key concept from the source');
    expect(answers).not.toContain('Explain its definition');
  });

  it('checks typed answers and MCQ letter answers', () => {
    expect(answerMatches({ answer: 'Photosynthesis', type: 'fill_in' }, ' photosynthesis ')).toBe(true);
    expect(
      answerMatches(
        {
          answer: 'mitochondria',
          type: 'mcq',
          options: ['chlorophyll', 'mitochondria', 'oxygen', 'glucose'],
        },
        'B',
      ),
    ).toBe(true);
  });

  it('repeats missed practice questions until all are mastered above 70 percent', () => {
    const session = createPracticeSession([
      { prompt: 'Define photosynthesis.', answer: 'photosynthesis', concept: 'photosynthesis' },
      { prompt: 'Define chlorophyll.', answer: 'chlorophyll', concept: 'chlorophyll' },
      { prompt: 'Define mitochondria.', answer: 'mitochondria', concept: 'mitochondria' },
    ]);

    expect(session.answer('photosynthesis').isCorrect).toBe(true);
    expect(session.answer('wrong').isCorrect).toBe(false);
    expect(session.answer('mitochondria').isCorrect).toBe(true);
    expect(session.masteryPercent).toBe(67);
    expect(session.isComplete).toBe(false);
    expect(session.currentQuestion.concept).toBe('chlorophyll');

    expect(session.answer('chlorophyll').isCorrect).toBe(true);
    expect(session.masteryPercent).toBe(100);
    expect(session.isComplete).toBe(true);
  });

  it('summarizes timed quiz score, mastery, and elapsed time', () => {
    const session = createTimedQuizSession([
      { prompt: 'Q1', answer: 'alpha', type: 'fill_in', timerSeconds: 20 },
      { prompt: 'Q2', answer: 'beta', type: 'fill_in', timerSeconds: 20 },
    ]);

    session.answer('alpha', 8);
    session.answer('wrong', 21);

    expect(session.summary()).toEqual({
      correctCount: 1,
      totalCount: 2,
      scorePercent: 50,
      masteryPercent: 50,
      elapsedSeconds: 29,
    });
  });
});
