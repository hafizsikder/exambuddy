import AdmZip from 'adm-zip';
import { PDFParse } from 'pdf-parse';
import { extractKeyConcepts } from '../src/lib/study.js';

export class SourceParseError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.name = 'SourceParseError';
    this.status = status;
  }
}

export function parseTextSource(text, title = 'Pasted text') {
  const cleaned = cleanText(text);
  if (!cleaned) throw new SourceParseError('No readable text was found.');
  return {
    title,
    sourceType: 'text',
    text: cleaned,
    concepts: extractKeyConcepts(cleaned),
  };
}

export async function parseFileSource(file) {
  if (!file) throw new SourceParseError('Upload a PDF, PPTX, TXT, or Markdown file.');

  const originalName = file.originalname || 'Uploaded file';
  const lowerName = originalName.toLowerCase();
  let text = '';
  let sourceType = 'text';

  if (lowerName.endsWith('.pdf')) {
    sourceType = 'pdf';
    text = await extractTextFromPdf(file.buffer);
  } else if (lowerName.endsWith('.pptx')) {
    sourceType = 'pptx';
    text = extractTextFromPptx(file.buffer);
  } else if (lowerName.endsWith('.txt') || lowerName.endsWith('.md')) {
    sourceType = 'text';
    text = file.buffer.toString('utf8');
  } else {
    throw new SourceParseError('Supported files are PDF, PPTX, TXT, and MD.');
  }

  const cleaned = cleanText(text);
  if (!cleaned) throw new SourceParseError('No readable text was found in the selected file.');
  return {
    title: originalName,
    sourceType,
    text: cleaned,
    concepts: extractKeyConcepts(cleaned),
  };
}

export async function parseUrlSource(url) {
  if (!/^https?:\/\//i.test(url || '')) {
    throw new SourceParseError('Enter a full http:// or https:// web link.');
  }

  let response;
  try {
    response = await fetch(url, {
      headers: { 'user-agent': 'ExamBuddyWeb/1.0' },
      signal: AbortSignal.timeout(15000),
    });
  } catch (error) {
    throw new SourceParseError(`Could not fetch the web link: ${error.message}`, 502);
  }

  if (!response.ok) {
    throw new SourceParseError(`The web link returned HTTP ${response.status}.`, 502);
  }

  const contentType = response.headers.get('content-type') || '';
  const payload = await response.text();
  const { title, text } = contentType.includes('html') || payload.slice(0, 500).toLowerCase().includes('<html')
    ? extractTextFromHtml(payload)
    : { title: url, text: payload };

  const cleaned = cleanText(text);
  if (!cleaned) throw new SourceParseError('No readable text was found at the web link.');
  return {
    title: title || url,
    sourceType: 'web',
    text: cleaned,
    concepts: extractKeyConcepts(cleaned),
  };
}

export function extractTextFromHtml(html) {
  const title = decodeEntities(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] || '').trim();
  const body = html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ')
    .replace(/<svg[\s\S]*?<\/svg>/gi, ' ')
    .replace(/<\/(p|li|div|section|article|h[1-6]|br)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ');

  return {
    title,
    text: cleanText(decodeEntities(body)),
  };
}

export function extractTextFromPptxXml(xmlFragments) {
  return cleanText(
    xmlFragments
      .flatMap((xml) => Array.from(xml.matchAll(/<a:t[^>]*>([\s\S]*?)<\/a:t>/g), (match) => decodeEntities(match[1])))
      .join('\n'),
  );
}

async function extractTextFromPdf(buffer) {
  const parser = new PDFParse({ data: buffer });
  try {
    const result = await parser.getText();
    return result.text || '';
  } catch (error) {
    throw new SourceParseError(`Could not parse PDF: ${error.message}`);
  } finally {
    await parser.destroy();
  }
}

function extractTextFromPptx(buffer) {
  try {
    const zip = new AdmZip(buffer);
    const slideXml = zip
      .getEntries()
      .filter((entry) => /^ppt\/slides\/slide\d+\.xml$/i.test(entry.entryName))
      .sort((left, right) => left.entryName.localeCompare(right.entryName, undefined, { numeric: true }))
      .map((entry) => entry.getData().toString('utf8'));
    return extractTextFromPptxXml(slideXml);
  } catch (error) {
    throw new SourceParseError(`Could not parse PPTX: ${error.message}`);
  }
}

function cleanText(text) {
  return String(text || '')
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function decodeEntities(text) {
  const entities = {
    amp: '&',
    lt: '<',
    gt: '>',
    quot: '"',
    apos: "'",
    nbsp: ' ',
  };
  return String(text || '')
    .replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (_, entity) => {
      if (entity.startsWith('#x')) return String.fromCodePoint(Number.parseInt(entity.slice(2), 16));
      if (entity.startsWith('#')) return String.fromCodePoint(Number.parseInt(entity.slice(1), 10));
      return entities[entity.toLowerCase()] ?? `&${entity};`;
    })
    .replace(/\s+/g, ' ')
    .trim();
}
