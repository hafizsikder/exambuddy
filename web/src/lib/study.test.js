import { describe, expect, it } from 'vitest';
import {
  answerMatches,
  createPracticeSession,
  createTimedQuizSession,
  extractKeyConcepts,
  generateStudySet,
} from './study.js';

describe('web study engine', () => {
  it('extracts ranked key concepts from source text', () => {
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
    expect(concepts.some((item) => item.toLowerCase().includes('glucose'))).toBe(true);
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
