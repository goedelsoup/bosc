/**
 * Which catalogued source files get a **route** (#1887, epic #1884 phase 3).
 *
 * A small minority of the corpus is machine exhaust that a records custodian swept up with the
 * responsive records: Windows thumbnail caches, and the sidecar directories Word/Outlook writes
 * when a document or email is saved as a web page. Today each of those is a fully-rendered,
 * first-class page — there are 38 `Thumbs.db` routes in the Lima build.
 *
 * They are **not** removed from the corpus, the feed, or the object store. `data/documents/**` is
 * litigation evidence and a public-records production has to remain provably complete: every one
 * of these files stays listed in its container's manifest with its as-received path, and stays
 * fetchable via `/api/doc/<rel>`. This predicate governs one thing — whether the static build
 * mints a page for it.
 *
 * Deliberately three exact rules rather than a heuristic, so the set is auditable. Measured
 * against the committed Lima feed: 38 + 15 + 1 = 54 of 3,247 (1.7%). `docRouting.test.ts` pins
 * those counts, so a corpus change that alters the filter's reach shows up as a failing test
 * rather than as silently vanished routes.
 *
 * Note that the source catalog already drops `.DS_Store`, `README.md`, and `*.md|yaml|yml|sh`
 * before they ever reach the feed (`watermark.site.documents._SKIP_NAMES` / `_SKIP_SUFFIXES`) —
 * the OS-artifact rule below re-states those names because this predicate is also applied to the
 * legacy-path redirect, which sees raw paths rather than feed entries.
 */

/** Exact filenames that are operating-system exhaust, never a record. Compared case-insensitively. */
const OS_ARTIFACT_NAMES: ReadonlySet<string> = new Set(["thumbs.db", ".ds_store", "desktop.ini"]);

/**
 * Files whose name is a content hash rather than a title — an image lifted out of an email body
 * by the export tool. The record is the message; this is one of its inline graphics.
 *
 * Matches exactly one file in the Lima corpus today (`imagef2270f.PNG`). Kept because it is a
 * pattern PRR productions reliably re-emit and the rule is cheap — but it is not load-bearing,
 * and nothing should be built on the assumption that it catches a meaningful volume.
 */
const INLINE_IMAGE_NAME = /^image[0-9a-f]{4,}\.(?:png|jpe?g|gif|bmp)$/i;

/** The `<name>_files/` sidecar suffix Office writes beside a "Save as Web Page" export. */
const WEB_PAGE_SIDECAR_SUFFIX = "_files";

/**
 * Whether any *ancestor directory* of `rel` is an Office "Save as Web Page" sidecar.
 *
 * The sidecar holds the rendering chrome for the record next to it — `colorschememapping.xml`,
 * `filelist.xml`, `themedata.thmx`, and the message's inline images. Every one of the five such
 * directories in the Lima corpus has a surviving sibling `.htm` record still in the catalog, so
 * dropping their contents as routes orphans nothing; `docRouting.test.ts` asserts that invariant
 * rather than trusting it.
 */
function inWebPageSidecar(rel: string): boolean {
  const segments = rel.split("/");
  // Last segment is the filename — only the directories above it can be a sidecar.
  return segments.slice(0, -1).some((segment) => segment.endsWith(WEB_PAGE_SIDECAR_SUFFIX));
}

/**
 * Whether a catalogued document gets its own page. `false` means catalogued and fetchable but not
 * routed — it still appears in its container's listing, marked as such.
 */
export function isRoutableDoc(entry: { rel: string; name: string }): boolean {
  if (OS_ARTIFACT_NAMES.has(entry.name.toLowerCase())) return false;
  if (INLINE_IMAGE_NAME.test(entry.name)) return false;
  if (inWebPageSidecar(entry.rel)) return false;
  return true;
}

/** Why a document isn't routed, for the "listed but not a page" chip on its container listing. */
export type NonRoutableReason = "os-artifact" | "inline-image" | "web-page-sidecar";

/** The rule that excluded `entry`, or `null` when it is routable. Mirrors `isRoutableDoc` exactly. */
export function nonRoutableReason(entry: { rel: string; name: string }): NonRoutableReason | null {
  if (OS_ARTIFACT_NAMES.has(entry.name.toLowerCase())) return "os-artifact";
  if (INLINE_IMAGE_NAME.test(entry.name)) return "inline-image";
  if (inWebPageSidecar(entry.rel)) return "web-page-sidecar";
  return null;
}
