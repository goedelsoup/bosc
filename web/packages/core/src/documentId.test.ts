import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  DOCUMENT_ID_LENGTH,
  DOCUMENT_ID_PINS,
  docPermalink,
  docPermalinkForRel,
  documentId,
  isDocumentId,
} from "./documentId";
import type { DocumentCollectionItem } from "./feeds";

const HERE = fileURLToPath(new URL(".", import.meta.url));

interface VectorFile {
  algorithm: string;
  vectors: Array<{ rel: string; id: string; note: string }>;
}
const GOLDEN = JSON.parse(
  readFileSync(resolve(HERE, "__fixtures__/document-id-vectors.json"), "utf-8"),
) as VectorFile;

/** Every rel in the committed Lima bundle — the corpus this scheme actually has to address. */
function limaRels(): string[] {
  const feed = JSON.parse(
    readFileSync(resolve(HERE, "../../../sites/lima/feeds/documents.json"), "utf-8"),
  ) as DocumentCollectionItem[];
  return feed.flatMap((c) => c.entries.map((e) => e.rel));
}

describe("documentId — golden vectors", () => {
  // THE parity guard. `tests/test_site_document_id.py` asserts this same file against the Python
  // transcription. A drift between the two runtimes doesn't raise anywhere — it silently 404s
  // every document citation — so if this fails, fix the implementation, never the fixture.
  it.each(GOLDEN.vectors)("$note", ({ rel, id }) => {
    expect(documentId(rel)).toBe(id);
  });

  it("covers the encodings that actually break cross-runtime hashes", () => {
    const notes = GOLDEN.vectors.map((v) => v.note).join(" ");
    expect(notes).toMatch(/2-byte UTF-8/);
    expect(notes).toMatch(/3-byte UTF-8/);
    expect(notes).toMatch(/4-byte UTF-8/); // JS iterates surrogate pairs; TextEncoder must flatten
  });
});

describe("documentId — shape", () => {
  it("is always DOCUMENT_ID_LENGTH characters of lower-case Crockford base32", () => {
    for (const rel of limaRels()) {
      expect(documentId(rel)).toMatch(/^[0-9a-hjkmnp-tv-z]{8}$/);
    }
  });

  it("excludes the ambiguous glyphs i, l, o and u", () => {
    const alphabet = new Set(limaRels().flatMap((rel) => [...documentId(rel)]));
    for (const forbidden of ["i", "l", "o", "u"]) {
      expect(alphabet.has(forbidden)).toBe(false);
    }
  });

  it("is deterministic", () => {
    expect(documentId("aedg/PRR-01-bundle.ocr.pdf")).toBe(documentId("aedg/PRR-01-bundle.ocr.pdf"));
  });

  it("takes the rel verbatim — case is significant, since the corpus never renames", () => {
    expect(documentId("A/B.pdf")).not.toBe(documentId("a/b.pdf"));
  });

  it("does not normalize away the characters that made the old routes fragile", () => {
    // Each of these is a real as-received shape; none may collapse onto another.
    const rels = ["a/b c.pdf", "a/b%20c.pdf", "a/b&c.pdf", "a/b#c.pdf", "a/bc.pdf"];
    expect(new Set(rels.map(documentId)).size).toBe(rels.length);
  });
});

describe("documentId — the corpus it has to address", () => {
  it("mints a distinct handle for all 3,251 committed Lima rels", () => {
    const rels = limaRels();
    expect(rels.length).toBe(3251); // a corpus change should surface here, not as a silent collision
    const ids = new Set(rels.map(documentId));
    expect(ids.size).toBe(rels.length);
  });

  it("keeps ample headroom at 40 bits for the network's growth", () => {
    // 21 sites at Lima's scale is ~68k documents. Birthday collision probability at 2^40 is
    // ~n^2/2^41 — well under 1% there. If this corpus ever approaches 10^6, widen the handle
    // (and pin every existing id) rather than letting the first collision decide it.
    const ids = new Set(limaRels().map(documentId));
    expect(ids.size).toBeGreaterThan(3000);
    expect(DOCUMENT_ID_LENGTH * 5).toBe(40);
  });
});

describe("DOCUMENT_ID_PINS", () => {
  const pins = DOCUMENT_ID_PINS as Record<string, string>;
  afterEach(() => {
    for (const key of Object.keys(pins)) delete pins[key];
  });

  it("ships empty, so every handle is reproducible from the corpus alone", () => {
    expect(Object.keys(DOCUMENT_ID_PINS)).toHaveLength(0);
  });

  it("wins over the derivation, so a moved document keeps its cited handle", () => {
    const rel = "oepa/van-wert/moved.pdf";
    const derived = documentId(rel);
    pins[rel] = "zzzzzzzz";
    expect(documentId(rel)).toBe("zzzzzzzz");
    expect(documentId(rel)).not.toBe(derived);
  });

  it("does not leak onto a neighbouring rel", () => {
    pins["oepa/a.pdf"] = "zzzzzzzz";
    expect(documentId("oepa/b.pdf")).not.toBe("zzzzzzzz");
  });
});

describe("isDocumentId", () => {
  it("accepts a minted handle", () => {
    expect(isDocumentId(documentId("aedg/PRR-01-bundle.ocr.pdf"))).toBe(true);
  });

  it("rejects the wrong length", () => {
    expect(isDocumentId("abc")).toBe(false);
    expect(isDocumentId("abcdefghi")).toBe(false);
  });

  it("rejects the excluded glyphs and upper case", () => {
    for (const bad of ["iiiiiiii", "llllllll", "oooooooo", "uuuuuuuu", "ABCDEFGH"]) {
      expect(isDocumentId(bad)).toBe(false);
    }
  });

  it("rejects a path masquerading as a handle", () => {
    expect(isDocumentId("../../etc")).toBe(false);
    expect(isDocumentId("a/b.pdf")).toBe(false);
  });
});

describe("docPermalink", () => {
  it("is flat, collection-free, and carries no site base", () => {
    expect(docPermalink("7k3m9qpb")).toBe("/doc/7k3m9qpb/");
  });

  it("keeps every permalink at two segments, whatever the rel's depth", () => {
    const deepest = GOLDEN.vectors.find((v) => v.note.includes("deepest"));
    if (!deepest) throw new Error("the deep-rel vector is the point of this assertion");
    const path = docPermalinkForRel(deepest.rel);
    expect(path.split("/").filter(Boolean)).toHaveLength(2);
    // For scale: the rel it replaces is 12 segments, and rendered at 16 in the old route.
    expect(deepest.rel.split("/")).toHaveLength(12);
  });
});
