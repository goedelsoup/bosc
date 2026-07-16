// MCP Playground client (#918). Framework-free, in the style of ask.ts.
// Calls POST /api/mcp (JSON-RPC 2.0 + SSE) and renders tool results with
// provenance-tagged rows. Handles: tool selection, form field generation,
// example injection, SSE streaming response, abort, and tab switching.

import { drainSse } from "@watermark/functions/api/_lib/sse";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ToolSchema {
  label: string;
  desc: string;
  fields: Array<{
    name: string;
    label: string;
    required?: boolean;
    type?: string;
    placeholder?: string;
  }>;
}

interface CorpusResult {
  _type?: string;
  evidence?: string;
  source?: string;
  page?: number;
  text?: string;
  // timeline / entity / hypothesis / document fields
  date?: string;
  category?: string;
  name?: string;
  role?: string;
  description?: string;
  collection?: string;
}

type EvidenceKind = "verified" | "inference" | "open" | "gap" | "key" | "filename";

// ─── DOM handles ─────────────────────────────────────────────────────────────

const page = document.querySelector<HTMLElement>(".mcp-page");
const endpoint = page?.dataset.endpoint ?? "/api/mcp";

const form = document.getElementById("mcp-form") as HTMLFormElement | null;
const fieldsEl = document.getElementById("mcp-fields");
const toolLabelEl = document.getElementById("mcp-tool-label");
const toolDescEl = document.getElementById("mcp-tool-desc");
const exampleBtn = document.getElementById("mcp-example-btn") as HTMLButtonElement | null;
const submitBtn = document.getElementById("mcp-submit") as HTMLButtonElement | null;
const abortBtn = document.getElementById("mcp-abort") as HTMLButtonElement | null;

const resultEmpty = document.getElementById("mcp-result-empty");
const resultRows = document.getElementById("mcp-result-rows");
const rawPre = document.getElementById("mcp-raw-pre");
const metaEl = document.getElementById("mcp-response-meta");

const formWrap = document.querySelector<HTMLElement>(".param-form-wrap");
const schemas: Record<string, ToolSchema> = formWrap?.dataset.schemas
  ? (JSON.parse(formWrap.dataset.schemas) as Record<string, ToolSchema>)
  : {};

// ─── Session state ────────────────────────────────────────────────────────────

let sessionId: string | null = null;
let selectedTool = "search_corpus";
let abort: AbortController | null = null;
let rpcId = 1;

// ─── Tool picker ──────────────────────────────────────────────────────────────

for (const row of document.querySelectorAll<HTMLButtonElement>(".tool-row")) {
  row.addEventListener("click", () => {
    const tool = row.dataset.tool;
    if (!tool || tool === selectedTool) return;
    selectTool(tool);
  });
}

function selectTool(tool: string): void {
  selectedTool = tool;

  // Update picker active state
  for (const row of document.querySelectorAll<HTMLButtonElement>(".tool-row")) {
    const active = row.dataset.tool === tool;
    row.setAttribute("aria-selected", active ? "true" : "false");
    row.classList.toggle("tool-row--active", active);
  }

  // Update form header
  const schema = schemas[tool];
  if (!schema || !fieldsEl || !toolLabelEl || !toolDescEl) return;
  toolLabelEl.textContent = schema.label;
  toolDescEl.textContent = schema.desc;

  // Rebuild fields
  rebuildFields(schema);
}

function rebuildFields(schema: ToolSchema): void {
  if (!fieldsEl) return;
  fieldsEl.innerHTML = "";

  const isWide = schema.fields.length >= 3;
  const pairFields = isWide ? schema.fields.slice(1, 3) : [];
  const singleFields = isWide ? [schema.fields[0], ...schema.fields.slice(3)] : schema.fields;

  for (const f of singleFields) {
    fieldsEl.appendChild(buildFieldGroup(f, ""));
  }

  if (pairFields.length === 2) {
    const row = document.createElement("div");
    row.className = "field-row-2";
    row.appendChild(buildFieldGroup(pairFields[0], ""));
    row.appendChild(buildFieldGroup(pairFields[1], ""));
    fieldsEl.appendChild(row);
  }

  // Re-bind example button for this tool
  if (exampleBtn) {
    exampleBtn.onclick = () => loadExample(schema);
  }
}

