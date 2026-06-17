const STOP_WORDS = new Set([
  'about',
  'above',
  'after',
  'again',
  'against',
  'also',
  'and',
  'are',
  'but',
  'because',
  'before',
  'being',
  'below',
  'between',
  'could',
  'during',
  'each',
  'for',
  'from',
  'have',
  'has',
  'how',
  'its',
  'into',
  'is',
  'inside',
  'not',
  'of',
  'on',
  'or',
  'more',
  'most',
  'other',
  'over',
  'should',
  'some',
  'such',
  'than',
  'the',
  'to',
  'that',
  'their',
  'then',
  'there',
  'these',
  'they',
  'this',
  'through',
  'under',
  'uses',
  'using',
  'when',
  'where',
  'which',
  'while',
  'with',
  'would',
  'your',
]);

const QUESTION_TYPES = ['mcq', 'fill_in', 'rearrange', 'math_problem'];

export function extractKeyConcepts(text, { minimum = 5, maximum = 24 } = {}) {
  const cleaned = cleanText(text).toLowerCase();
  if (!cleaned) return [];

  const words = Array.from(cleaned.matchAll(/[a-z][a-z0-9'-]{2,}/g), (match) => match[0]).filter(
    (word) => !STOP_WORDS.has(word) && !/^\d+$/.test(word),
  );
  if (!words.length) return [];

  const wordCounts = new Map();
  const firstSeen = new Map();
  words.forEach((word, index) => {
    wordCounts.set(word, (wordCounts.get(word) ?? 0) + 1);
    if (!firstSeen.has(word)) firstSeen.set(word, index);
  });

  const candidates = new Map();
  for (const [word, count] of wordCounts.entries()) {
    candidates.set(word, count * 10 + Math.min(word.length, 16) / 4);
  }

  for (const size of [2, 3]) {
    const phraseCounts = new Map();
    for (let index = 0; index <= words.length - size; index += 1) {
      const phraseWords = words.slice(index, index + size);
      if (new Set(phraseWords).size === 1) continue;
      const phrase = phraseWords.join(' ');
      phraseCounts.set(phrase, (phraseCounts.get(phrase) ?? 0) + 1);
      if (!firstSeen.has(phrase)) firstSeen.set(phrase, index);
    }
    for (const [phrase, count] of phraseCounts.entries()) {
      const phraseWords = phrase.split(' ');
      const hasRepeatedWord = phraseWords.some((word) => (wordCounts.get(word) ?? 0) > 1);
      if (count > 1 || hasRepeatedWord) {
        candidates.set(phrase, count * 7 + phraseWords.length * 2);
      }
    }
  }

  const ranked = Array.from(candidates.keys()).sort((left, right) => {
    const scoreDiff = candidates.get(right) - candidates.get(left);
    if (scoreDiff) return scoreDiff;
    const positionDiff = firstSeen.get(left) - firstSeen.get(right);
    if (positionDiff) return positionDiff;
    return left.localeCompare(right);
  });

  const results = [];
  const usedWords = new Set();
  for (const candidate of ranked) {
    const parts = candidate.split(' ');
    if (parts.length > 1 && parts.some((part) => usedWords.has(part))) continue;
    results.push(candidate);
    parts.forEach((part) => usedWords.add(part));
    if (results.length >= maximum) break;
  }

  if (results.length < minimum) {
    const fallbackWords = Array.from(wordCounts.keys()).sort((left, right) => {
      const countDiff = wordCounts.get(right) - wordCounts.get(left);
      if (countDiff) return countDiff;
      return firstSeen.get(left) - firstSeen.get(right);
    });
    for (const word of fallbackWords) {
      if (!results.includes(word)) results.push(word);
      if (results.length >= Math.min(minimum, maximum)) break;
    }
  }

  return results.slice(0, maximum);
}

export function generateStudySet(concepts, { cardCount = 10, quizCount = 12 } = {}) {
  const prepared = prepareConcepts(concepts);
  const flashcardTotal = clamp(cardCount, 5, Math.max(5, prepared.length));
  const quizTotal = clamp(quizCount, 10, 15);

  const flashcards = cycleTake(prepared, flashcardTotal).map((concept) => ({
    question: `What is the key idea behind ${concept}?`,
    answer: `${concept} is a key concept from the source. Explain its definition, purpose, and one example.`,
    concept,
  }));

  const practiceQuestions = cycleTake(prepared, Math.max(5, Math.min(prepared.length, 12))).map((concept) => ({
    prompt: `In your own words, explain ${concept}.`,
    answer: concept,
    concept,
  }));

  const quizQuestions = cycleTake(prepared, quizTotal).map((concept, index) => buildQuizQuestion(concept, prepared, index));

  return { flashcards, practiceQuestions, quizQuestions };
}

export function answerMatches(question, response) {
  const expected = normalizeAnswer(question.answer);
  let actual = normalizeAnswer(response);
  if (!actual) return false;

  if (question.type === 'mcq' && /^[abcd]$/.test(actual)) {
    const optionIndex = actual.charCodeAt(0) - 'a'.charCodeAt(0);
    if (question.options?.[optionIndex]) {
      actual = normalizeAnswer(question.options[optionIndex]);
    }
  }

  if (question.type === 'math_problem') {
    return numericValue(actual) === numericValue(expected);
  }

  if (question.type === 'rearrange') {
    return actual === expected;
  }

  return actual === expected || actual.includes(expected) || expected.includes(actual);
}

export function createPracticeSession(questions, passingScore = 70) {
  if (!questions.length) throw new Error('Practice session requires at least one question.');

  const queue = questions.map((_, index) => index);
  const mastered = questions.map(() => false);
  const session = {
    questions,
    passingScore,
    masteryPercent: 0,
    isComplete: false,
    currentQuestion: questions[queue[0]],
    answer(response) {
      if (this.isComplete) {
        return { isCorrect: true, expectedAnswer: '', message: 'Practice is already complete.' };
      }

      const questionIndex = queue.shift();
      const question = questions[questionIndex];
      const isCorrect = answerMatches(question, response);
      mastered[questionIndex] = isCorrect;
      if (!isCorrect) queue.push(questionIndex);

      this.masteryPercent = Math.round((mastered.filter(Boolean).length / mastered.length) * 100);
      this.isComplete = this.masteryPercent >= passingScore && mastered.every(Boolean);
      if (!this.isComplete && queue.length) {
        this.currentQuestion = questions[queue[0]];
      }

      return {
        isCorrect,
        expectedAnswer: question.answer,
        message: isCorrect ? 'Correct.' : `Review this again. Expected: ${question.answer}`,
      };
    },
  };

  return session;
}

export function createTimedQuizSession(questions) {
  if (!questions.length) throw new Error('Timed quiz requires at least one question.');

  const answers = [];
  return {
    questions,
    currentIndex: 0,
    get currentQuestion() {
      return this.questions[this.currentIndex] ?? null;
    },
    get isComplete() {
      return this.currentIndex >= this.questions.length;
    },
    answer(response, elapsedSeconds) {
      if (this.isComplete) {
        return { isCorrect: true, expectedAnswer: '', message: 'Quiz is already complete.' };
      }
      const question = this.currentQuestion;
      const isCorrect = Boolean(String(response).trim()) && answerMatches(question, response);
      answers.push({ question, response, isCorrect, elapsedSeconds: Math.max(0, Number(elapsedSeconds) || 0) });
      this.currentIndex += 1;
      return {
        isCorrect,
        expectedAnswer: question.answer,
        message: isCorrect ? 'Correct.' : `Incorrect. Expected: ${question.answer}`,
      };
    },
    summary() {
      const correctCount = answers.filter((answer) => answer.isCorrect).length;
      const totalCount = questions.length;
      const scorePercent = Math.round((correctCount / totalCount) * 100);
      return {
        correctCount,
        totalCount,
        scorePercent,
        masteryPercent: scorePercent,
        elapsedSeconds: answers.reduce((sum, answer) => sum + answer.elapsedSeconds, 0),
      };
    },
  };
}

function buildQuizQuestion(concept, concepts, index) {
  const type = QUESTION_TYPES[index % QUESTION_TYPES.length];
  const timerSeconds = 20 + (index % 5) * 10;

  if (type === 'mcq') {
    return {
      prompt: `Which option best matches this study concept: ${concept}?`,
      answer: concept,
      type,
      timerSeconds,
      options: makeOptions(concept, concepts, index),
    };
  }

  if (type === 'fill_in') {
    return {
      prompt: 'Fill in the blank: _____ is one of the key concepts from this material.',
      answer: concept,
      type,
      timerSeconds,
      options: [],
    };
  }

  if (type === 'rearrange') {
    const phrase = concept.split(' ').length >= 2 ? concept : `key idea ${concept}`;
    return {
      prompt: `Rearrange these words into the correct phrase: ${phrase.split(' ').reverse().join(' / ')}`,
      answer: phrase,
      type,
      timerSeconds,
      options: [],
    };
  }

  const minutesEach = 5 + index;
  const conceptCount = Math.min(concepts.length, 6);
  return {
    prompt: `Math problem: If you spend ${minutesEach} minutes reviewing each of ${conceptCount} concepts, how many minutes is that in total?`,
    answer: String(minutesEach * conceptCount),
    type: 'math_problem',
    timerSeconds,
    options: [],
  };
}

function prepareConcepts(concepts) {
  const clean = [];
  const seen = new Set();
  for (const concept of concepts) {
    const item = String(concept).replace(/\s+/g, ' ').replace(/[ .,:;]+$/g, '').trim();
    const key = item.toLowerCase();
    if (item && !seen.has(key)) {
      clean.push(item);
      seen.add(key);
    }
  }
  return clean.length ? clean : ['main idea', 'definition', 'example', 'process', 'application'];
}

function cycleTake(items, count) {
  return Array.from({ length: count }, (_, index) => items[index % items.length]);
}

function makeOptions(answer, concepts, seed) {
  const distractors = concepts.filter((concept) => concept.toLowerCase() !== answer.toLowerCase());
  while (distractors.length < 3) distractors.push(`related idea ${distractors.length + 1}`);
  const options = [answer, ...distractors.slice(0, 3)];
  return seededShuffle(options, seed);
}

function seededShuffle(items, seed) {
  const result = [...items];
  let state = seed + 1;
  for (let index = result.length - 1; index > 0; index -= 1) {
    state = (state * 1664525 + 1013904223) % 4294967296;
    const swapIndex = state % (index + 1);
    [result[index], result[swapIndex]] = [result[swapIndex], result[index]];
  }
  return result;
}

function normalizeAnswer(value) {
  return String(value ?? '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9.\- ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function numericValue(value) {
  const match = String(value).match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function cleanText(text) {
  return String(text ?? '')
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, Number(value) || low));
}
