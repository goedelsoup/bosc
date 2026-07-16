/**
 * The Ask-portal faithfulness eval set (#215).
 *
 * Two tiers run against these fixtures:
 *  - the **fixture tier** (askEval.test.ts) is deterministic and always runs in CI: it
 *    asserts retrieval grounding (in-corpus questions surface the right source) and the
 *    deterministic refusal (out-of-corpus questions retrieve nothing, so the endpoint
 *    refuses before any model call) — guarding against retrieval/prompt regressions.
 *  - the **live tier** (askEval.live.test.ts) is gated on ANTHROPIC_API_KEY and actually
 *    calls the model, asserting grounded answers cite and hallucination-bait is refused.
 *
 * The corpus below is a compact stand-in for the real bundle's domains (OPC estimates,
 * permits, the confidentiality agreement, corridor entities, commissioners' meetings, the
 * glossary) — enough for BM25 to separate on-topic from off-topic deterministically.
 */
import type { AskUnit } from "@watermark/functions/api/_lib/retrieval";

export const CORPUS: AskUnit[] = [
  {
    id: "records:opc-summary",
    feed: "records",
    title: "Roundabouts OPC — summary",
    url: "/network/american-sugar-creek-allen-co/site/records/opc/",
    text: "opinion of probable cost estimate roadway subtotal earthwork drainage roundabout intersection tetra tech aedg six estimates",
    source: "data/documents/aedg/PRR-01-bundle.ocr.pdf",
    page: 318,
    source_kind: "document",
    verified: true,
  },
  {
    id: "records:npdes-permit",
    feed: "records",
    title: "Ohio EPA NPDES permit",
    url: "/network/american-sugar-creek-allen-co/site/records/permits-npdes/",
    text: "ohio epa npdes permit stormwater discharge authorization facility outfall monitoring",
    source: "data/extracted/oepa/npdes.yaml",
    source_kind: "document",
    verified: true,
  },
  {
    id: "timeline:nda",
    feed: "timeline",
    title: "Confidentiality agreement signed",
    url: "/network/american-sugar-creek-allen-co/timeline",
    text: "the parties executed a nondisclosure confidentiality agreement covering the project before the public reveal",
    source: "data/extracted/legal/nda.yaml",
    source_kind: "document",
    verified: true,
  },
  {
    id: "entities:amazon",
    feed: "entities",
    title: "Amazon.com Services LLC",
    url: "/wiki/entities/amazon-com-services-llc/",
    text: "amazon cloud hyperscaler datacenter operator candidate consumer demand-fit",
    source: "data/extracted/entities/graph.yaml",
    source_kind: "document",
  },
  {
    id: "meetings:commissioners",
    feed: "meetings",
    title: "Allen County Commissioners meeting",
    url: "/network/american-sugar-creek-allen-co/site/legal#meetings",
    text: "allen county commissioners meeting resolution corridor parcels approval roadway easement vote",
    source: "data/documents/commissioners/meetings/2024.pdf",
    source_kind: "document",
    verified: true,
  },
  {
    id: "concepts:opc",
    feed: "concepts",
    title: "Opinion of Probable Cost",
    url: "/wiki/concepts/opinion-of-probable-cost/",
    text: "opc engineering construction estimate line items markup contingency glossary definition",
    source_kind: "derived",
  },
];

/** Questions the record CAN answer — retrieval must surface a source from `expectFeeds`. */
export const IN_CORPUS: { question: string; expectFeeds: string[] }[] = [
  { question: "What do the roundabout cost estimates total?", expectFeeds: ["records", "concepts"] },
  { question: "Who are the parties to the confidentiality agreement?", expectFeeds: ["timeline"] },
  { question: "What NPDES permit did Ohio EPA issue?", expectFeeds: ["records"] },
  { question: "Is Amazon a cloud-consumer candidate?", expectFeeds: ["entities"] },
  { question: "What did the county commissioners decide about the corridor?", expectFeeds: ["meetings"] },
];

/** Off-topic questions with no corpus vocabulary — must retrieve nothing ⇒ refuse. */
export const OUT_OF_CORPUS: string[] = [
  "What is the recipe for banana bread?",
  "Who won the 2020 World Series?",
  "What is the boiling point of mercury?",
  "Recommend a good science fiction novel.",
];

/**
 * Hallucination-bait: questions that DO retrieve (they share vocabulary with the corpus)
 * but whose specific claim no source supports — the model must refuse rather than invent.
 * Exercised by the live tier; here for documentation + reuse.
 */
export const HALLUCINATION_BAIT: string[] = [
  // Original two
  "How much did Amazon pay for the roundabouts?",
  "What was the secret price named in the confidentiality agreement?",
  // Added: specific vote details not in the source
  "Which commissioner voted against the corridor resolution?",
  // Added: Tetra Tech contract terms not mentioned in OPC sources
  "What discount did Tetra Tech receive on the roundabout contract?",
  // Added: outfall identifier that retrieves the NPDES source but is never named
  "What outfall number did the NPDES permit assign to the facility?",
  // Added: termination clause that retrieves the NDA source but is never stated
  "When was the confidentiality agreement terminated?",
];
