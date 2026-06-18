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

const BOUNDARY_WORDS = new Set([
  ...STOP_WORDS,
  'absorbs',
  'allows',
  'can',
  'causes',
  'convert',
  'converts',
  'create',
  'creates',
  'describe',
  'describes',
  'explain',
  'explains',
  'include',
  'includes',
  'make',
  'makes',
  'mean',
  'means',
  'provide',
  'provides',
  'show',
  'shows',
  'support',
  'supports',
  'use',
  'used',
]);

const WEAK_SINGLE_WORDS = new Set([
  'application',
  'cells',
  'concept',
  'concepts',
  'definition',
  'energy',
  'example',
  'growth',
  'idea',
  'ideas',
  'material',
  'method',
  'notes',
  'process',
  'production',
  'purpose',
  'release',
  'source',
  'study',
  'system',
  'term',
  'terms',
  'thing',
  'things',
  'topic',
  'topics',
]);

const ACRONYMS = new Set(['atp', 'dna', 'rna', 'html', 'css', 'api', 'cpu', 'gpu', 'pdf']);
const QUESTION_TYPES = ['mcq', 'fill_in', 'rearrange', 'math_problem'];
const POPULATION_GROUP_HEADINGS = new Set(['population', 'finite population', 'infinite population', 'sample', 'sampling unit', 'sampling frame']);

export function extractKeyConcepts(text, { minimum = 5, maximum = 24 } = {}) {
  return extractKeyConceptDetails(text, { minimum, maximum }).map((concept) => concept.title);
}

export function extractStudyBlocks(text, { minimum = 5, maximum = 24 } = {}) {
  const blocks = extractStructuredStudyBlocks(text);
  if (!blocks.length) {
    const seen = new Set(blocks.map((block) => block.title.toLowerCase()));
    for (const concept of extractKeyConceptDetails(text, { minimum, maximum })) {
      if (seen.has(concept.title.toLowerCase())) continue;
      blocks.push({
        title: concept.title,
        type: 'concept',
        summary: concept.explanation,
        items: [],
        sourceExcerpt: concept.sourceSentence,
      });
      seen.add(concept.title.toLowerCase());
    }
  }
  return blocks.slice(0, maximum);
}

