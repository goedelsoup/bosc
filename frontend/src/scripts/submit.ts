// Client for the submissions form (/submit). Framework-free, in the style of
// search.ts. Reads an optional target prefill from the query string, takes the
// Turnstile token the widget injects, and POSTs JSON to the endpoint.
//
// A page can deep-link a pre-filled target:
//   /submit?ref_kind=record&ref_id=<rel>&ref_label=<label>
// (the per-page "suggest a correction" affordance, when wired up.)

const form = document.getElementById("submit-form") as HTMLFormElement | null;
const statusEl = document.getElementById("submit-status");

if (form && statusEl) {
  const endpoint = form.dataset.endpoint || "/api/submit";

  const params = new URLSearchParams(location.search);
  const refKind = params.get("ref_kind");
  const refId = params.get("ref_id");
  const refLabel = params.get("ref_label");

  const targetNote = document.getElementById("submit-target");
  if (refKind && targetNote) {
    const bits = [refKind, refId, refLabel].filter(Boolean).join(" · ");
    targetNote.textContent = `Concerns: ${bits}`;
    targetNote.hidden = false;
  }

  const setStatus = (msg: string, kind: "ok" | "err" | "info"): void => {
    statusEl.textContent = msg;
    statusEl.dataset.kind = kind;
  };

  const turnstile = (): { reset: () => void } | undefined =>
    (window as unknown as { turnstile?: { reset: () => void } }).turnstile;

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(form);

    const token = String(data.get("cf-turnstile-response") || "");
    if (!token) {
      setStatus("Please complete the verification challenge.", "err");
      return;
    }
    const body = String(data.get("body") || "").trim();
    if (!body) {
      setStatus("Please describe the tip or correction.", "err");
      return;
    }

    const payload: Record<string, unknown> = {
      kind: String(data.get("kind") || "tip"),
      body,
      turnstile_token: token,
      page_url: location.href,
    };
    const evidence = String(data.get("evidence_url") || "").trim();
    if (evidence) payload.evidence_url = evidence;
    if (refKind) {
      payload.target = {
        ref_kind: refKind,
        ...(refId ? { ref_id: refId } : {}),
        ...(refLabel ? { ref_label: refLabel } : {}),
      };
    }

    const submitBtn = form.querySelector<HTMLButtonElement>("button[type=submit]");
    if (submitBtn) submitBtn.disabled = true;
    setStatus("Sending…", "info");

    void fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(async (r) => {
        const out = (await r.json().catch(() => ({}))) as {
          issue_url?: string;
          error?: string;
          deduped?: boolean;
        };
        if (r.ok && out.issue_url) {
          form.reset();
          const safe = out.issue_url.replace(/"/g, "%22");
          const verb = out.deduped ? "already tracked as" : "filed as";
          statusEl.innerHTML = `Thank you — ${verb} <a href="${safe}">${safe}</a> for review.`;
          statusEl.dataset.kind = "ok";
          return;
        }
        setStatus(out.error ? `Couldn't send: ${out.error}` : "Couldn't send your submission.", "err");
        if (submitBtn) submitBtn.disabled = false;
        turnstile()?.reset(); // a Turnstile token is single-use; reset for a retry
      })
      .catch(() => {
        setStatus("Network error — please try again.", "err");
        if (submitBtn) submitBtn.disabled = false;
        turnstile()?.reset();
      });
  });
}
