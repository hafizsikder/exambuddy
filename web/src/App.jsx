import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  BookOpen,
  Brain,
  CheckCircle2,
  FileText,
  Link as LinkIcon,
  LogOut,
  Play,
  RefreshCcw,
  Send,
  Sparkles,
  Timer,
  Upload,
} from 'lucide-react';
import { createPracticeSession, createTimedQuizSession } from './lib/study.js';

const THEMES = {
  anime: {
    label: 'Anime',
    banner: '/theme-assets/anime-study-banner.png',
    bg: '#fff7fb',
    panel: '#ffffff',
    text: '#202233',
    muted: '#62677a',
    border: '#f0dce9',
    accent: '#ff5f9f',
    accentText: '#ffffff',
    second: '#2eb7e8',
    third: '#e5b318',
  },
  floral: {
    label: 'Floral',
    banner: '/theme-assets/floral-study-banner.png',
    bg: '#f6fbf3',
    panel: '#ffffff',
    text: '#253126',
    muted: '#66715f',
    border: '#dcebd7',
    accent: '#3c8f64',
    accentText: '#ffffff',
    second: '#d86f91',
    third: '#be8d1d',
  },
  game: {
    label: 'Game-style',
    banner: '/theme-assets/game-study-banner.png',
    bg: '#111820',
    panel: '#1d2833',
    text: '#f4f7fb',
    muted: '#aeb9c4',
    border: '#334455',
    accent: '#00d084',
    accentText: '#071017',
    second: '#ffb000',
    third: '#49a6ff',
  },
};

const API = {
  async parseText(text) {
    return request('/api/parse-text', { method: 'POST', json: { text } });
  },
  async parseLink(url) {
    return request('/api/parse-link', { method: 'POST', json: { url } });
  },
  async parseFile(file) {
    const body = new FormData();
    body.append('file', file);
    return request('/api/parse-file', { method: 'POST', body });
  },
  async generate(payload) {
    return request('/api/generate', { method: 'POST', json: payload });
  },
};