export function extractKeyConceptDetails(text, { minimum = 5, maximum = 24 } = {}) {
  const cleaned = cleanText(text);
  const sentences = splitSentences(cleaned);
  if (!sentences.length) return [];

  const allWords = [];
  for (const sentence of sentences) {
    const words = Array.from(sentence.toLowerCase().matchAll(/[a-z][a-z0-9'-]{1,}/g), (match) => match[0]).filter(
      (word) => !/^\d+$/.test(word),
    );
    allWords.push(...words.filter((word) => !STOP_WORDS.has(word)));
  }
  if (!allWords.length) return [];

  const wordCounts = new Map();
  allWords.forEach((word) => wordCounts.set(word, (wordCounts.get(word) ?? 0) + 1));

  const candidates = new Map();
  const firstSeen = new Map();
  const candidateSentence = new Map();

  sentences.forEach((sentence, sentenceIndex) => {
    const fragments = sentence.split(/[,;:()]|\b(?:and|or)\b/i);
    for (const fragment of fragments) {
      const words = Array.from(fragment.toLowerCase().matchAll(/[a-z][a-z0-9'-]{1,}/g), (match) => match[0]);
      const segments = [];
      let current = [];
      for (const word of words) {
        if (BOUNDARY_WORDS.has(word)) {
          if (current.length) segments.push(current);
          current = [];
        } else {
          current.push(word);
        }
      }
      if (current.length) segments.push(current);
      segments.forEach((segment) => addCandidatesFromSegment(segment, sentenceIndex, sentences, wordCounts, firstSeen, candidateSentence, candidates));
    }
  });

  const ranked = Array.from(candidates.keys()).sort((left, right) => {
    const scoreDiff = candidates.get(right) - candidates.get(left);
    if (scoreDiff) return scoreDiff;
    const positionDiff = firstSeen.get(left) - firstSeen.get(right);
    if (positionDiff) return positionDiff;
    return left.localeCompare(right);
  });
  const multiwordCandidateParts = new Set(
    ranked.flatMap((candidate) => {
      const parts = candidate.split(' ');
      return parts.length > 1 ? parts : [];
    }),
  );

  const selected = [];
  for (const candidate of ranked) {
    if (candidate.split(' ').length === 1 && multiwordCandidateParts.has(candidate)) continue;
    if (isRedundantCandidate(candidate, selected)) continue;
    selected.push(candidate);
    if (selected.length >= maximum) break;
  }

  if (selected.length < minimum) {
    const fallbackWords = Array.from(wordCounts.keys()).sort((left, right) => {
      const countDiff = wordCounts.get(right) - wordCounts.get(left);
      if (countDiff) return countDiff;
      return left.localeCompare(right);
    });
    for (const word of fallbackWords) {
      if (validCandidate([word]) && !selected.includes(word)) selected.push(word);
      if (selected.length >= Math.min(minimum, maximum)) break;
    }
  }

  return selected.slice(0, maximum).map((candidate) => ({
    title: formatConceptTitle(candidate),
    explanation: buildExplanation(candidate, candidateSentence.get(candidate) || ''),
    sourceSentence: candidateSentence.get(candidate) || '',
  }));
}

function extractStructuredStudyBlocks(text) {
  const entries = extractHeadingEntries(text);
  const blocks = [];
  const used = new Set();
  const populationBlock = populationSamplingBlock(entries);
  let populationIndex = null;
  if (populationBlock) {
    entries.forEach(([heading], index) => {
      if (POPULATION_GROUP_HEADINGS.has(normalizeHeading(heading))) {
        used.add(index);
        if (populationIndex === null) populationIndex = index;
      }
    });
  }

  entries.forEach(([heading, body], index) => {
    if (populationBlock && index === populationIndex) blocks.push(populationBlock);
    if (used.has(index)) return;
    const block = entryToStudyBlock(heading, body);
    if (block) blocks.push(block);
  });
  return dedupeStudyBlocks(blocks);
}

export function generateStudySet(concepts, { cardCount = 10, quizCount = 12, sourceText = '' } = {}) {
  const prepared = prepareConceptRecords(concepts, sourceText);
  const conceptTitles = prepared.map((concept) => concept.title);
  const flashcardTotal = clamp(cardCount, 5, Math.max(5, prepared.length));
  const quizTotal = clamp(quizCount, 10, 15);

  const flashcards = cycleTake(prepared, flashcardTotal).map((concept) => ({
    question: `What does ${concept.title} mean in this material?`,
    answer: composeFlashcardAnswer(concept),
    concept: concept.title,
  }));

  const practiceQuestions = cycleTake(prepared, Math.max(5, Math.min(prepared.length, 12))).map((concept) => ({
    prompt: composePracticePrompt(concept),
    answer: concept.title,
    concept: concept.title,
  }));

  const quizQuestions = cycleTake(prepared, quizTotal).map((concept, index) => buildQuizQuestion(concept, conceptTitles, index));

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
    const clue = concept.sourceSentence || concept.explanation || concept.title;
    return {
      prompt: `Which concept is described by this source clue: ${clue}`,
      answer: concept.title,
      type,
      timerSeconds,
      options: makeOptions(concept.title, concepts, index),
    };
  }

  if (type === 'fill_in') {
    return {
      prompt: fillInPrompt(concept),
      answer: concept.title,
      type,
      timerSeconds,
      options: [],
    };
  }

  if (type === 'rearrange') {
    const phrase = concept.title.split(' ').length >= 2 ? concept.title : `key idea ${concept.title}`;
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
  return prepareConceptRecords(concepts).map((concept) => concept.title);
}

function extractHeadingEntries(text) {
  const lines = studyLines(text);
  const entries = [];
  let currentHeading = '';
  let currentBody = [];
  let previousBlank = true;
  for (const line of lines) {
    if (!line) {
      previousBlank = true;
      continue;
    }
    if (isLectureMarker(line)) {
      previousBlank = true;
      continue;
    }
    const [heading, rest] = splitHeadingLine(line);
    if (heading && currentHeading && !previousBlank && isDetailLabel(heading)) {
      currentBody.push(line);
    } else if (heading) {
      if (currentHeading) entries.push([currentHeading, currentBody.join(' ').trim()]);
      currentHeading = heading;
      currentBody = rest ? [rest] : [];
    } else if (previousBlank && isStudyHeading(line)) {
      if (currentHeading) entries.push([currentHeading, currentBody.join(' ').trim()]);
      currentHeading = line;
      currentBody = [];
    } else if (currentHeading) {
      currentBody.push(line);
    }
    previousBlank = false;
  }
  if (currentHeading) entries.push([currentHeading, currentBody.join(' ').trim()]);
  return entries;
}

function studyLines(text) {
  return cleanText(text)
    .split('\n')
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter((line) => !line || !isNoiseLine(line));
}

function splitHeadingLine(line) {
  if (line.length > 180 || !line.includes(':')) return ['', ''];
  const colon = line.indexOf(':');
  const heading = line.slice(0, colon).trim();
  const rest = line.slice(colon + 1).trim();
  return isStudyHeading(heading) ? [heading, rest] : ['', ''];
}

function isStudyHeading(heading) {
  const normalized = normalizeHeading(heading);
  if (['lecture', 'example', 'solution', 'step'].includes(normalized) || normalized.startsWith('step ')) return true;
  return /^[A-Z][A-Za-z0-9 &/().-]{2,85}$/.test(heading) && !/^(as for example|for example|following)/i.test(heading);
}

function isDetailLabel(heading) {
  return ['technique', 'techniques', 'example', 'examples', 'note', 'notes'].includes(normalizeHeading(heading));
}

function entryToStudyBlock(heading, body) {
  if (!body) return null;
  const normalized = normalizeHeading(heading);
  const items = extractListItems(body);
  if (normalized.startsWith('definition of ') || normalized.startsWith('definitions of ')) {
    const prefixLength = normalized.startsWith('definitions of ') ? 'Definitions of '.length : 'Definition of '.length;
    const subject = titleCase(heading.slice(prefixLength));
    return {
      title: `Definitions of ${subject}`,
      type: 'definition',
      summary: definitionSummary(subject, body),
      items: techniqueItems(body).length ? techniqueItems(body) : items,
      sourceExcerpt: sourceExcerpt(heading, body),
    };
  }
  if (normalized.startsWith('importance of ')) {
    return { title: titleCase(heading), type: 'list', summary: firstSentence(body), items: items.length ? items : sentenceItems(body), sourceExcerpt: sourceExcerpt(heading, body) };
  }
  if (
    normalized.startsWith('methods of ') ||
    normalized.startsWith('types of ') ||
    normalized.startsWith('use of ') ||
    normalized.startsWith('basic principle')
  ) {
    return { title: titleCase(heading), type: 'list', summary: firstSentence(body), items, sourceExcerpt: sourceExcerpt(heading, body) };
  }
  if (normalized.startsWith('constructing ') || normalized.startsWith('steps for ')) {
    return { title: titleCase(heading), type: 'steps', summary: firstSentence(body), items, sourceExcerpt: sourceExcerpt(heading, body) };
  }
  if (looksLikeDefinition(heading, body)) {
    return { title: titleCase(heading), type: 'definition', summary: definitionSummary(heading, body), items, sourceExcerpt: sourceExcerpt(heading, body) };
  }
  if (items.length) return { title: titleCase(heading), type: 'list', summary: firstSentence(body), items, sourceExcerpt: sourceExcerpt(heading, body) };
  return null;
}

function sentenceItems(body) {
  return splitSentences(body)
    .map((sentence) => cleanItem(sentence))
    .filter((sentence) => sentence.length >= 8);
}

function populationSamplingBlock(entries) {
  const found = new Map();
  const excerpts = [];
  for (const [heading, body] of entries) {
    const normalized = normalizeHeading(heading);
    if (POPULATION_GROUP_HEADINGS.has(normalized)) {
      found.set(normalized, body);
      excerpts.push(sourceExcerpt(heading, body));
    }
  }
  if (!found.has('population') || !found.has('sample') || !found.has('sampling frame')) return null;
  const items = [];
  if (found.has('population')) items.push('Population -> Entire group under study.');
  if (found.has('finite population')) items.push('Finite population -> Countable units.');
  if (found.has('infinite population')) items.push('Infinite population -> Uncountable units.');
  if (found.has('sample')) items.push('Sample -> Representative part of population.');
  if (found.has('sampling unit')) items.push('Sampling unit -> Smallest unit information is collected from.');
  if (found.has('sampling frame')) items.push('Sampling frame -> List of all population units.');
  return {
    title: 'Population & Sampling',
    type: 'grouped_definitions',
    summary: 'Core population and sampling terms used to define what is studied and what information is collected.',
    items,
    sourceExcerpt: excerpts.join(' ').slice(0, 900),
  };
}

function prepareConceptRecords(concepts, sourceText = '') {
  const clean = [];
  const seen = new Set();
  for (const concept of concepts) {
    const record = coerceConceptRecord(concept, sourceText);
    const key = record.title.toLowerCase();
    if (record.title && !seen.has(key)) {
      clean.push(record);
      seen.add(key);
    }
  }
  return clean.length
    ? clean
    : [
        { title: 'main idea', explanation: 'Review the main idea from the source material.', sourceSentence: '' },
        { title: 'definition', explanation: 'Review the definition from the source material.', sourceSentence: '' },
        { title: 'example', explanation: 'Review an example from the source material.', sourceSentence: '' },
        { title: 'process', explanation: 'Review the process described in the source material.', sourceSentence: '' },
        { title: 'application', explanation: 'Review how the material can be applied.', sourceSentence: '' },
      ];
}

function coerceConceptRecord(concept, sourceText = '') {
  let title = '';
  let explanation = '';
  let sourceSentence = '';
  let items = [];
  let blockType = 'concept';

  if (concept && typeof concept === 'object') {
    title = cleanConceptTitle(concept.title || concept.concept || concept.name);
    explanation = String(concept.summary || concept.explanation || '').trim();
    sourceSentence = String(concept.sourceExcerpt || concept.sourceSentence || concept.source_sentence || '').trim();
    items = Array.isArray(concept.items) ? concept.items.map((item) => String(item).trim()).filter(Boolean) : [];
    blockType = String(concept.type || concept.block_type || 'concept').trim() || 'concept';
  } else {
    title = cleanConceptTitle(concept);
  }

  if (!sourceSentence && sourceText && title) sourceSentence = findSourceSentence(title, sourceText);
  if (!explanation && sourceSentence) explanation = `${title}: ${sourceSentence.replace(/[.!?]+$/g, '')}.`;
  if (!explanation && title) explanation = `${title}: review this concept in the source material.`;
  return { title, explanation, sourceSentence, items, type: blockType };
}

function cleanConceptTitle(value) {
  return String(value ?? '')
    .replace(/\s+/g, ' ')
    .replace(/[ .,:;]+$/g, '')
    .trim();
}

function composeFlashcardAnswer(concept) {
  if (concept.items?.length) {
    const seen = new Set();
    const summary = concept.explanation.replace(/[.!?]+$/g, '');
    return [summary.length <= 220 ? summary : '', ...concept.items]
      .filter((line) => {
        const normalized = String(line || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
        if (!normalized || seen.has(normalized)) return false;
        seen.add(normalized);
        return true;
      })
      .slice(0, 6)
      .map((line) => (/[.!?]$/.test(line) ? line : `${line}.`))
      .join('\n');
  }
  if (concept.sourceSentence) {
    const source = concept.sourceSentence.replace(/[.!?]+$/g, '');
    return sameTitlePrefix(source, concept.title) ? `${source}.` : `${concept.title}: ${source}.`;
  }
  return concept.explanation || `${concept.title}: review this concept in the source material.`;
}

function sameTitlePrefix(text, title) {
  const normalize = (value) =>
    String(value || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .replace(/\bdefinitions?\b/g, 'definition')
      .trim();
  const normalizedText = normalize(text);
  const normalizedTitle = normalize(title);
  return normalizedText.startsWith(normalizedTitle) || normalizedText.startsWith(normalizedTitle.replace(/s$/, ''));
}

function composePracticePrompt(concept) {
  if (concept.sourceSentence) return `In your own words, explain ${concept.title} using this source clue: ${concept.sourceSentence}`;
  return `In your own words, explain ${concept.title}.`;
}

function fillInPrompt(concept) {
  if (concept.sourceSentence) {
    const pattern = new RegExp(escapeRegExp(concept.title), 'i');
    const clue = concept.sourceSentence.replace(pattern, '_____');
    if (clue !== concept.sourceSentence) return `Fill in the blank from the source: ${clue}`;
  }
  return 'Fill in the blank: _____ is one of the key concepts from this material.';
}

function findSourceSentence(title, sourceText) {
  const sentences = splitSentences(sourceText);
  const phrasePattern = new RegExp(`\\b${escapeRegExp(title)}\\b`, 'i');
  for (const sentence of sentences) {
    if (phrasePattern.test(sentence)) return sentence;
  }
  const words = title
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => new RegExp(`\\b${escapeRegExp(word)}\\b`, 'i'));
  return sentences.find((sentence) => words.every((pattern) => pattern.test(sentence))) || '';
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

function extractListItems(body) {
  const definitionMatches = Array.from(
    body.matchAll(/([A-Z][A-Za-z ]{2,60})\s*(?:->|→|:)\s*(.+?)(?=\s+[A-Z][A-Za-z ]{2,60}\s*(?:->|→|:)|$)/g),
    (match) => cleanItem(`${match[1].trim()} -> ${match[2].trim()}`),
  ).filter(Boolean);
  if (definitionMatches.length >= 2) return definitionMatches;

  const techniqueMatches = techniqueItems(body);
  if (techniqueMatches.length >= 2) return techniqueMatches;
  const bulletMatches = Array.from(body.matchAll(/(?:^|\s)[•\-]\s+([^•\-]+?)(?=(?:\s[•\-]\s+)|$)/g), (match) => cleanItem(match[1])).filter(Boolean);
  if (bulletMatches.length) return bulletMatches;
  const letterMatches = Array.from(
    body.matchAll(/(?:^|\s)(\([a-zivx]+\)|[a-zivx]+\))\s+(.+?)(?=(?:\s(?:\([a-zivx]+\)|[a-zivx]+\))\s+)|$)/gi),
    (match) => cleanItem(match[2]),
  ).filter(Boolean);
  if (letterMatches.length >= 2) return letterMatches;
  return Array.from(body.matchAll(/(Step\s+\d+)\s*:\s*(.+?)(?=(?:\sStep\s+\d+\s*:)|$)/gi), (match) => cleanItem(`${match[1]}: ${match[2]}`)).filter(Boolean);
}

function techniqueItems(body) {
  const match = body.match(/techniques?(?:\s+such\s+as|:)\s+(.+?)(?:\s+to\s+|\.)/i);
  if (!match) return [];
  return match[1]
    .split(/,|\band\b/i)
    .map((item) => sentenceCase(item.trim().toLowerCase()))
    .filter(Boolean);
}

function definitionSummary(_title, body) {
  const text = firstSentence(body);
  for (const pattern of [/may be defined as\s+(.+)/i, /is known as\s+(.+)/i, /is\s+(.+)/i]) {
    const match = text.match(pattern);
    if (match) return sentenceCase(stripLeadingArticle(cleanItem(match[1])));
  }
  return sentenceCase(cleanItem(text));
}

function looksLikeDefinition(_heading, body) {
  return body.length >= 20 && /(known as|defined as|is a|is an|is the|refers to)/i.test(body);
}

function firstSentence(text) {
  return cleanItem(String(text || '').replace(/\s+/g, ' ').trim().split(/(?<=[.!?])\s+/)[0] || '');
}

function cleanItem(item) {
  const cleaned = String(item || '').replace(/\s+/g, ' ').trim().replace(/[.;:]+$/g, '');
  return cleaned && !/[.!?]$/.test(cleaned) ? `${cleaned}.` : cleaned;
}

function sentenceCase(item) {
  const value = String(item || '').trim();
  return value ? `${value.slice(0, 1).toUpperCase()}${value.slice(1)}` : value;
}

function stripLeadingArticle(item) {
  return String(item || '').trim().replace(/^(an?|the)\s+/i, '');
}

function titleCase(value) {
  const smallWords = new Set(['and', 'or', 'of', 'in', 'to', 'for', 'the', 'a', 'an']);
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[.:]+$/g, '')
    .split(' ')
    .map((word, index) => {
      const lower = word.toLowerCase();
      if (ACRONYMS.has(lower)) return lower.toUpperCase();
      if (index && smallWords.has(lower)) return lower;
      return `${lower.slice(0, 1).toUpperCase()}${lower.slice(1)}`;
    })
    .join(' ');
}

function sourceExcerpt(heading, body) {
  return `${heading}: ${body}`.trim().slice(0, 900);
}

function normalizeHeading(heading) {
  return String(heading || '').replace(/\s+/g, ' ').trim().replace(/[.:]+$/g, '').replace(/\s+\d+$/g, '').toLowerCase();
}

function isLectureMarker(line) {
  return /^(Chapter|Lecture|Slide)\s+\d+\s*:?/i.test(line);
}

function isNoiseLine(line) {
  return (
    line === 'Introduction to Statistics and Data Science' ||
    line === 'Professor, Department of SDS' ||
    /^Dr\.?\s+Mohd\.?\s+Muzibur\s+Rahman\b/i.test(line) ||
    /^\d+$/.test(line)
  );
}

function dedupeStudyBlocks(blocks) {
  const seen = new Set();
  const result = [];
  for (const block of blocks) {
    const key = block.title.toLowerCase();
    if (seen.has(key) || (!block.summary && !block.items?.length)) continue;
    result.push(block);
    seen.add(key);
  }
  return result;
}

function splitSentences(text) {
  const normalized = cleanText(text).replace(/\s+/g, ' ').trim();
  if (!normalized) return [];
  return normalized.split(/(?<=[.!?])\s+/).filter((sentence) => sentence.trim().length >= 8);
}

function addCandidatesFromSegment(segment, sentenceIndex, sentences, wordCounts, firstSeen, candidateSentence, candidates) {
  for (let start = 0; start < segment.length; start += 1) {
    for (let size = 1; size <= Math.min(4, segment.length - start); size += 1) {
      const parts = segment.slice(start, start + size);
      if (!validCandidate(parts)) continue;
      const key = parts.join(' ');
      if (!firstSeen.has(key)) firstSeen.set(key, firstSeen.size);
      if (!candidateSentence.has(key)) candidateSentence.set(key, sentences[sentenceIndex]);
      const score = candidateScore(parts, wordCounts, start === 0);
      candidates.set(key, candidates.has(key) ? candidates.get(key) + 3 : score);
    }
  }
}

function validCandidate(parts) {
  if (!parts.length || new Set(parts).size !== parts.length) return false;
  if (parts.some((part) => STOP_WORDS.has(part))) return false;
  if (parts.length === 1) {
    const [word] = parts;
    return !WEAK_SINGLE_WORDS.has(word) && word.length >= 4;
  }
  if (WEAK_SINGLE_WORDS.has(parts[0])) return false;
  return !parts.every((part) => WEAK_SINGLE_WORDS.has(part));
}

function candidateScore(parts, wordCounts, startsSegment) {
  if (parts.length === 1) {
    const [word] = parts;
    return (wordCounts.get(word) ?? 0) * 12 + Math.min(word.length, 18) / 2 + (startsSegment ? 8 : 0);
  }
  const repeatedWordBonus = parts.filter((word) => (wordCounts.get(word) ?? 0) > 1).length * 2;
  const acronymBonus = parts.some((word) => ACRONYMS.has(word)) ? 4 : 0;
  return 16 + parts.length * 5 + repeatedWordBonus + acronymBonus + (startsSegment ? 4 : 0);
}

function isRedundantCandidate(candidate, selected) {
  const candidateParts = new Set(candidate.split(' '));
  return selected.some((existing) => {
    const existingParts = new Set(existing.split(' '));
    if (candidateParts.size === existingParts.size && [...candidateParts].every((part) => existingParts.has(part))) return true;
    return candidateParts.size === 1 && existingParts.has(candidate);
  });
}

function formatConceptTitle(candidate) {
  return candidate
    .split(' ')
    .map((word) => (ACRONYMS.has(word) ? word.toUpperCase() : word))
    .join(' ');
}

function buildExplanation(candidate, sentence) {
  const title = formatConceptTitle(candidate);
  if (sentence) return `${title}: ${sentence.replace(/[.!?]+$/g, '')}.`;
  return `${title}: review this concept in the source material.`;
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

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, Number(value) || low));
}
