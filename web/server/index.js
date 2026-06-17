import express from 'express';
import multer from 'multer';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer as createViteServer } from 'vite';
import { generateStudyMaterial } from './generator.js';
import { parseFileSource, parseTextSource, parseUrlSource, SourceParseError } from './sourceParser.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..');
const isDev = process.argv.includes('--dev');
const port = Number(process.env.PORT || 5173);
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 20 * 1024 * 1024 } });

const app = express();
app.use(express.json({ limit: '2mb' }));

app.get('/api/health', (_request, response) => {
  response.json({ ok: true, app: 'Exam Buddy Web' });
});

app.post('/api/parse-text', (request, response, next) => {
  try {
    response.json(parseTextSource(request.body?.text, request.body?.title || 'Pasted text'));
  } catch (error) {
    next(error);
  }
});

app.post('/api/parse-link', async (request, response, next) => {
  try {
    response.json(await parseUrlSource(request.body?.url));
  } catch (error) {
    next(error);
  }
});

app.post('/api/parse-file', upload.single('file'), async (request, response, next) => {
  try {
    response.json(await parseFileSource(request.file));
  } catch (error) {
    next(error);
  }
});

app.post('/api/generate', async (request, response, next) => {
  try {
    response.json(await generateStudyMaterial(request.body || {}));
  } catch (error) {
    next(error);
  }
});

if (isDev) {
  const vite = await createViteServer({
    root: rootDir,
    server: { middlewareMode: true },
    appType: 'spa',
  });
  app.use(vite.middlewares);
} else {
  app.use(express.static(path.join(rootDir, 'dist')));
  app.get(/.*/, (_request, response) => {
    response.sendFile(path.join(rootDir, 'dist', 'index.html'));
  });
}

app.use((error, _request, response, _next) => {
  const status = error instanceof SourceParseError ? error.status : 500;
  response.status(status).json({ error: error.message || 'Unexpected server error.' });
});

app.listen(port, '127.0.0.1', () => {
  console.log(`Exam Buddy Web running at http://127.0.0.1:${port}`);
});