export default function App() {
  const [themeName, setThemeName] = useState('anime');
  const theme = THEMES[themeName];
  const [status, setStatus] = useState('Ready');
  const [isBusy, setIsBusy] = useState(false);
  const [useAi, setUseAi] = useState(false);
  const [cardCount, setCardCount] = useState(8);
  const [quizCount, setQuizCount] = useState(12);
  const [url, setUrl] = useState('');
  const [pastedText, setPastedText] = useState('');
  const [source, setSource] = useState(null);
  const [studySet, setStudySet] = useState(null);
  const [provider, setProvider] = useState('');
  const [mode, setMode] = useState('source');
  const [feedback, setFeedback] = useState('');
  const [flashIndex, setFlashIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [answer, setAnswer] = useState('');
  const [practiceTick, setPracticeTick] = useState(0);
  const practiceRef = useRef(null);
  const quizRef = useRef(null);
  const [quizTick, setQuizTick] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const questionStartedAt = useRef(0);

  useEffect(() => {
    document.documentElement.dataset.theme = themeName;
  }, [themeName]);

  useEffect(() => {
    const quiz = quizRef.current;
    if (mode !== 'test' || !quiz || quiz.isComplete) return undefined;
    const currentQuestion = quiz.currentQuestion;
    questionStartedAt.current = Date.now();
    setRemaining(currentQuestion.timerSeconds);
    const interval = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - questionStartedAt.current) / 1000);
      const nextRemaining = Math.max(0, currentQuestion.timerSeconds - elapsed);
      setRemaining(nextRemaining);
      if (nextRemaining <= 0) {
        window.clearInterval(interval);
        submitQuizAnswer(true);
      }
    }, 250);
    return () => window.clearInterval(interval);
  }, [mode, quizTick]);

  const currentCard = studySet?.flashcards?.[flashIndex];
  const practiceSession = practiceRef.current;
  const quizSession = quizRef.current;
  const quizQuestion = quizSession?.currentQuestion;
  const mastery = practiceSession?.masteryPercent ?? 0;

  const conceptsPreview = useMemo(() => source?.studyBlocks?.slice(0, 18) ?? source?.conceptDetails?.slice(0, 18) ?? source?.concepts?.slice(0, 18) ?? [], [source]);

  async function runJob(message, job, onDone) {
    setIsBusy(true);
    setStatus(message);
    setFeedback('');
    try {
      const result = await job();
      onDone(result);
    } catch (error) {
      setFeedback(error.message);
      setStatus('Needs attention');
    } finally {
      setIsBusy(false);
    }
  }

  function acceptSource(parsed) {
    setSource(parsed);
    setStudySet(null);
    setProvider('');
    setMode('source');
    setStatus(`${parsed.title} loaded`);
  }

  function parseFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    runJob('Parsing file', () => API.parseFile(file), acceptSource);
    event.target.value = '';
  }

  function parsePastedText() {
    if (!pastedText.trim()) {
      setFeedback('Paste study text first.');
      return;
    }
    runJob('Parsing text', () => API.parseText(pastedText), acceptSource);
  }

  function parseLink() {
    if (!url.trim()) {
      setFeedback('Paste a web link first.');
      return;
    }
    runJob('Parsing link', () => API.parseLink(url), acceptSource);
  }

  async function startMode(nextMode) {
    if (!source) {
      setFeedback('Add study material first.');
      return;
    }
    if (studySet) {
      openMode(nextMode, studySet);
      return;
    }
    await runJob(
      useAi ? 'Generating with AI' : 'Generating locally',
      () =>
        API.generate({
          concepts: source.studyBlocks?.length ? source.studyBlocks : source.conceptDetails?.length ? source.conceptDetails : source.concepts,
          sourceText: source.text,
          cardCount,
          quizCount,
          useAi,
        }),
      (result) => {
        setStudySet(result.studySet);
        setProvider(result.provider);
        openMode(nextMode, result.studySet);
      },
    );
  }

  function openMode(nextMode, nextStudySet) {
    setFeedback('');
    if (nextMode === 'cards') {
      setFlashIndex(0);
      setShowAnswer(false);
    }
    if (nextMode === 'practice') {
      practiceRef.current = createPracticeSession(nextStudySet.practiceQuestions);
      setAnswer('');
      setPracticeTick((value) => value + 1);
    }
    if (nextMode === 'test') {
      quizRef.current = createTimedQuizSession(nextStudySet.quizQuestions);
      setAnswer('');
      setQuizTick((value) => value + 1);
    }
    setMode(nextMode);
    setStatus(modeLabel(nextMode));
  }

  function studyAgain() {
    setMode(source ? 'source' : 'welcome');
    setFeedback('');
    setAnswer('');
    setShowAnswer(false);
    practiceRef.current = null;
    quizRef.current = null;
    setStatus(source ? 'Ready' : 'Add a source');
  }

  function submitPracticeAnswer(event) {
    event?.preventDefault();
    const session = practiceRef.current;
    if (!session || session.isComplete) return;
    const result = session.answer(answer);
    setFeedback(result.message);
    setAnswer('');
    setPracticeTick((value) => value + 1);
  }

  function submitQuizAnswer(auto = false) {
    const session = quizRef.current;
    if (!session || session.isComplete) return;
    const question = session.currentQuestion;
    const elapsed = Math.min(question.timerSeconds, Math.floor((Date.now() - questionStartedAt.current) / 1000));
    session.answer(auto ? '' : answer, elapsed);
    setAnswer('');
    setQuizTick((value) => value + 1);
  }

  function exitApp() {
    window.close();
    setStatus('Exit requested');
  }

  return (
    <main
      className="app-shell"
      style={{
        '--bg': theme.bg,
        '--panel': theme.panel,
        '--text': theme.text,
        '--muted': theme.muted,
        '--border': theme.border,
        '--accent': theme.accent,
        '--accent-text': theme.accentText,
        '--second': theme.second,
        '--third': theme.third,
      }}
    >
      <section className="banner" aria-label={`${theme.label} theme`}>
        <img src={theme.banner} alt="" />
        <div className="banner-overlay">
          <div>
            <p className="eyebrow">Exam Buddy Web</p>
            <h1>Study console</h1>
          </div>
          <div className="status-chip">
            <CheckCircle2 size={18} />
            <span>{status}</span>
          </div>
        </div>
      </section>

      <section className="toolbar" aria-label="Study controls">
        <div className="theme-tabs" role="tablist" aria-label="Theme">
          {Object.entries(THEMES).map(([key, item]) => (
            <button key={key} className={key === themeName ? 'selected' : ''} onClick={() => setThemeName(key)} type="button">
              {item.label}
            </button>
          ))}
        </div>
        <label className="toggle">
          <input type="checkbox" checked={useAi} onChange={(event) => setUseAi(event.target.checked)} />
          <Sparkles size={17} />
          <span>Use AI</span>
        </label>
        <label className="number-field">
          <span>Cards</span>
          <input type="number" min="5" max="30" value={cardCount} onChange={(event) => setCardCount(Number(event.target.value))} />
        </label>
        <label className="number-field">
          <span>Quiz</span>
          <input type="number" min="10" max="15" value={quizCount} onChange={(event) => setQuizCount(Number(event.target.value))} />
        </label>
      </section>

      <section className="workspace">
        <aside className="source-panel">
          <div className="panel-title">
            <FileText size={18} />
            <h2>Source</h2>
          </div>

          <label className="upload-button">
            <Upload size={18} />
            <span>Upload PDF / PPTX</span>
            <input type="file" accept=".pdf,.pptx,.txt,.md" onChange={parseFile} disabled={isBusy} />
          </label>

          <div className="field-row">
            <LinkIcon size={18} />
            <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://..." disabled={isBusy} />
            <button type="button" onClick={parseLink} disabled={isBusy} aria-label="Parse link">
              <Send size={18} />
            </button>
          </div>

          <textarea value={pastedText} onChange={(event) => setPastedText(event.target.value)} placeholder="Paste notes or article text" disabled={isBusy} />
          <button className="wide-button secondary" type="button" onClick={parsePastedText} disabled={isBusy}>
            <FileText size={18} />
            Parse Text
          </button>

          <div className="concepts">
            <div className="panel-title compact">
              <Brain size={18} />
              <h2>Concepts</h2>
            </div>
            {conceptsPreview.length ? (
              <ol>
                {conceptsPreview.map((concept) => (
                  <li key={concept.title || concept}>
                    <strong>{concept.title || concept}</strong>
                    {concept.summary || concept.sourceSentence || concept.explanation ? <span>{concept.summary || concept.sourceSentence || concept.explanation}</span> : null}
                    {concept.items?.length ? <span>{concept.items.slice(0, 4).join('; ')}</span> : null}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty">No concepts loaded.</p>
            )}
          </div>
        </aside>

        <section className="study-panel">
          <ModeContent
            mode={mode}
            source={source}
            studySet={studySet}
            currentCard={currentCard}
            flashIndex={flashIndex}
            showAnswer={showAnswer}
            feedback={feedback}
            provider={provider}
            practiceSession={practiceSession}
            practiceTick={practiceTick}
            mastery={mastery}
            quizSession={quizSession}
            quizQuestion={quizQuestion}
            quizTick={quizTick}
            remaining={remaining}
            answer={answer}
            setAnswer={setAnswer}
            setShowAnswer={setShowAnswer}
            setFlashIndex={setFlashIndex}
            submitPracticeAnswer={submitPracticeAnswer}
            submitQuizAnswer={submitQuizAnswer}
          />

          <div className="action-bar">
            <button type="button" onClick={() => startMode('cards')} disabled={isBusy}>
              <BookOpen size={18} />
              Start Cards
            </button>
            <button type="button" onClick={() => startMode('practice')} disabled={isBusy}>
              <Brain size={18} />
              Start Practice
            </button>
            <button type="button" onClick={() => startMode('test')} disabled={isBusy}>
              <Timer size={18} />
              Start Test
            </button>
            <button type="button" onClick={studyAgain} disabled={isBusy}>
              <RefreshCcw size={18} />
              Study Again
            </button>
            <button type="button" onClick={exitApp}>
              <LogOut size={18} />
              Exit
            </button>
          </div>
        </section>
      </section>
    </main>
  );
}

function ModeContent(props) {
  if (props.mode === 'cards' && props.currentCard) return <FlashcardView {...props} />;
  if (props.mode === 'practice' && props.practiceSession) return <PracticeView {...props} />;
  if (props.mode === 'test' && props.quizSession) return <QuizView {...props} />;

  return (
    <div className="ready-state">
      <div className="mode-icon">
        <Play size={26} />
      </div>
      <h2>{props.source ? props.source.title : 'Source needed'}</h2>
      <p>{props.source ? `${props.source.concepts.length} concepts ready.` : 'Upload, link, or paste material.'}</p>
      {props.feedback ? <p className="feedback error">{props.feedback}</p> : null}
      {props.provider ? <p className="provider">Generated by {props.provider}</p> : null}
    </div>
  );
}

function FlashcardView({ studySet, currentCard, flashIndex, showAnswer, setShowAnswer, setFlashIndex, feedback, provider }) {
  return (
    <div className="mode-stack">
      <div className="mode-header">
        <span>Card {flashIndex + 1} of {studySet.flashcards.length}</span>
        {provider ? <span>Provider: {provider}</span> : null}
      </div>
      <article className="flashcard">
        <h2>{currentCard.question}</h2>
        <p>{showAnswer ? currentCard.answer : 'Answer hidden'}</p>
      </article>
      <div className="inline-actions">
        <button type="button" onClick={() => setFlashIndex((flashIndex - 1 + studySet.flashcards.length) % studySet.flashcards.length)}>
          Previous
        </button>
        <button type="button" onClick={() => setShowAnswer(!showAnswer)}>
          {showAnswer ? 'Hide Answer' : 'Show Answer'}
        </button>
        <button type="button" onClick={() => setFlashIndex((flashIndex + 1) % studySet.flashcards.length)}>
          Next
        </button>
      </div>
      {feedback ? <p className="feedback error">{feedback}</p> : null}
    </div>
  );
}

function PracticeView({ practiceSession, mastery, answer, setAnswer, submitPracticeAnswer, feedback }) {
  if (practiceSession.isComplete) {
    return (
      <div className="ready-state">
        <div className="mode-icon">
          <CheckCircle2 size={28} />
        </div>
        <h2>Practice complete</h2>
        <p>Mastery: {practiceSession.masteryPercent}%</p>
      </div>
    );
  }

  return (
    <form className="mode-stack" onSubmit={submitPracticeAnswer}>
      <div className="mode-header">
        <span>Practice</span>
        <span>Mastery: {mastery}%</span>
      </div>
      <h2 className="prompt">{practiceSession.currentQuestion.prompt}</h2>
      <input className="answer-input" value={answer} onChange={(event) => setAnswer(event.target.value)} autoFocus />
      <button className="submit-button" type="submit">
        <Send size={18} />
        Submit Answer
      </button>
      {feedback ? <p className={`feedback ${feedback.startsWith('Correct') ? 'good' : 'error'}`}>{feedback}</p> : null}
    </form>
  );
}

function QuizView({ quizSession, quizQuestion, quizTick, remaining, answer, setAnswer, submitQuizAnswer }) {
  if (quizSession.isComplete) {
    const summary = quizSession.summary();
    const minutes = Math.floor(summary.elapsedSeconds / 60);
    const seconds = summary.elapsedSeconds % 60;
    return (
      <div className="ready-state">
        <div className="mode-icon">
          <Timer size={28} />
        </div>
        <h2>Quiz feedback</h2>
        <div className="summary-grid">
          <Metric label="Score" value={`${summary.correctCount}/${summary.totalCount}`} />
          <Metric label="Percent" value={`${summary.scorePercent}%`} />
          <Metric label="Mastery" value={`${summary.masteryPercent}%`} />
          <Metric label="Timing" value={`${minutes}m ${seconds}s`} />
        </div>
        <p>{summary.masteryPercent >= 70 ? 'Ready to move on.' : 'Study again, then retry the test.'}</p>
      </div>
    );
  }

  return (
    <div className="mode-stack" key={quizTick}>
      <div className="mode-header">
        <span>
          Question {quizSession.currentIndex + 1} of {quizSession.questions.length}
        </span>
        <span>{remaining}s</span>
      </div>
      <p className="question-type">{quizQuestion.type.replace('_', ' ')}</p>
      <h2 className="prompt">{quizQuestion.prompt}</h2>
      {quizQuestion.type === 'mcq' ? (
        <div className="options">
          {quizQuestion.options.map((option, index) => (
            <label key={option}>
              <input type="radio" name="quiz-answer" value={String.fromCharCode(65 + index)} checked={answer === String.fromCharCode(65 + index)} onChange={(event) => setAnswer(event.target.value)} />
              <span>{String.fromCharCode(65 + index)}. {option}</span>
            </label>
          ))}
        </div>
      ) : (
        <input className="answer-input" value={answer} onChange={(event) => setAnswer(event.target.value)} autoFocus />
      )}
      <button className="submit-button" type="button" onClick={() => submitQuizAnswer(false)}>
        <Send size={18} />
        Submit
      </button>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

async function request(path, { method = 'GET', json, body } = {}) {
  const response = await fetch(path, {
    method,
    headers: json ? { 'content-type': 'application/json' } : undefined,
    body: json ? JSON.stringify(json) : body,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed with HTTP ${response.status}`);
  return payload;
}

function modeLabel(mode) {
  return {
    cards: 'Flashcards',
    practice: 'Practice',
    test: 'Timed quiz',
  }[mode] || 'Ready';
}
