// JSON-RPC 2.0 router for the MCP Streamable HTTP transport (#911).
// Tool implementations: #913 (search_corpus), #914 (bundle readers).
// Resource implementations: #915 (watermark://{site}/feeds/{name}).
// Tool schemas live in @watermark/core/mcpTools (shared with /network/connect, #917).

import { MCP_TOOLS } from "@watermark/core/mcpTools";
import type { HybridRetrievalEnv } from "./hybridRetrieve";
import { handleSearchCorpus } from "./mcpTools/searchCorpus";
import { handleSearchPassages } from "./mcpTools/searchPassages";
import {
  handleAggregateFacts,
  handleGetDocument,
  handleGetDocuments,
  handleGetEntities,
  handleGetFacts,
  handleGetHypotheses,
  handleGetTimeline,
} from "./mcpTools/bundleReaders";
import { listResources, readResource } from "./mcpResources";

export interface JsonRpcRequest {
  jsonrpc: string;
  id?: string | number | null;
  method: string;
  params?: unknown;
}

export interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: string | number | null;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

export class McpError extends Error {
  constructor(
    readonly code: number,
    message: string,
    readonly data?: unknown,
  ) {
    super(message);
  }
}

// Standard JSON-RPC 2.0 error codes (MCP uses the same set)
export const RPC = {
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
} as const;

// The MCP revision this server speaks. Bumped to 2025-06-18 (#1577) — the revision that
// formalizes tool `outputSchema` + result `structuredContent`, which every tool now declares
// and returns. No new capability flag is needed — `structuredContent` is implied by a tool
// carrying an `outputSchema`.
export const PROTOCOL_VERSION = "2025-06-18";
// The revisions this server can actually speak. Negotiation echoes the client's requested
// version only when it is one of these; anything else (a future or unrecognized value) falls back
// to PROTOCOL_VERSION — the server offers its latest and the client decides. 2025-03-26 is the
// original transport revision this server was written against; the 2025-06-18 fields are additive,
// so a 2025-03-26 client just ignores structuredContent/outputSchema.
const SUPPORTED_PROTOCOL_VERSIONS: ReadonlySet<string> = new Set(["2025-06-18", "2025-03-26"]);
const SERVER_INFO = { name: "watermark-directory", version: "1.0.0" };

function parseRequest(body: unknown): JsonRpcRequest {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new McpError(RPC.INVALID_REQUEST, "Expected a JSON-RPC 2.0 request object");
  }
  const r = body as Record<string, unknown>;
  if (r.jsonrpc !== "2.0") {
    throw new McpError(RPC.INVALID_REQUEST, 'jsonrpc must be "2.0"');
  }
  if (typeof r.method !== "string") {
    throw new McpError(RPC.INVALID_REQUEST, "method must be a string");
  }
  return r as unknown as JsonRpcRequest;
}

function handleInitialize(params: unknown): unknown {
  const p = (params ?? {}) as Record<string, unknown>;
  const clientVersion = typeof p.protocolVersion === "string" ? p.protocolVersion : "";
  // Negotiate down only to a revision we actually support; otherwise offer our latest.
  const negotiated = SUPPORTED_PROTOCOL_VERSIONS.has(clientVersion) ? clientVersion : PROTOCOL_VERSION;
  return {
    protocolVersion: negotiated,
    capabilities: {
      tools: { listChanged: false },
      resources: { subscribe: false, listChanged: false },
    },
    serverInfo: SERVER_INFO,
  };
}

function handleToolsList(): unknown {
  return { tools: MCP_TOOLS };
}

/**
 * Derive the MCP `structuredContent` (spec 2025-06-18) from a handler's `content` (#1577).
 * Every tool handler already returns exactly one text block whose `text` is the JSON
 * serialization of its governed envelope, so re-parsing it is the single source of truth —
 * `structuredContent` is guaranteed to match the `content` block byte-for-byte, and no handler
 * needs to return the object twice. Returns undefined only for a non-JSON or non-object body
 * (no current handler produces one), so `structuredContent` is simply omitted there.
 */