function buildFieldGroup(f: ToolSchema["fields"][number], value: string): HTMLDivElement {
  const id = `mcp-f-${f.name}`;
  const wrap = document.createElement("div");
  wrap.className = `field-group${f.name === "limit" ? " field-group--narrow" : ""}`;

  const label = document.createElement("label");
  label.className = "field-label";
  label.htmlFor = id;
  label.innerHTML = f.label.toUpperCase();
  if (f.required) {
    label.innerHTML += `<span class="field-required" aria-hidden="true">*</span>`;
  } else {
    label.innerHTML += `<span class="field-optional">— optional</span>`;
  }

  const input = document.createElement("input");
  input.id = id;
  input.className = "field-input";
  input.type = f.type ?? "text";
  input.name = f.name;
  input.dataset.field = f.name;
  if (f.placeholder) input.placeholder = f.placeholder;
  if (f.required) input.required = true;
  if (value) input.value = value;

  wrap.appendChild(label);
  wrap.appendChild(input);
  return wrap;
}

// ─── Example injection ────────────────────────────────────────────────────────

const EXAMPLES: Record<string, Record<string, string>> = {
  search_corpus: { query: "water discharge permit Lima" },
  get_timeline: { since: "2020-01-01" },
  get_entities: { type: "company" },
  get_hypotheses: {},
  get_documents: { collection: "oepa" },
};

function loadExample(schema: ToolSchema): void {
  const ex = EXAMPLES[selectedTool] ?? {};
  for (const f of schema.fields) {
    const el = document.querySelector<HTMLInputElement>(`[data-field="${f.name}"]`);
    if (el && ex[f.name]) el.value = ex[f.name];
  }
}

// Wire the default example button (search_corpus rendered statically)
if (exampleBtn) {
  exampleBtn.addEventListener("click", () => {
    const schema = schemas[selectedTool];
    if (schema) loadExample(schema);
  });
}

// ─── MCP JSON-RPC client ──────────────────────────────────────────────────────

// Captures the Mcp-Session-Id response header (spec: only the initialize response carries it)
async function initSession(): Promise<void> {
  if (sessionId) return;
  const id = rpcId++;
  const body = JSON.stringify({
    jsonrpc: "2.0",
    id,
    method: "initialize",
    params: {
      protocolVersion: "2025-03-26",
      clientInfo: { name: "mcp-playground", version: "1.0.0" },
      capabilities: {},
    },
  });
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  sessionId = res.headers.get("mcp-session-id");
  // Send the initialized notification (no response expected)
  if (sessionId) {
    void fetch(endpoint, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "mcp-session-id": sessionId,
      },
      body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
    });
  }
}

// ─── Form submission ──────────────────────────────────────────────────────────

form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!form) return;

  // Collect params from current fields
  const params: Record<string, unknown> = {};
  for (const input of form.querySelectorAll<HTMLInputElement>("[data-field]")) {
    const key = input.dataset.field;
    if (key && input.value.trim()) {
      params[key] = input.type === "number" ? Number(input.value) : input.value.trim();
    }
  }

  setStreaming(true);
  clearResults();

  try {
    // Ensure we have a session
    await initSession();

    abort = new AbortController();
    const signal = abort.signal;
    const t0 = performance.now();
    const rpcParams = { name: selectedTool, arguments: params };

    // POST to the MCP endpoint
    const id = rpcId++;
    const reqBody = JSON.stringify({
      jsonrpc: "2.0",
      id,
      method: "tools/call",
      params: rpcParams,
    });
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (sessionId) headers["mcp-session-id"] = sessionId;

    const res = await fetch(endpoint, {
      method: "POST",
      headers,
      body: reqBody,
      signal,
    });

    const ms = Math.round(performance.now() - t0);
    const ct = res.headers.get("content-type") ?? "";
    let rpcResponse: unknown;
    let rawText: string;

    if (ct.includes("text/event-stream")) {
      rawText = await res.text();
      const buf = rawText;
      const { events } = drainSse(buf);
      for (const evt of events) {
        if (evt.event === "message" || evt.event === "") {
          try {
            rpcResponse = JSON.parse(evt.data);
          } catch {
            /* skip */
          }
        }
      }
    } else {
      rawText = await res.text();
      try {
        rpcResponse = JSON.parse(rawText);
      } catch {
        /* ignore */
      }
    }

    renderResponse(rpcResponse, rawText, ms);
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      setMeta("Aborted.");
    } else {
      const msg = err instanceof Error ? err.message : String(err);
      renderError(msg);
    }
  } finally {
    setStreaming(false);
    abort = null;
  }
});

