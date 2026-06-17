import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { extractTextFromHtml, extractTextFromPptxXml, parseTextSource } from './sourceParser.js';

describe('server source parser helpers', () => {
  it('imports parser module without export-shape errors', async () => {
    const module = await import('./sourceParser.js');

    expect(typeof module.parseFileSource).toBe('function');
  });

  it('loads under native Node ESM like the server startup path', () => {
    const output = execFileSync(process.execPath, ['-e', "import('./server/sourceParser.js').then(() => console.log('native import ok'))"], {
      cwd: process.cwd(),
      encoding: 'utf8',
    });

    expect(output.trim()).toBe('native import ok');
  });

  it('turns pasted text into title, text, and concepts', () => {
    const parsed = parseTextSource(
      'Photosynthesis uses chlorophyll. Photosynthesis creates glucose and oxygen for plant growth.',
      'Pasted notes',
    );

    expect(parsed.title).toBe('Pasted notes');
    expect(parsed.sourceType).toBe('text');
    expect(parsed.text).toContain('Photosynthesis');
    expect(parsed.concepts.map((item) => item.toLowerCase())).toContain('photosynthesis');
  });

  it('extracts readable body text and page title from html', () => {
    const parsed = extractTextFromHtml(`
      <html>
        <head><title>Cell Biology</title><style>.hide{display:none}</style></head>
        <body><script>ignore()</script><h1>Mitochondria</h1><p>ATP energy powers cells.</p></body>
      </html>
    `);

    expect(parsed.title).toBe('Cell Biology');
    expect(parsed.text).toContain('Mitochondria');
    expect(parsed.text).toContain('ATP energy powers cells');
    expect(parsed.text).not.toContain('ignore');
  });

  it('extracts slide text from pptx xml fragments', () => {
    const text = extractTextFromPptxXml([
      '<a:t>Slide 1</a:t><a:t>Key Concept</a:t>',
      '<a:t>Energy &amp; Cells</a:t>',
    ]);

    expect(text).toContain('Slide 1');
    expect(text).toContain('Key Concept');
    expect(text).toContain('Energy & Cells');
  });
});
