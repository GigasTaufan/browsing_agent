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
    answer.textContent = payload.answer ?? "";
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
  answer.textContent = "";
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
