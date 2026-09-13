import { DEEPSEEK_API_URL } from "./config.js";

const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#query");
const bookSelect = document.querySelector("#book-select");
const submitButton = document.querySelector("#submit-button");
const status = document.querySelector("#status");
const stats = document.querySelector("#corpus-stats");
const answerSection = document.querySelector("#answer-section");
const emptySection = document.querySelector("#empty-section");
const answer = document.querySelector("#answer");
const resultsNode = document.querySelector("#results");
const resultMeta = document.querySelector("#result-meta");

let books = [];
let lastTokens = [];
const worker = new Worker("search-worker.js");

function selectedEdition() {
  return form.elements.edition.value;
}

function refreshBookOptions() {
  const edition = selectedEdition();
  const current = bookSelect.value;
  bookSelect.replaceChildren(new Option("全部著作", ""));
  for (const book of books.filter((item) => edition === "all" || item.publisher === edition)) {
    bookSelect.add(new Option(`${book.title}${book.year ? ` · ${book.year}` : ""}`, book.id));
  }
  if ([...bookSelect.options].some((option) => option.value === current)) bookSelect.value = current;
}

function appendHighlighted(parent, text, tokens) {
  const useful = tokens.filter((token) => token.length >= 2).sort((a, b) => b.length - a.length).slice(0, 12);
  if (!useful.length) {
    parent.textContent = text;
    return;
  }
  const escaped = useful.map((token) => token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`(${escaped.join("|")})`, "gi");
  for (const part of text.split(regex)) {
    if (useful.some((token) => token.toLowerCase() === part.toLowerCase())) {
      const mark = document.createElement("mark");
      mark.textContent = part;
      parent.append(mark);
    } else parent.append(document.createTextNode(part));
  }
}

function citationText(item) {
  return `《${item.title}》${item.section ? `·${item.section}` : ""}（${item.publisher}${item.year ? `，${item.year}` : ""}）`;
}

function renderAnswer(items) {
  answer.replaceChildren();
  const intro = document.createElement("p");
  intro.textContent = "以下是与问题最贴近的原文句子：";
  answer.append(intro);
  for (const item of items) {
    const paragraph = document.createElement("p");
    appendHighlighted(paragraph, item.sentence, lastTokens);
    paragraph.append(" ");
    const cite = document.createElement("span");
    cite.className = "citation";
    cite.textContent = `[${citationText(item.result)}]`;
    paragraph.append(cite);
    answer.append(paragraph);
  }
}

function renderDeepSeekAnswer(text) {
  answer.replaceChildren();
  for (const block of text.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean)) {
    const paragraph = document.createElement("p");
    paragraph.textContent = block;
    answer.append(paragraph);
  }
}

async function requestDeepSeek(question, items) {
  if (!DEEPSEEK_API_URL) throw new Error("DeepSeek 后端尚未配置");
  const sources = items.slice(0, 6).map((item) => ({
    citation: citationText(item),
    text: item.text,
  }));
  const response = await fetch(`${DEEPSEEK_API_URL.replace(/\/$/, "")}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, sources }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `请求失败（${response.status}）`);
  return data.answer;
}

function renderResults(items) {
  resultsNode.replaceChildren();
  for (const item of items) {
    const article = document.createElement("article");
    article.className = "result";
    const top = document.createElement("div");
    top.className = "result-top";
    const title = document.createElement("h4");
    title.textContent = `《${item.title}》${item.section ? ` · ${item.section}` : ""}`;
    const meta = document.createElement("p");
    meta.className = "result-meta";
    meta.textContent = `${item.publisher}${item.year ? ` · ${item.year}` : ""} · 片段 ${item.chunkIndex + 1}`;
    top.append(title, meta);
    const text = document.createElement("p");
    appendHighlighted(text, item.text, lastTokens);
    article.append(top, text);
    resultsNode.append(article);
  }
}

worker.onmessage = ({ data }) => {
  if (data.type === "ready") {
    books = data.books;
    refreshBookOptions();
    bookSelect.disabled = false;
    submitButton.disabled = false;
    status.textContent = "已就绪，可直接输入问题";
    stats.textContent = `${books.length} 部著作 · ${data.chunkCount.toLocaleString("zh-CN")} 条原文片段`;
    return;
  }
  if (data.type === "error") {
    status.textContent = `载入失败：${data.message}`;
    return;
  }
  if (data.type === "results") {
    submitButton.disabled = false;
    submitButton.querySelector("span").textContent = "检索原文";
    lastTokens = data.tokens;
    if (!data.results.length) {
      answerSection.hidden = true;
      emptySection.hidden = false;
      emptySection.scrollIntoView({ behavior: "smooth" });
      status.textContent = "检索完成";
      return;
    }
    emptySection.hidden = true;
    resultMeta.textContent = `找到 ${data.results.length} 条高相关片段`;
    renderAnswer(data.answer);
    renderResults(data.results);
    answerSection.hidden = false;
    answerSection.scrollIntoView({ behavior: "smooth" });
    status.textContent = "已找到原文，正在请 DeepSeek 回答…";
    requestDeepSeek(data.query, data.results)
      .then((text) => {
        renderDeepSeekAnswer(text);
        status.textContent = "DeepSeek 回答完成";
      })
      .catch((error) => {
        status.textContent = `${error.message}；已显示原文摘录`;
      });
  }
};

form.addEventListener("change", (event) => {
  if (event.target.name === "edition") refreshBookOptions();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;
  submitButton.disabled = true;
  submitButton.querySelector("span").textContent = "检索中…";
  status.textContent = "正在逐条比对原文…";
  worker.postMessage({ type: "search", query, edition: selectedEdition(), bookId: bookSelect.value });
});

for (const button of document.querySelectorAll(".examples button")) {
  button.addEventListener("click", () => {
    queryInput.value = button.textContent;
    queryInput.focus();
  });
}