function structuredFromContent(content: Array<{ type: string; text: string }>): unknown | undefined {
  if (content.length !== 1 || content[0]?.type !== "text") return undefined;
  try {
    const parsed: unknown = JSON.parse(content[0].text);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : undefined;
  } catch {
    return undefined;
  }
}

async function handleToolsCall(
  params: unknown,
  requestUrl: string,
  env: HybridRetrievalEnv,
): Promise<unknown> {
  const p = (params ?? {}) as Record<string, unknown>;
  const name = p.name;
  if (typeof name !== "string") {
    throw new McpError(RPC.INVALID_PARAMS, "params.name must be a string");
  }
  const tool = MCP_TOOLS.find((t) => t.name === name);
  if (!tool) {
    throw new McpError(RPC.INVALID_PARAMS, `Unknown tool: ${name}`);
  }

  const toolParams = p.arguments ?? {};

  let content: Array<{ type: string; text: string }>;
  switch (name) {
    case "search_corpus":
      content = await handleSearchCorpus(toolParams, requestUrl, env);
      break;
    case "search_passages":
      content = await handleSearchPassages(toolParams, requestUrl, env);
      break;
    case "get_timeline":
      content = await handleGetTimeline(toolParams, requestUrl);
      break;
    case "get_entities":
      content = await handleGetEntities(toolParams, requestUrl);
      break;
    case "get_hypotheses":
      content = await handleGetHypotheses(toolParams, requestUrl);
      break;
    case "get_documents":
      content = await handleGetDocuments(toolParams, requestUrl);
      break;
    case "get_document":
      content = await handleGetDocument(toolParams, requestUrl);
      break;
    case "get_facts":
      content = await handleGetFacts(toolParams, requestUrl);
      break;
    case "aggregate_facts":
      content = await handleAggregateFacts(toolParams, requestUrl);
      break;
    default:
      throw new McpError(RPC.INVALID_PARAMS, `Tool "${name}" has no implementation`);
  }

  // Alongside the back-compat `content` text block, return the MCP `structuredContent`
  // (#1577) that validates against the tool's declared `outputSchema`.
  const result: { content: typeof content; isError: boolean; structuredContent?: unknown } = {
    content,
    isError: false,
  };
  const structuredContent = structuredFromContent(content);
  if (structuredContent !== undefined) result.structuredContent = structuredContent;
  return result;
}

export async function dispatch(
  body: unknown,
  requestUrl: string,
  env: HybridRetrievalEnv = {},
): Promise<JsonRpcResponse> {
  let req: JsonRpcRequest;
  try {
    req = parseRequest(body);
  } catch (e) {
    const err = e instanceof McpError ? e : new McpError(RPC.PARSE_ERROR, "Parse error");
    return { jsonrpc: "2.0", id: null, error: { code: err.code, message: err.message } };
  }

  const id = req.id ?? null;

  // Notifications (no id) get no response — caller should 202 directly
  if (req.id === undefined && req.method === "notifications/initialized") {
    return { jsonrpc: "2.0", id: null, result: null };
  }

  try {
    let result: unknown;
    switch (req.method) {
      case "initialize":
        result = handleInitialize(req.params);
        break;
      case "tools/list":
        result = handleToolsList();
        break;
      case "tools/call":
        result = await handleToolsCall(req.params, requestUrl, env);
        break;
      case "resources/list":
        result = await listResources(requestUrl);
        break;
      case "resources/read":
        result = await readResource(req.params, requestUrl);
        break;
      default:
        throw new McpError(RPC.METHOD_NOT_FOUND, `Method not found: ${req.method}`);
    }
    return { jsonrpc: "2.0", id, result };
  } catch (e) {
    const err = e instanceof McpError ? e : new McpError(RPC.INTERNAL_ERROR, "Internal error");
    return {
      jsonrpc: "2.0",
      id,
      error: { code: err.code, message: err.message, data: err.data },
    };
  }
}
