// Unit tests for the /api/ask Bearer service-token bypass (#1578).

import { describe, expect, it } from "vitest";
import { isPluginAuthorized } from "@watermark/functions/api/_lib/askPluginAuth";

const req = (auth?: string): Request =>
  new Request("https://bosc.test/api/ask", {
    method: "POST",
    headers: auth ? { authorization: auth } : {},
  });

describe("isPluginAuthorized", () => {
  it("authorizes a matching Bearer token", () => {
    expect(isPluginAuthorized(req("Bearer s3cret"), { ASK_PLUGIN_TOKEN: "s3cret" })).toBe(true);
  });

  it("accepts a case-insensitive scheme", () => {
    expect(isPluginAuthorized(req("bearer s3cret"), { ASK_PLUGIN_TOKEN: "s3cret" })).toBe(true);
  });

  it("rejects a mismatched token", () => {
    expect(isPluginAuthorized(req("Bearer nope"), { ASK_PLUGIN_TOKEN: "s3cret" })).toBe(false);
  });

  it("rejects a token that is a prefix of the secret (length guard)", () => {
    expect(isPluginAuthorized(req("Bearer s3cre"), { ASK_PLUGIN_TOKEN: "s3cret" })).toBe(false);
  });

  it("rejects when no Authorization header is present", () => {
    expect(isPluginAuthorized(req(), { ASK_PLUGIN_TOKEN: "s3cret" })).toBe(false);
  });

  it("rejects a non-Bearer scheme", () => {
    expect(isPluginAuthorized(req("Basic s3cret"), { ASK_PLUGIN_TOKEN: "s3cret" })).toBe(false);
  });

  it("is disabled (always false) when no token is configured", () => {
    expect(isPluginAuthorized(req("Bearer anything"), {})).toBe(false);
    expect(isPluginAuthorized(req("Bearer anything"), { ASK_PLUGIN_TOKEN: "" })).toBe(false);
  });
});
