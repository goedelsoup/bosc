// Validation guard for the ChatGPT-plugin discovery files (#1578):
//   web/public/.well-known/ai-plugin.json  — the plugin manifest
//   web/public/openapi.yaml                — the OpenAPI 3 spec it points at
//
// Asserts both parse, carry the required fields, are internally consistent (the manifest's
// api.url resolves to the served spec; logo_url points at a real public asset), and that the
// spec matches the live /api/ask contract (docs/ask-api.md, functions/api/ask.ts) — the
// operation, its Bearer security, and the AskResult response shape.

import { existsSync } from "node:fs";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parse as parseYaml } from "yaml";

const publicDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../public");
const readPublic = (rel: string): string => readFileSync(path.join(publicDir, rel), "utf8");

const ORIGIN = "https://watermark.directory";

// biome-ignore lint/suspicious/noExplicitAny: parsed JSON/YAML documents are structurally asserted below.
type Any = any;

describe("ai-plugin.json manifest", () => {
  const manifest: Any = JSON.parse(readPublic(".well-known/ai-plugin.json"));

  it("declares the v1 plugin schema with model-facing names + descriptions", () => {
    expect(manifest.schema_version).toBe("v1");
    expect(manifest.name_for_human).toBeTruthy();
    // name_for_model must be a bare identifier (ChatGPT rule).
    expect(manifest.name_for_model).toMatch(/^[a-zA-Z0-9_]+$/);
    expect(manifest.description_for_human).toBeTruthy();
    expect(manifest.description_for_model).toBeTruthy();
  });

  it("instructs the model to cite sources + honor the evidence tags", () => {
    const d: string = manifest.description_for_model;
    expect(d.toLowerCase()).toContain("cite");
    expect(d).toContain("[verified]");
    expect(d).toContain("[inference]");
    expect(d).toContain("refused");
  });

  it("uses the service_http Bearer auth tier", () => {
    expect(manifest.auth.type).toBe("service_http");
    expect(manifest.auth.authorization_type).toBe("bearer");
    expect(manifest.auth.verification_tokens).toBeTypeOf("object");
  });

  it("points api.url at the served OpenAPI spec on this origin", () => {
    expect(manifest.api.type).toBe("openapi");
    expect(manifest.api.url).toBe(`${ORIGIN}/openapi.yaml`);
    // The referenced spec is actually shipped in public/.
    expect(existsSync(path.join(publicDir, "openapi.yaml"))).toBe(true);
  });

  it("carries a logo_url that resolves to a committed public asset", () => {
    expect(manifest.logo_url.startsWith(`${ORIGIN}/`)).toBe(true);
    const asset = manifest.logo_url.slice(`${ORIGIN}/`.length);
    expect(existsSync(path.join(publicDir, asset))).toBe(true);
  });

  it("has an https legal_info_url and no personal contact email", () => {
    expect(manifest.legal_info_url).toMatch(/^https:\/\//);
    // The issue asks that we avoid a personal address — a noreply placeholder is used.
    expect(manifest.contact_email).not.toMatch(/gmail|hotmail|outlook|yahoo/i);
  });
});

describe("openapi.yaml spec", () => {
  const spec: Any = parseYaml(readPublic("openapi.yaml"));

  it("is a valid OpenAPI 3 document served from this origin", () => {
    expect(String(spec.openapi)).toMatch(/^3\./);
    expect(spec.info?.title).toBeTruthy();
    expect(spec.info?.version).toBeTruthy();
    expect(spec.servers?.[0]?.url).toBe(ORIGIN);
  });

  it("documents POST /api/ask as askCorpus behind the bearerAuth scheme", () => {
    const op = spec.paths?.["/api/ask"]?.post;
    expect(op).toBeTruthy();
    expect(op.operationId).toBe("askCorpus");
    // The operation requires the bearer scheme, and the scheme is defined as HTTP bearer.
    expect(op.security).toEqual([{ bearerAuth: [] }]);
    const scheme = spec.components?.securitySchemes?.bearerAuth;
    expect(scheme).toMatchObject({ type: "http", scheme: "bearer" });
  });

  it("describes the request body matching the live askSchema limits", () => {
    const schema = spec.paths["/api/ask"].post.requestBody.content["application/json"].schema;
    const req = schema.$ref ? spec.components.schemas[schema.$ref.split("/").pop()] : schema;
    expect(req.required).toContain("question");
    expect(req.properties.question.minLength).toBe(3);
    expect(req.properties.question.maxLength).toBe(1000);
    expect(req.additionalProperties).toBe(false);
  });

  it("describes the 200 response with the AskResult contract shape", () => {
    const ref = spec.paths["/api/ask"].post.responses["200"].content["application/json"].schema.$ref;
    const result = spec.components.schemas[ref.split("/").pop()];
    // Mirrors AskResult in functions/api/_lib/ask.ts (answer/citations/refused/model[/usage]).
    for (const key of ["answer", "citations", "refused", "model"]) {
      expect(result.properties).toHaveProperty(key);
      expect(result.required).toContain(key);
    }
    expect(result.properties.usage).toBeTruthy();
    // Citations resolve to the AskCitation schema with a [n] marker + a deep link.
    const citationRef = result.properties.citations.items.$ref;
    const citation = spec.components.schemas[citationRef.split("/").pop()];
    for (const key of ["marker", "id", "feed", "title", "url"]) {
      expect(citation.properties).toHaveProperty(key);
    }
  });
});
