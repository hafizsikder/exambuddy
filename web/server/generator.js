import OpenAI from 'openai';
import { generateStudySet } from '../src/lib/study.js';

export async function generateStudyMaterial({ concepts, sourceText = '', cardCount = 10, quizCount = 12, useAi = false }) {
  if (!useAi || !process.env.OPENAI_API_KEY) {
    return { studySet: generateStudySet(concepts, { cardCount, quizCount }), provider: 'local' };
  }

  try {
    const client = new OpenAI();
    const response = await client.responses.create({
      model: process.env.OPENAI_MODEL || 'gpt-5.4-mini',
      input: buildPrompt(concepts, sourceText, cardCount, quizCount),
      store: false,
    });
    return { studySet: normalizeAiStudySet(response.output_text, concepts, cardCount, quizCount), provider: 'openai' };
  } catch {
    return { studySet: generateStudySet(concepts, { cardCount, quizCount }), provider: 'local-fallback' };
  }
}

function buildPrompt(concepts, sourceText, cardCount, quizCount) {
  return `
Create an Exam Buddy study set as strict JSON only.
Concepts: ${concepts.join(', ')}
Source excerpt:
${String(sourceText).slice(0, 6000)}

Return:
{
  "flashcards": [{"question": "...", "answer": "...", "concept": "..."}],
  "practiceQuestions": [{"prompt": "...", "answer": "...", "concept": "..."}],
  "quizQuestions": [{"prompt": "...", "answer": "...", "type": "mcq|fill_in|rearrange|math_problem", "timerSeconds": 20, "options": ["...", "...", "...", "..."]}]
}

Rules:
- flashcards count: ${Math.max(5, Number(cardCount) || 10)}
- quiz question count: ${Math.max(10, Math.min(15, Number(quizCount) || 12))}
- include mcq, fill_in, rearrange, and math_problem quiz types
- each timerSeconds must be between 20 and 60
- answers must be short enough for automated checking
`.trim();
}

function normalizeAiStudySet(payload, concepts, cardCount, quizCount) {
  const data = JSON.parse(stripCodeFence(payload));
  const studySet = {
    flashcards: Array.isArray(data.flashcards) ? data.flashcards : [],
    practiceQuestions: Array.isArray(data.practiceQuestions) ? data.practiceQuestions : [],
    quizQuestions: Array.isArray(data.quizQuestions) ? data.quizQuestions : [],
  };

  if (studySet.flashcards.length < 5 || studySet.practiceQuestions.length < 1 || studySet.quizQuestions.length < 10) {
    return generateStudySet(concepts, { cardCount, quizCount });
  }

  return {
    flashcards: studySet.flashcards.slice(0, Math.max(5, Number(cardCount) || 10)),
    practiceQuestions: studySet.practiceQuestions,
    quizQuestions: studySet.quizQuestions.slice(0, Math.max(10, Math.min(15, Number(quizCount) || 12))).map((question) => ({
      ...question,
      type: ['mcq', 'fill_in', 'rearrange', 'math_problem'].includes(question.type) ? question.type : 'fill_in',
      timerSeconds: Math.max(20, Math.min(60, Number(question.timerSeconds) || 30)),
      options: Array.isArray(question.options) ? question.options : [],
    })),
  };
}

function stripCodeFence(payload) {
  return String(payload || '')
    .trim()
    .replace(/^```(?:json)?/i, '')
    .replace(/```$/i, '')
    .trim();
}
