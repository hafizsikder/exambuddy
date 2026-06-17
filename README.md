# Exam Buddy

Exam Buddy is a local study app available in two forms:

- Python + Tkinter desktop app.
- React + Express web app.

## Features

- Load PDF, PPTX, TXT, Markdown, pasted text, or a user-supplied web link.
- Extract key concepts locally.
- Generate flashcards, iterative practice, and timed quizzes.
- Practice repeats missed questions until mastery is at least 70 percent.
- Timed quiz questions include MCQ, fill-in, rearrange, and math problem types with 20-60 second timers.
- Quiz feedback shows timing, score, and mastery.
- Theme picker: Anime, Floral, and Game-style graphics.

## Run The Desktop App

```powershell
python -m pip install -r requirements.txt
python main.py
```

You can also run:

```powershell
python -m exam_buddy
```

## Run The Web App

The web app runs locally and uses an Express API for PDF/PPTX parsing, web-link parsing, and optional AI generation.

```powershell
cd web
corepack enable
pnpm install
pnpm dev
```

Then open:

```text
http://127.0.0.1:5173
```

For a production-style local run:

```powershell
cd web
pnpm build
pnpm start
```

## Optional AI Generation

By default, Exam Buddy generates study material locally with no AI call.
To enable OpenAI generation, set `OPENAI_API_KEY`, optionally set `OPENAI_MODEL`, then tick `Use AI` in either app.

```powershell
setx OPENAI_API_KEY "your_api_key_here"
setx OPENAI_MODEL "gpt-5.4-mini"
```

If the AI call fails or credentials are not configured, the app falls back to local generation.

## Project Layout

- `exam_buddy/parser.py`: source parsing and concept extraction.
- `exam_buddy/generation.py`: local and optional AI study generation.
- `exam_buddy/sessions.py`: practice and timed quiz state.
- `exam_buddy/ui.py`: Tkinter desktop interface.
- `tests/test_core.py`: core behavior tests.
- `web/server/`: Express parsing and generation API.
- `web/src/`: React interface and shared study logic.
- `web/public/theme-assets/`: local theme artwork for anime, floral, and game-style modes.
