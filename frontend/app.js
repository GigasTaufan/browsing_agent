"use strict";

const form = document.querySelector("#question-form");
const questionInput = document.querySelector("#question");
const submitButton = document.querySelector("#submit-button");
const status = document.querySelector("#status");
const result = document.querySelector("#result");
const answer = document.querySelector("#answer");
const citationsSection = document.querySelector("#citations-section");
const citationsList = document.querySelector("#citations");
const errorPanel = document.querySelector("#error");
const errorMessage = document.querySelector("#error-message");
const newQuestionButton = document.querySelector("#new-question");
let isSubmitting = false;

function safeHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

const INLINE_MARKDOWN = /(\*\*[^\n]+?\*\*|__[^\n]+?__|\*[^*\n]+?\*|_[^_\n]+?_|`[^`\n]+`|\[[^\]\n]+\]\((?:[^()\s]+|\([^()]*\))+\))/g;

function appendInlineTokens(container, text) {
  let cursor = 0;
  for (const match of text.matchAll(INLINE_MARKDOWN)) {
    if (match.index > cursor) {
      container.append(document.createTextNode(text.slice(cursor, match.index)));
    }
    const token = match[0];
    cursor = match.index + token.length;

    if (token.startsWith("**") || token.startsWith("__")) {
      const strong = document.createElement("strong");
      appendInlineTokens(strong, token.slice(2, -2));
      container.append(strong);
    } else if (token.startsWith("`")) {
      const code = document.createElement("code");
      code.textContent = token.slice(1, -1);
      container.append(code);
    } else if (token.startsWith("[")) {
      const labelEnd = token.indexOf("](");
      const label = labelEnd > 0 ? token.slice(1, labelEnd) : "";
      const rawUrl = labelEnd > 0 ? token.slice(labelEnd + 2, -1) : "";
      const url = safeHttpUrl(rawUrl);
      if (label && url) {
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
        appendInlineTokens(anchor, label);
        container.append(anchor);
      } else {
        container.append(document.createTextNode(token));
      }
    } else {
      const em = document.createElement("em");
      appendInlineTokens(em, token.slice(1, -1));
      container.append(em);
    }
  }
  if (cursor < text.length) {
    container.append(document.createTextNode(text.slice(cursor)));
  }
}

function appendInline(container, text) {
  const lines = text.split("\n");
  lines.forEach((line, index) => {
    if (index > 0) container.append(document.createElement("br"));
    appendInlineTokens(container, line);
  });
}

function renderMarkdown(source) {
  const fragment = document.createDocumentFragment();
  const lines = String(source ?? "").replace(/\r\n?/g, "\n").split("\n");
  let paragraph = [];
  let list = null;
  let quote = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const node = document.createElement("p");
    appendInline(node, paragraph.join("\n"));
    fragment.append(node);
    paragraph = [];
  };
  const flushList = () => {
    if (!list) return;
    fragment.append(list.element);
    list = null;
  };
  const flushQuote = () => {
    if (!quote.length) return;
    const node = document.createElement("blockquote");
    appendInline(node, quote.join("\n"));
    fragment.append(node);
    quote = [];
  };
  const flushAll = () => {
    flushParagraph();
    flushList();
    flushQuote();
  };

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, "");
    if (!line.trim()) {
      flushAll();
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushAll();
      const level = Math.min(heading[1].length + 2, 6);
      const node = document.createElement(`h${level}`);
      appendInline(node, heading[2]);
      fragment.append(node);
      continue;
    }

    if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      flushAll();
      fragment.append(document.createElement("hr"));
      continue;
    }

    const quoted = line.match(/^\s*>\s?(.*)$/);
    if (quoted) {
      flushParagraph();
      flushList();
      quote.push(quoted[1]);
      continue;
    }

    const unordered = line.match(/^(\s*)[-*+]\s+(.*)$/);
    const ordered = unordered ? null : line.match(/^(\s*)\d+[.)]\s+(.*)$/);
    if (unordered || ordered) {
      flushParagraph();
      flushQuote();
      const type = unordered ? "ul" : "ol";
      const indent = (unordered ? unordered[1] : ordered[1]).replace(/\t/g, "  ").length;
      if (!list || list.type !== type) {
        flushList();
        list = { type, element: document.createElement(type), indent };
      }
      const item = document.createElement("li");
      const depth = Math.max(0, Math.floor((indent - list.indent) / 2));
      if (depth > 0) item.style.marginLeft = `${Math.min(depth, 6) * 1.25}em`;
      appendInline(item, unordered ? unordered[2] : ordered[2]);
      list.element.append(item);
      continue;
    }

    flushList();
    flushQuote();
    paragraph.push(line.trim());
  }

  flushAll();
  return fragment;
}

function renderCitations(items) {
  citationsList.replaceChildren();
  for (const citation of items) {
    const item = document.createElement("li");
    const safeUrl = safeHttpUrl(citation.url);
    if (safeUrl) {
      const link = document.createElement("a");
      link.href = safeUrl;
      link.textContent = citation.title || safeUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      item.append(link);
    } else {
      const title = document.createElement("span");
      title.textContent = citation.title || "Sumber tanpa judul";
      item.append(title);
    }
    if (citation.snippet) {
      const snippet = document.createElement("p");
      snippet.textContent = citation.snippet;
      item.append(snippet);
    }
    citationsList.append(item);
  }
  citationsSection.hidden = items.length === 0;
}

function setSubmitting(submitting) {
  isSubmitting = submitting;
  submitButton.disabled = submitting;
  questionInput.disabled = submitting;
  submitButton.textContent = submitting ? "Sedang mencari…" : "Cari jawaban →";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSubmitting) return;

  const question = questionInput.value.trim();
  if (!question) {
    questionInput.focus();
    return;
  }

  result.hidden = true;
  errorPanel.hidden = true;
  status.hidden = false;
  status.textContent = "Sedang mencari jawaban dan sumber…";
  setSubmitting(true);

  try {
    const response = await fetch("/ui-api/v1/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.error?.message || payload?.detail || `Permintaan gagal (${response.status}).`);
    }
    answer.replaceChildren(renderMarkdown(payload.answer ?? ""));
    renderCitations(Array.isArray(payload.citations) ? payload.citations : []);
    result.hidden = false;
    newQuestionButton.disabled = false;
  } catch (error) {
    errorMessage.textContent = error instanceof Error ? error.message : "Tidak dapat menghubungi layanan. Coba lagi.";
    errorPanel.hidden = false;
  } finally {
    status.hidden = true;
    setSubmitting(false);
  }
});

newQuestionButton.addEventListener("click", () => {
  answer.replaceChildren();
  citationsList.replaceChildren();
  citationsSection.hidden = true;
  result.hidden = true;
  errorMessage.textContent = "";
  errorPanel.hidden = true;
  status.hidden = true;
  newQuestionButton.disabled = true;
  questionInput.value = "";
  questionInput.focus();
});