abortBtn?.addEventListener("click", () => {
  abort?.abort();
});

// ─── Rendering ────────────────────────────────────────────────────────────────

function setStreaming(on: boolean): void {
  if (submitBtn) submitBtn.disabled = on;
  if (abortBtn) abortBtn.disabled = !on;
  if (on) setMeta("Calling…");
}

function clearResults(): void {
  if (resultRows) {
    resultRows.innerHTML = "";
    resultRows.hidden = true;
  }
  if (resultEmpty) resultEmpty.hidden = false;
  if (rawPre) rawPre.textContent = "";
  setMeta("");
}

function setMeta(text: string): void {
  if (metaEl) metaEl.textContent = text;
}

function evBadge(kind: EvidenceKind, label?: string): string {
  const isFile = kind === "filename";
  return `<span class="ev-badge ev-${kind}">${isFile ? (label ?? "") : `[${label ?? kind}]`}</span>`;
}

function renderResponse(data: unknown, raw: string, ms: number): void {
  // Show raw
  if (rawPre) rawPre.textContent = tryPrettyJson(raw);

  const rpc = data as { result?: { content?: CorpusResult[] }; error?: { message?: string } } | null;
  if (!rpc) {
    renderError("No response received.");
    return;
  }
  if (rpc.error) {
    renderError(rpc.error.message ?? "Unknown error");
    return;
  }

  const content = rpc.result?.content ?? [];

  if (resultEmpty) resultEmpty.hidden = true;
  if (resultRows) resultRows.hidden = false;

  if (content.length === 0) {
    if (resultEmpty) {
      resultEmpty.hidden = false;
      const label = resultEmpty.querySelector(".rv-empty-label");
      if (label) label.textContent = "No results returned.";
    }
    setMeta(`0 results · ${ms} ms`);
    return;
  }

  const html = content.map((r) => buildResultRow(r)).join("");
  if (resultRows) resultRows.innerHTML = html;
  setMeta(`${content.length} result${content.length !== 1 ? "s" : ""} · ${ms} ms`);
}

function buildResultRow(r: CorpusResult): string {
  const evidence = (r.evidence ?? "open") as EvidenceKind;
  const source = r.source ?? "";
  const page = r.page != null ? `p. ${r.page}` : "";
  const text = r.text ?? r.description ?? JSON.stringify(r);

  return `
    <div class="result-row">
      <div class="result-meta">
        ${evBadge(evidence, evidence)}
        ${source ? evBadge("filename", source) : ""}
        ${page ? `<span class="result-page">${esc(page)}</span>` : ""}
      </div>
      <p class="result-text">${esc(text)}</p>
    </div>
  `;
}

function renderError(msg: string): void {
  if (resultEmpty) {
    resultEmpty.hidden = false;
    const label = resultEmpty.querySelector(".rv-empty-label");
    if (label) label.textContent = `Error: ${msg}`;
  }
  setMeta("Error");
}

function tryPrettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ─── Tab switching ────────────────────────────────────────────────────────────

for (const tab of document.querySelectorAll<HTMLButtonElement>(".rv-tab")) {
  tab.addEventListener("click", () => {
    const name = tab.dataset.tab;
    if (!name) return;

    for (const t of document.querySelectorAll<HTMLButtonElement>(".rv-tab")) {
      const active = t.dataset.tab === name;
      t.classList.toggle("rv-tab--active", active);
      t.setAttribute("aria-selected", active ? "true" : "false");
    }

    const resultPane = document.getElementById("mcp-result-pane");
    const rawPane = document.getElementById("mcp-raw-pane");
    if (resultPane) resultPane.hidden = name !== "result";
    if (rawPane) rawPane.hidden = name !== "raw";
  });
}
