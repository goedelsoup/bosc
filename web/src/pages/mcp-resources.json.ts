import type { APIRoute } from "astro";
import { activeSite, loadManifest } from "@watermark/core/bundle";

// Static endpoint: emits the MCP resource descriptors for readable bundle feeds.
// The MCP `resources/list` handler fetches this at runtime to build its response (#915).
// Each resource maps to the `watermark://{site}/feeds/{name}` URI scheme.
//
// Only feeds with a corresponding /feeds/{name}.json static endpoint are advertised —
// listing a feed that `resources/read` cannot serve breaks the list→read contract.
// Extend READABLE_FEEDS as additional static endpoints are added.
//
// Feed descriptions embed the evidentiary tag vocabulary so MCP clients inherit
// the investigative discipline when reading raw feeds.

// Feeds with a /feeds/{name}.json static endpoint. hypothesis-assessments shares
// the /feeds/hypotheses.json endpoint and is handled as a sub-key by readResource().
const READABLE_FEEDS = new Set(["timeline", "entities", "hypotheses", "hypothesis-assessments", "documents"]);

const FEED_DESCRIPTIONS: Record<string, string> = {
  records:
    "Structured extracted data from source documents. Tags: [verified] = sourced directly from a document; [inference] = derived from evidence.",
  timeline:
    "Dated events from the documentary corpus, sorted ascending. Tags: [verified] = sourced directly; [inference] = derived.",
  entities:
    "Entity graph: corporate parties, people, parcels, and relationship stubs. Do not fabricate roles or relationships not present.",
  relationships:
    "Explicit relationships between entities (ownership, contract, regulatory). Cite the source document for each.",
  people: "Named individuals linked to entities and events in the record.",
  places: "Geographic places, parcels, and zoning-relevant locations.",
  meetings:
    "Board and committee meeting records. Minutes are source documents; do not paraphrase beyond what they say.",
  documents:
    "Ingested source document collections by type (oepa, aedg, recorder, …). Each entry is an immutable evidence artifact.",
  hypotheses:
    "Boom-origin research hypotheses with signal strength. Assessments carry [verified]/[inference]/[open] evidence tags.",
  "hypothesis-assessments":
    "Per-site evidence cells for each hypothesis. Signal strength is not a conclusion — cite the supporting evidence.",
  concepts: "Glossary of domain concepts derived from the documentary record.",
  leads: "Open investigative leads sourced from GitHub issues labelled area:evidence.",
  "economics-baseline":
    "Economic baseline figures (tax increment, utility rates, public subsidy). All figures are document-sourced.",
  "hydrology-scenarios": "Water-balance scenarios for the municipal loop. Lima reference site only.",
  rsei: "EPA RSEI toxics risk scores by facility and chemical. County-level aggregates only; read methodological notes before drawing conclusions.",
};

export const GET: APIRoute = () => {
  const site = activeSite();
  const manifest = loadManifest(site);
  const resources = manifest.feeds
    .filter((f) => f.kind !== "geojson" && READABLE_FEEDS.has(f.name))
    .map((f) => ({
      uri: `watermark://${site}/feeds/${f.name}`,
      name: `${f.name.replace(/-/g, " ")} — ${site}`,
      description: FEED_DESCRIPTIONS[f.name] ?? `${f.name} bundle feed for ${site}.`,
      mimeType: f.media_type,
    }));
  return new Response(JSON.stringify(resources), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
