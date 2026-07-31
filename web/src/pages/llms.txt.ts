import type { APIRoute } from "astro";

// llms.txt — emerging standard (https://llmstxt.org/) for describing how LLMs
// should interact with a site. Analogous to robots.txt but for AI agents.
export const GET: APIRoute = ({ site }) => {
  const base = site ? site.href.replace(/\/$/, "") : "https://watermark.directory";
  const lines = [
    "# Watermark Directory",
    "",
    "> Documentary corpus of the American Sugar Creek watershed — Lima OH,",
    "> Fort Wayne IN, and surrounding Maumee basin watershed points.",
    "> Investigative-grade public-records research: evidence tagged",
    "> [verified] / [inference] / [open].",
    "",
    "## Programmatic access",
    "",
    `- MCP server manifest: ${base}/.well-known/mcp.json`,
    `- ChatGPT plugin manifest: ${base}/.well-known/ai-plugin.json (OpenAPI: ${base}/openapi.yaml)`,
    `- Corpus search (Q&A interface): ${base}/ask`,
    `- Network hub: ${base}/network`,
    "",
    "The MCP server exposes: search_corpus, search_passages, get_timeline,",
    "get_entities, get_hypotheses, get_documents, get_document, get_facts,",
    "aggregate_facts. Every result carries a structured `citation`",
    "(document_id, source, page/pages, source_url, evidence, label) —",
    "cite from the result, never from memory. Public tier: 60 req/hour per IP,",
    "100k output tokens/day. Authenticated tier available at",
    `${base}/network/connect`,
    "",
    "## Content areas",
    "",
    "- NPDES discharge permits and DMR monitoring data (EPA ECHO)",
    "- Engineering records: OPC estimates, plan sheets, design parameters",
    "- Commissioners' meeting minutes and resolutions",
    "- Timeline of watershed events with evidentiary sourcing",
    "- Entity graph: facilities, contractors, regulators, transactions",
    "- Boom-origin hypotheses with structured evidence assessments",
    "- Water-balance and stormwater model outputs (USGS NWIS, NOAA Atlas-14)",
    "",
    "## Data policy",
    "",
    "All corpus content derives from public records and is citable.",
    "Attribution required for reuse. Not licensed for AI training without",
    "explicit written permission. Evidence tags ([verified]/[inference]/[open])",
    "must be preserved when citing findings.",
    "",
    "## Optional",
    "",
    `- Sitemap: ${base}/sitemap-index.xml`,
    `- robots.txt: ${base}/robots.txt`,
  ];

  return new Response(`${lines.join("\n")}\n`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
