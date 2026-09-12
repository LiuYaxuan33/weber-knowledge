let corpus = null;

const STOP_TOKENS = new Set([
  "什么", "如何", "为何", "是否", "怎么", "哪些", "关于", "认为", "理解", "韦伯", "一个", "一种",
]);

function normalize(text) {
  return String(text || "").normalize("NFKC").toLowerCase().replace(/\s+/g, "");
}

function queryTokens(query) {
  const normalized = normalize(query);
  const tokens = new Set();
  for (const word of normalized.match(/[a-z0-9][a-z0-9-]{1,}/g) || []) tokens.add(word);
  for (const run of normalized.match(/[\u3400-\u9fff]{2,}/g) || []) {
    if (run.length <= 5 && !STOP_TOKENS.has(run)) tokens.add(run);
    for (let i = 0; i < run.length - 1; i += 1) {
      const pair = run.slice(i, i + 2);
      if (!STOP_TOKENS.has(pair)) tokens.add(pair);
    }
    for (let i = 0; i < run.length - 2; i += 1) tokens.add(run.slice(i, i + 3));
  }
  return [...tokens].slice(0, 42);
}

function occurrences(text, token) {
  let count = 0;
  let cursor = 0;
  while (count < 3 && (cursor = text.indexOf(token, cursor)) !== -1) {
    count += 1;
    cursor += token.length;
  }
  return count;
}

function scoreText(text, title, section, exact, tokens) {
  const body = normalize(text);
  const heading = normalize(`${title}${section}`);
  let score = exact.length >= 2 && body.includes(exact) ? 80 : 0;
  let matched = 0;
  for (const token of tokens) {
    const count = occurrences(body, token);
    if (!count) continue;
    matched += 1;
    score += count * (token.length >= 3 ? 6 : 3.5);
    if (heading.includes(token)) score += token.length >= 3 ? 12 : 6;
  }
  const coverage = tokens.length ? matched / tokens.length : 0;
  return score + coverage * 28;
}

function bestSentences(results, tokens) {
  const candidates = [];
  const seen = new Set();
  for (const result of results.slice(0, 7)) {
    const sentences = result.text.split(/(?<=[。！？!?；;])/).map((s) => s.trim()).filter((s) => s.length >= 24);
    for (const sentence of sentences) {
      const key = sentence.slice(0, 80);
      if (seen.has(key)) continue;
      seen.add(key);
      const body = normalize(sentence);
      let score = 0;
      for (const token of tokens) if (body.includes(token)) score += token.length;
      if (score) candidates.push({ sentence, score, result });
    }
  }
  return candidates.sort((a, b) => b.score - a.score).slice(0, 3);
}

async function loadCorpus() {
  const response = await fetch("data/search-data.json");
  if (!response.ok) throw new Error(`载入失败（${response.status}）`);
  const data = await response.json();
  const entries = [];
  for (const book of data.books) {
    for (const [section, chunkIndex, text] of book.chunks) {
      entries.push({
        bookId: book.id,
        title: book.title,
        publisher: book.publisher,
        year: book.year,
        section,
        chunkIndex,
        text,
      });
    }
  }
  corpus = { ...data, entries };
  postMessage({ type: "ready", books: data.books.map(({ chunks, ...book }) => book), chunkCount: data.chunkCount });
}

function search({ query, edition, bookId }) {
  const exact = normalize(query);
  const tokens = queryTokens(query);
  const ranked = [];
  for (const entry of corpus.entries) {
    if (edition !== "all" && entry.publisher !== edition) continue;
    if (bookId && entry.bookId !== bookId) continue;
    const score = scoreText(entry.text, entry.title, entry.section, exact, tokens);
    if (score < 7) continue;
    ranked.push({ ...entry, score });
  }
  ranked.sort((a, b) => b.score - a.score);

  const results = [];
  const perBook = new Map();
  for (const item of ranked) {
    const count = perBook.get(item.bookId) || 0;
    if (count >= 3) continue;
    perBook.set(item.bookId, count + 1);
    results.push(item);
    if (results.length === 9) break;
  }

  postMessage({ type: "results", query, tokens, results, answer: bestSentences(results, tokens) });
}

self.onmessage = (event) => {
  if (event.data.type === "search") search(event.data);
};

loadCorpus().catch((error) => postMessage({ type: "error", message: error.message }));
