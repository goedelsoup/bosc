/**
 * Stable document handles (#1887, epic #1884 phase 3) — the **routing** key for a source document.
 *
 * The corpus's on-disk tree is not the URL tree. A document is addressed by an opaque 8-character
 * handle derived from its `data/documents` rel; the as-received path stays untouched on disk and
 * stays on the page as the custody record. This module is the whole ID axis: no other file may
 * mint one.
 *
 * Why derived rather than assigned, and why a non-crypto hash:
 *
 *  - **The redirect budget.** Cloudflare Pages caps `_redirects` at 2,000 static + 100 dynamic
 *    rules; Lima alone has 3,247 documents whose deep legacy paths must keep resolving. Because
 *    the handle is a pure function of the rel, the legacy-path Function computes it at the edge
 *    and 301s with no lookup table — one file instead of 3,247 impossible redirect lines.
 *  - **Three runtimes, one answer.** Node (the Astro build), the Workers runtime (the redirect
 *    Function and `/api/ask` citation rendering), and Python (`watermark.site.document_id`, for
 *    the MCP `search_passages` citation) must agree byte-for-byte or a citation silently 404s.
 *    `crypto.subtle.digest` is async and would poison every sync call site, so this is FNV-1a —
 *    trivially portable, and collision resistance is not a security property here. Integrity is
 *    already carried by the Git-LFS oid / R2 etag; this is a routing key. `documentId.test.ts`
 *    asserts zero collisions across the committed corpus, and the golden vectors in
 *    `__fixtures__/document-id-vectors.json` are asserted from both Node and pytest.
 *  - **Stable across the re-pull that actually happens.** A source re-served at the *same* rel
 *    with new bytes (the Ohio EPA DAM re-serving `permits/doc/` in place) keeps its handle, which
 *    is correct — it is the same record. A byte change at a stable rel is a *version* event, and
 *    `data/site/document-versions.yaml` (#1590) already carries that vocabulary.
 *
 * The handle deliberately does not encode the filename: that is what produced the 16-segment
 * routes this replaces.
 */

// FNV-1a, 64-bit. BigInt keeps the arithmetic exact and the port to Python a transcription.
const FNV_OFFSET_BASIS = 0xcbf29ce484222325n;
const FNV_PRIME = 0x100000001b3n;
const MASK_64 = 0xffffffffffffffffn;

/**
 * Crockford base32, lower-cased for URLs — no `i`/`l`/`o`/`u`, so a handle read aloud, written
 * down, or re-typed from a filing can't collide through `1`/`l` or `0`/`O`. These handles end up
 * in citations that outlive the build, so the alphabet matters.
 */
const ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz";

/** Handle width in characters: 8 × 5 bits = the 40 bits taken off the hash. */
export const DOCUMENT_ID_LENGTH = 8;

/** Bits discarded from the 64-bit hash to leave a whole number of base32 characters. */
const DISCARDED_BITS = 64n - BigInt(DOCUMENT_ID_LENGTH) * 5n;

const DOCUMENT_ID_RE = new RegExp(`^[${ALPHABET}]{${DOCUMENT_ID_LENGTH}}$`);

/**
 * Curated handle pins — the escape hatch for the one case the derivation can't cover: a document
 * that **moves** to a different rel and must keep the handle it was already cited under.
 *
 * Same shape and same discipline as `HANDLE_RENAMES` (#1099): keep it small, keep it reviewed,
 * and add an entry only with the old and new rels recorded in the commit. Left empty, every
 * handle is reproducible from the corpus alone. Note that old *URLs* keep working without a pin —
 * the legacy path still hashes to the handle it was minted under; a pin is needed only so the
 * document's *current* rel resolves to that same handle.
 */
export const DOCUMENT_ID_PINS: Readonly<Record<string, string>> = {
  // "oepa/van-wert/old-name.pdf": "7k3m9qpb",
};

/** FNV-1a over the UTF-8 bytes of `input`. `TextEncoder` is present in Node, Workers, and browsers. */
function fnv1a64(input: string): bigint {
  let hash = FNV_OFFSET_BASIS;
  for (const byte of new TextEncoder().encode(input)) {
    hash = ((hash ^ BigInt(byte)) * FNV_PRIME) & MASK_64;
  }
  return hash;
}

/** Big-endian Crockford base32 of the low `DOCUMENT_ID_LENGTH * 5` bits of `value`. */
function encodeBase32(value: bigint): string {
  let out = "";
  let remaining = value;
  for (let i = 0; i < DOCUMENT_ID_LENGTH; i++) {
    out = ALPHABET[Number(remaining & 31n)] + out;
    remaining >>= 5n;
  }
  return out;
}

/**
 * The stable handle for a `data/documents` rel — the document's address everywhere in the site.
 *
 * Takes the rel **verbatim**, exactly as it appears in the documents feed: no case folding, no
 * separator normalization, no URL decoding. The rel is the as-received chain-of-custody path and
 * any normalization here would be a second, silently-diverging definition of it.
 */
export function documentId(rel: string): string {
  const pinned = DOCUMENT_ID_PINS[rel];
  if (pinned !== undefined) return pinned;
  return encodeBase32(fnv1a64(rel) >> DISCARDED_BITS);
}

/** Whether `value` is well-formed as a handle — a cheap route-param / redirect-target guard. */
export function isDocumentId(value: string): boolean {
  return DOCUMENT_ID_RE.test(value);
}

/**
 * The site-relative permalink for a handle (`/doc/<id>/`). Callers wrap it in `withSite` /
 * `withBasePath`; it carries no base of its own, matching `docPagePath`'s contract.
 *
 * Flat and collection-free on purpose: the address survives any re-shelving of the corpus, and
 * the collection/container/folder path renders *on* the page as provenance instead.
 */
export function docPermalink(id: string): string {
  return `/doc/${id}/`;
}

/** `docPermalink(documentId(rel))` — the common one-step call. */
export function docPermalinkForRel(rel: string): string {
  return docPermalink(documentId(rel));
}
