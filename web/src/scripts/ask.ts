// Client for the Ask portal (/ask). Framework-free, in the style of search.ts/submit.ts.
// Takes the Turnstile token the widget injects, POSTs the question to /api/ask, and
// renders the grounded answer with inline citation links + a sources list (#212, #213).
// The answer HTML is built by the pure, escaped renderer in lib/askRender.ts.
//
// Streaming UX (#331): a `meta` frame arrives before any token, carrying the count of
// records searched and the *candidate* citations — so `[n]` markers resolve to links
// incrementally as tokens stream, not only at `done`. The control row offers Stop /
// Copy / Retry, with Stop aborting the in-flight request.

import { drainSse } from "@watermark/functions/api/_lib/sse";
import { type AskCitation, renderAnswer, renderSources, searchingHint } from "@watermark/core/askRender";

interface AskResponse {
  answer?: string;
  citations?: AskCitation[];
  refused?: boolean;
  error?: string;
}

interface AskMeta {
  searched?: number;
  candidates?: AskCitation[];
}

interface AskDone {
  citations?: AskCitation[];
  refused?: boolean;
}

const form = document.getElementById("ask-form") as HTMLFormElement | null;
const input = document.getElementById("ask-question") as HTMLTextAreaElement | null;
const statusEl = document.getElementById("ask-status");
const answerEl = document.getElementById("ask-answer");
const sourcesEl = document.getElementById("ask-sources");
const controlsEl = document.getElementById("ask-controls");
const stopBtn = document.getElementById("ask-stop") as HTMLButtonElement | null;
const copyBtn = document.getElementById("ask-copy") as HTMLButtonElement | null;
const retryBtn = document.getElementById("ask-retry") as HTMLButtonElement | null;

