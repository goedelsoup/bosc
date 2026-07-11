// Ref-context for /submit. Always loaded (both the live-form and the not-yet-live
// fallback states). When the page is reached from a per-record "✎ Suggest a
// correction" deep-link —
//
//   /submit?ref_kind=record&ref_id=<rel>&ref_label=<label>
//
// — this surfaces a styled banner naming the record, and pre-fills the manual
// GitHub-issue fallback link so the record reference survives even without the
// submissions endpoint. The banner element is the single source of truth the form
// client (submit.ts) reads at submit time, so the "clear" button cleanly drops it.

const params = new URLSearchParams(location.search);
const refKind = params.get("ref_kind");
const refId = params.get("ref_id");
const refLabel = params.get("ref_label");

// Reveal only when a specific record is actually identified — `ref_kind` alone
// (no `ref_id`) is a degraded deep-link, so fall through to the general form
// rather than naming a "this record" that the URL never defined.
if (refKind && refId) {
  const banner = document.getElementById("submit-ref");
  if (banner) {
    const labelEl = document.getElementById("submit-ref-label");
    const idEl = document.getElementById("submit-ref-id");
    if (labelEl) labelEl.textContent = refLabel || refId || "this record";
    // Only show the raw id line when it adds something beyond the label.
    if (idEl && refId && refId !== refLabel) idEl.textContent = refId;

    // Expose to the form client as the single source of truth (see submit.ts).
    banner.dataset.refKind = refKind;
    if (refId) banner.dataset.refId = refId;
    if (refLabel) banner.dataset.refLabel = refLabel;
    banner.hidden = false;

    document.getElementById("submit-ref-clear")?.addEventListener("click", () => {
      banner.hidden = true;
      delete banner.dataset.refKind;
      delete banner.dataset.refId;
      delete banner.dataset.refLabel;
      // Strip the params so a reload / shared URL is a clean general submission.
      const url = new URL(location.href);
      for (const k of ["ref_kind", "ref_id", "ref_label"]) url.searchParams.delete(k);
      history.replaceState(null, "", url.pathname + url.search + url.hash);
    });
  }

  // Pre-fill the manual GitHub-issue fallback (not-yet-live state) with the record
  // reference, so the context isn't lost when the endpoint isn't available.
  const fallback = document.getElementById("submit-fallback-link") as HTMLAnchorElement | null;
  if (fallback) {
    const title = `Correction: ${refLabel || refId || "record"}`;
    const body = [
      `**Concerns:** ${[refKind, refId].filter(Boolean).join(" · ")}`,
      "",
      "_Describe the correction. Cite a page or figure if you can._",
    ].join("\n");
    const url = new URL(
      fallback.getAttribute("href") ||
        "https://github.com/watermark-directory/the-watermark-directory/issues/new",
    );
    url.searchParams.set("title", title);
    url.searchParams.set("body", body);
    fallback.href = url.toString();
  }
}
