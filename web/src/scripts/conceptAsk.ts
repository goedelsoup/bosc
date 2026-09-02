// Hydrates the "ask this concept" widget (#1575, epic #1560 D2). Reads the concept's corpus
// neighborhood embedded by ConceptAsk.astro, builds a client-side BM25 retriever over it, and
// renders cited corpus nodes as the reader types — instant, offline, no server, no generation.
// Distinct from site-wide /ask: scoped to one concept's neighborhood, and it returns cited nodes,
// never prose. The record is the answer; the widget only points at it.
import { type NeighborNode, makeRetriever } from "~/lib/conceptAsk";

/** Singular kind labels for a hit chip (KIND_META's are plural section headers). */
const KIND_LABEL: Record<string, string> = {
  site: "Site",
  entity: "Entity",
  person: "Person",
  concept: "Concept",
  hypothesis: "Hypothesis",
  lead: "Lead",
  "open-question": "Open question",
  relation: "Relationship",
  node: "Node",
};
/** The evidence tags that are real evidence (rendered as a tinted pill); others get no pill. */
const EVIDENCE = new Set(["verified", "inference", "reference", "open"]);
const RESULT_COUNT = 8;

function esc(s: string): string {
  return s.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string,
  );
}

// `node_text` is `label · description? · class · …meta`, so the segment after the label is the
// node's description when it has one, or the bare class token when it doesn't.
const CLASS_WORDS = new Set(["concept", "relation", "artifact", "question", "hypothesis", "record"]);

/** The reader-facing gloss — the node's description segment, or empty when it carries none. */
function snippet(node: NeighborNode): string {
  const desc = (node.text.split(" · ")[1] ?? "").trim();
  if (!desc || CLASS_WORDS.has(desc.toLowerCase())) return "";
  return desc.length > 180 ? `${desc.slice(0, 179)}…` : desc;
}

function renderHit(node: NeighborNode): string {
  const kind = `<span class="ask-hit-kind">${esc(KIND_LABEL[node.kind] ?? node.kind)}</span>`;
  const evidence =
    node.evidence && EVIDENCE.has(node.evidence)
      ? `<span class="evidence evidence-${node.evidence}"><span class="evidence-dot" aria-hidden="true"></span>[${node.evidence}]</span>`
      : "";
  const label = esc(node.label);
  const title = node.href
    ? `<a href="${esc(node.href)}">${label}</a>`
    : `<span class="ask-hit-label">${label}</span>`;
  const gloss = snippet(node);
  const body = gloss ? `<p class="ask-hit-snippet">${esc(gloss)}</p>` : "";
  return `<li class="ask-hit"><div class="ask-hit-head">${kind}${evidence}</div><div class="ask-hit-title">${title}</div>${body}</li>`;
}

function init(root: HTMLElement): void {
  const raw = root.querySelector<HTMLScriptElement>("script[data-concept-ask-nodes]")?.textContent;
  if (!raw) return;
  let nodes: NeighborNode[];
  try {
    nodes = JSON.parse(raw) as NeighborNode[];
  } catch {
    return;
  }
  const input = root.querySelector<HTMLInputElement>("input[type='search']");
  const results = root.querySelector<HTMLElement>(".ask-results");
  const status = root.querySelector<HTMLElement>(".ask-status");
  if (!input || !results) return;

  const retrieve = makeRetriever(nodes);
  // The default view: the un-ranked neighborhood, so the affordance is useful before any query.
  const renderDefault = (): void => {
    results.innerHTML = nodes.map(renderHit).join("");
    if (status)
      status.textContent = `${nodes.length} corpus node${nodes.length === 1 ? "" : "s"} near this concept`;
  };
  const renderQuery = (query: string): void => {
    const hits = retrieve(query, RESULT_COUNT);
    if (hits.length === 0) {
      results.innerHTML = `<li class="ask-empty">Nothing in this concept's corpus neighborhood matches. Try the site-wide <a href="/ask">Ask</a>.</li>`;
      if (status) status.textContent = "No matches in this neighborhood";
      return;
    }
    results.innerHTML = hits.map(renderHit).join("");
    if (status) status.textContent = `${hits.length} of ${nodes.length} nodes match`;
  };

  let timer = 0;
  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      const query = input.value.trim();
      if (query) renderQuery(query);
      else renderDefault();
    }, 120);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      input.value = "";
      renderDefault();
    }
  });
  renderDefault();
}

for (const root of document.querySelectorAll<HTMLElement>(".concept-ask")) init(root);