if (form && input && statusEl && answerEl && sourcesEl) {
  const endpoint = form.dataset.endpoint || "/api/ask";
  const base = form.dataset.base || "/";

  const setStatus = (msg: string, kind: "ok" | "err" | "info" | ""): void => {
    statusEl.textContent = msg;
    statusEl.dataset.kind = kind;
  };

  const turnstile = (): { reset: () => void } | undefined =>
    (window as unknown as { turnstile?: { reset: () => void } }).turnstile;

  // The control row: show only the buttons that apply to the current state, and collapse
  // the whole row when none do.
  const setControls = (opts: { stop?: boolean; copy?: boolean; retry?: boolean }): void => {
    if (stopBtn) stopBtn.hidden = !opts.stop;
    if (copyBtn) copyBtn.hidden = !opts.copy;
    if (retryBtn) retryBtn.hidden = !opts.retry;
    if (controlsEl) controlsEl.hidden = !(opts.stop || opts.copy || opts.retry);
  };

  // Per-ask streaming state, reset on each submit.
  let abort: AbortController | null = null;
  let stopped = false; // the user pressed Stop — finalize the partial as deliberate
  let lastAnswer = ""; // raw text of the last completed/partial answer, for Copy

  // Example-question chips seed the input and submit immediately.
  for (const chip of document.querySelectorAll<HTMLButtonElement>(".ask-example")) {
    chip.addEventListener("click", () => {
      input.value = chip.dataset.q || chip.textContent || "";
      form.requestSubmit();
    });
  }

  // The hand-off from search (#1890): a reader whose search came back thin arrives here with
  // their words in `?q=`. Seed the box but do NOT auto-submit — an ask costs a model call and
  // spends the caller's Turnstile token, and the words that failed as a lexical search are often
  // worth rephrasing as a question first. `/ask` is a static page, so this can only happen client
  // side; `Astro.url.searchParams` is empty at build time.
  const handoff = new URLSearchParams(window.location.search).get("q");
  if (handoff && !input.value) {
    input.value = handoff.slice(0, 1000);
    input.focus();
  }

  const showEmpty = (): void => {
    // Announce the outcome in the live status region too — the answer area isn't a live
    // region, so a screen reader that heard "Searching…" needs this to learn it resolved.
    setStatus("No answer found in the record.", "info");
    sourcesEl.innerHTML = "";
    answerEl.innerHTML =
      '<p class="ask-empty">The record doesn\'t answer that. ' +
      "Try rephrasing, or browse the corpus and timeline directly.</p>";
    answerEl.hidden = false;
    lastAnswer = "";
    setControls({ retry: true }); // nothing to copy, but the question can be re-asked
  };

  // Final render once the whole answer is in: reconcile [n] markers into links + sources.
  const renderFinal = (answer: string, citations: AskCitation[], refused?: boolean): void => {
    const a = answer.trim();
    if (refused || !a) {
      showEmpty();
      return;
    }
    // Announce completion (same a11y reason as showEmpty) and nudge toward verification.
    setStatus("Answer ready — verify each citation.", "ok");
    answerEl.innerHTML = renderAnswer(a, citations, base);
    sourcesEl.innerHTML = renderSources(citations, base);
    answerEl.hidden = false;
    lastAnswer = a;
    setControls({ copy: true, retry: true });
  };

  // Consume the Worker's SSE stream: resolve citations live against the candidates carried
  // on `meta`, then reconcile the cited subset at `done`.
  const consumeStream = async (body: ReadableStream<Uint8Array>): Promise<void> => {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let full = "";
    let candidates: AskCitation[] = []; // resolve [n] markers live until `done` filters them
    let started = false; // first delta seen — switch from the count hint to the answer
    let terminal = false; // a `done` or `error` event was handled
    answerEl.hidden = false;
    setControls({ stop: true }); // a request is in flight — offer to stop it
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = drainSse(buffer);
        buffer = rest;
        for (const ev of events) {
          if (ev.event === "meta") {
            let m: AskMeta = {};
            try {
              m = JSON.parse(ev.data) as AskMeta;
            } catch {}
            candidates = m.candidates ?? [];
            // Refine the generic "Searching the record…" into the grounded count.
            if (!started && m.searched) setStatus(searchingHint(m.searched), "info");
          } else if (ev.event === "delta") {
            try {
              full += (JSON.parse(ev.data) as { text?: string }).text ?? "";
            } catch {}
            if (!started) {
              started = true;
              setStatus("", ""); // clear the progress note only once an answer is arriving
            }
            // Live citation links: candidates carry the same per-marker metadata the final
            // citations do, so markers the answer actually uses link identically at `done`.
            answerEl.innerHTML = renderAnswer(full, candidates, base);
          } else if (ev.event === "done") {
            terminal = true;
            let d: AskDone = {};
            try {
              d = JSON.parse(ev.data) as AskDone;
            } catch {}
            renderFinal(full, d.citations ?? [], d.refused);
          } else if (ev.event === "error") {
            terminal = true;
            let msg = "Couldn't answer your question.";
            try {
              msg = (JSON.parse(ev.data) as { error?: string }).error ?? msg;
            } catch {}
            setStatus(`Couldn't answer: ${msg}`, "err");
            // Keep whatever streamed; let the reader re-ask.
            lastAnswer = full.trim();
            setControls({ copy: Boolean(lastAnswer), retry: true });
          }
        }
      }
    } catch (e) {
      // The user pressed Stop (we aborted the fetch) — keep the partial as a finished,
      // if incomplete, answer. Any other read error falls through to the drop handling.
      if (stopped) {
        const a = full.trim();
        if (a) {
          answerEl.innerHTML = renderAnswer(a, candidates, base);
          sourcesEl.innerHTML = "";
          answerEl.hidden = false;
          lastAnswer = a;
          setStatus("Stopped — partial answer; it may be incomplete.", "info");
          setControls({ copy: true, retry: true });
        } else {
          setStatus("Stopped before any answer arrived.", "info");
          setControls({ retry: true });
        }
        return;
      }
      throw e;
    }
    // The stream closed without a terminal event (e.g. the connection dropped). Don't leave
    // a half-rendered answer with raw [n] markers: format what arrived and flag it incomplete.
    if (!terminal) {
      const a = full.trim();
      if (a) {
        answerEl.innerHTML = renderAnswer(a, candidates, base);
        sourcesEl.innerHTML = "";
        answerEl.hidden = false;
        lastAnswer = a;
        setStatus("The connection ended before the answer finished — it may be incomplete.", "err");
        setControls({ copy: true, retry: true });
      } else {
        setStatus("The connection ended before any answer arrived. Please try again.", "err");
        setControls({ retry: true });
      }
    }
  };

  const ask = async (question: string, token: string): Promise<void> => {
    abort = new AbortController();
    let r: Response;
    try {
      r = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ question, turnstile_token: token }),
        signal: abort.signal,
      });
    } catch (e) {
      if (stopped) {
        setStatus("Stopped before any answer arrived.", "info");
        setControls({ retry: true });
        return;
      }
      if (e instanceof DOMException && e.name === "AbortError") return;
      setStatus("Network error — please try again.", "err");
      setControls({ retry: true });
      return;
    }

    const ct = r.headers.get("content-type") ?? "";
    if (r.ok && ct.includes("text/event-stream") && r.body) {
      await consumeStream(r.body);
      return;
    }
    // JSON path — error responses (gating/rate-limit/turnstile) and the non-stream fallback.
    const out = (await r.json().catch(() => ({}))) as AskResponse;
    if (!r.ok) {
      setStatus(out.error ? `Couldn't answer: ${out.error}` : "Couldn't answer your question.", "err");
      setControls({ retry: true });
      return;
    }
    renderFinal(out.answer ?? "", out.citations ?? [], out.refused);
  };

  // Stop: abort the in-flight request; consumeStream finalizes the partial as deliberate.
  stopBtn?.addEventListener("click", () => {
    stopped = true;
    if (stopBtn) stopBtn.hidden = true; // immediate feedback; final state set on unwind
    abort?.abort();
  });

  // Copy: lift the raw answer text to the clipboard, with a brief confirmation.
  copyBtn?.addEventListener("click", () => {
    if (!lastAnswer || !navigator.clipboard) return;
    void navigator.clipboard.writeText(lastAnswer).then(
      () => {
        const prev = copyBtn.textContent;
        copyBtn.textContent = "Copied";
        window.setTimeout(() => {
          copyBtn.textContent = prev;
        }, 1500);
      },
      () => {},
    );
  });

  // Retry: re-run the same question through the full submit flow (re-checks the challenge).
  retryBtn?.addEventListener("click", () => {
    form.requestSubmit();
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (question.length < 3) {
      setStatus("Type a question about the record.", "err");
      return;
    }
    const token = String(new FormData(form).get("cf-turnstile-response") || "");
    if (!token) {
      setStatus("Please complete the verification challenge.", "err");
      return;
    }

    const submitBtn = form.querySelector<HTMLButtonElement>("button[type=submit]");
    if (submitBtn) submitBtn.disabled = true;
    stopped = false;
    lastAnswer = "";
    answerEl.hidden = true;
    answerEl.innerHTML = "";
    sourcesEl.innerHTML = "";
    setControls({}); // hide all controls until a request is in flight
    setStatus("Searching the record…", "info");

    void ask(question, token).finally(() => {
      if (submitBtn) submitBtn.disabled = false;
      abort = null;
      turnstile()?.reset(); // a Turnstile token is single-use; reset for the next ask
    });
  });
}
