# Study Block Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Exam Buddy extract study-worthy blocks from PDFs, PPTX files, pasted text, and links, then generate flashcards from those blocks instead of short keyword phrases.

**Architecture:** Add a `StudyBlock` data model alongside existing concept details. The parser will clean source text, detect definitions, grouped definitions, lists, process steps, table-like comparisons, and examples, then expose both `study_blocks` and backward-compatible `concepts`. The local and web generators will prefer `StudyBlock` records for flashcards, practice, and quizzes, while AI prompts will receive the same structured blocks for optional refinement.

**Tech Stack:** Python dataclasses/Tkinter parser and generator, React/Express JavaScript parser and generator, unittest and Vitest, PyInstaller for the desktop executable.

---

### Task 1: Add Failing Tests For SDS Study Blocks

**Files:**
- Modify: `tests/test_core.py`
- Modify: `web/src/lib/study.test.js`

- [ ] **Step 1: Write Python tests**

Add tests that use an SDS lecture excerpt containing Data Science, Importance of Statistics in Data Science, and Population/Sampling definitions. Assert that extraction produces grouped study blocks and that local flashcards include definitions, techniques, and grouped items.

- [ ] **Step 2: Write web tests**

Add matching Vitest tests for `extractStudyBlocks` and `generateStudySet`.

- [ ] **Step 3: Run tests to verify failure**

Run:
`python -m unittest discover -s tests`
`node node_modules/vitest/vitest.mjs run`

Expected: fail because `extract_study_blocks` / `extractStudyBlocks` do not exist yet.

### Task 2: Implement Python Study Blocks

**Files:**
- Modify: `exam_buddy/parser.py`
- Modify: `exam_buddy/generation.py`
- Modify: `exam_buddy/ui.py`

- [ ] **Step 1: Add `StudyBlock`**

Fields: `title`, `block_type`, `summary`, `items`, `source_excerpt`, `page`.

- [ ] **Step 2: Extract blocks**

Clean repeated headers/footers, join wrapped lines, detect definition blocks (`Title: body`), grouped definitions, bullets, step lists, and section lists.

- [ ] **Step 3: Derive concept details**

Build `KeyConcept` records from top study blocks for compatibility.

- [ ] **Step 4: Generate block-backed flashcards**

When blocks are supplied, flashcard answers should include the block summary and key items rather than generic source sentences.

### Task 3: Implement Web Study Blocks

**Files:**
- Modify: `web/src/lib/study.js`
- Modify: `web/server/sourceParser.js`
- Modify: `web/server/generator.js`
- Modify: `web/src/App.jsx`

- [ ] **Step 1: Add `extractStudyBlocks`**

Mirror the Python local heuristics in JavaScript.

- [ ] **Step 2: Return `studyBlocks` from server parsing**

Keep `concepts` and `conceptDetails` for compatibility.

- [ ] **Step 3: Generate from blocks**

Send `studyBlocks` from the UI and use them in local generation and AI prompts.

### Task 4: Verify And Package

**Files:**
- Output: `outputs/ExamBuddy.exe`

- [ ] **Step 1: Run Python tests**
- [ ] **Step 2: Run web tests**
- [ ] **Step 3: Run web production build**
- [ ] **Step 4: Browser smoke test the web UI with SDS excerpt**
- [ ] **Step 5: Rebuild `ExamBuddy.exe`**
- [ ] **Step 6: Launch-test the executable**
- [ ] **Step 7: Commit and push**
