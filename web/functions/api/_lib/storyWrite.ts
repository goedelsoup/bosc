// The server-side Story write path (#1095): compile the submitted source against the runtime
// catalog and derive the persistable `StoryWrite` (SDM + refs). This is the "compile-once" half of
// the compile-once-store-run-many split — it runs the #1094 compiler server-side (never trusts a
// client-supplied SDM), so every handle is validated against the live catalog before persist.

import type { Catalog } from "../../../src/lib/catalog";
import { sdmAtomBlocks } from "../../../src/lib/sdm";
import {
  type StoryError,
  type StoryFormat,
  compileStory,
  dslFormat,
  mdxDataFormat,
} from "../../../src/lib/storyCompile";
import type { StoryRef, StorySourceFormat, StoryStatus, StoryWrite } from "./storiesStore";

const FORMATS: Record<StorySourceFormat, StoryFormat> = {
  dsl: dslFormat,
  "mdx-data": mdxDataFormat,
};

/** The author-supplied fields (the compiled SDM + refs + catalog_version are derived, not trusted). */
export interface StoryWriteInput {
  site: string;
  slug: string;
  title: string;
  dek: string;
  status: StoryStatus;
  source_format: StorySourceFormat;
  source_text: string;
}

const MAX_SOURCE = 100_000;
const MAX_TITLE = 200;
const MAX_DEK = 500;
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;

/** Validate + narrow an untrusted request body into a `StoryWriteInput`. Shape/limits only — the
 *  content-safety guarantee comes from `buildStoryWrite` compiling to the closed SDM vocabulary. */
export function parseStoryInput(
  value: unknown,
): { ok: true; input: StoryWriteInput } | { ok: false; error: string } {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { ok: false, error: "body must be an object" };
  }
  const v = value as Record<string, unknown>;
  const str = (k: string): string | undefined => (typeof v[k] === "string" ? (v[k] as string) : undefined);

  const site = str("site");
  const slug = str("slug");
  const title = str("title");
  const dek = str("dek") ?? "";
  const status = str("status") ?? "draft";
  const source_format = str("source_format") ?? "dsl";
  const source_text = str("source_text");

  if (!site) return { ok: false, error: "site is required" };
  if (!slug || !SLUG_RE.test(slug)) return { ok: false, error: "slug must be a lowercase kebab-case id" };
  if (!title) return { ok: false, error: "title is required" };
  if (title.length > MAX_TITLE) return { ok: false, error: "title is too long" };
  if (dek.length > MAX_DEK) return { ok: false, error: "dek is too long" };
  if (status !== "draft" && status !== "published") return { ok: false, error: "invalid status" };
  if (source_format !== "dsl" && source_format !== "mdx-data") {
    return { ok: false, error: "invalid source_format" };
  }
  if (source_text === undefined) return { ok: false, error: "source_text is required" };
  if (source_text.length > MAX_SOURCE) return { ok: false, error: "source_text is too long" };

  return { ok: true, input: { site, slug, title, dek, status, source_format, source_text } };
}

/**
 * Compile + validate a submitted Story into a `StoryWrite`. Runs the #1094 pipeline
 * (parse → assertNoCode → sanitize → resolveHandles → lowerToSDM); a dangling/unknown handle or any
 * unsafe construct is an author-facing error, so a Story with a bad ref is rejected at save.
 */
export function buildStoryWrite(
  input: StoryWriteInput,
  catalog: Catalog,
): { ok: true; write: StoryWrite } | { ok: false; errors: StoryError[] } {
  const result = compileStory(input.source_text, FORMATS[input.source_format], catalog);
  if (!result.ok) return { ok: false, errors: result.errors };

  const refs: StoryRef[] = sdmAtomBlocks(result.doc).map((b, i) => ({
    ord: i,
    handle: b.handle,
    kind: b.kind,
    title: b.title,
  }));

  return {
    ok: true,
    write: {
      site: input.site,
      slug: input.slug,
      title: input.title,
      dek: input.dek,
      status: input.status,
      source_format: input.source_format,
      source_text: input.source_text,
      sdm_json: JSON.stringify(result.doc),
      catalog_version: catalog.version,
      refs,
    },
  };
}
