/**
 * The curated catalog handle-rename map (#1099) — the optional auto-heal for user Stories. When an
 * atom's stable key changes (a record `rel` is corrected, a slug is renamed), add
 * `"<oldHandle>": "<newHandle>"` here; the revalidation job rewrites affected Stories' refs + SDM so
 * the citation resolves live again instead of dangling. Both sides are full handles
 * (`<kind>:<site>:<localId>`). Keep this small + curated — an unknown dangling handle is *flagged*
 * for the author, never silently retargeted.
 *
 * Pure data (no fs / no bundle) so the Worker revalidation endpoint can import it.
 */
import type { RenameMap } from "./revalidate";

export const HANDLE_RENAMES: RenameMap = {
  // "record:lima:old-rel": "record:lima:new-rel",
};
