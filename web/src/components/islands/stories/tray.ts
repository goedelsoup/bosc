/**
 * The Story "in-progress" tray (#1096) — the non-modal handoff between the grab affordance (a reader
 * grabbing atoms while reading site content) and the editor. Grabbed atoms are held in
 * `sessionStorage` as thin snapshots (`handle` + `kind` + `title`), so opening the editor seeds the
 * canvas with exactly what was grabbed. Snapshots only — the live payload is resolved at render time
 * (chain of custody), never copied here.
 */
import type { CatalogKind } from "~/lib/catalog";

export interface TrayItem {
  handle: string;
  kind: CatalogKind;
  title: string;
}

const TRAY_KEY = "watermark_story_tray";

export function readTray(): TrayItem[] {
  try {
    const raw = sessionStorage.getItem(TRAY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as TrayItem[]) : [];
  } catch {
    return [];
  }
}

function writeTray(items: TrayItem[]): void {
  sessionStorage.setItem(TRAY_KEY, JSON.stringify(items));
}

/** Toggle an atom in the tray by handle; returns the new tray. */
export function toggleTray(item: TrayItem): TrayItem[] {
  const items = readTray();
  const idx = items.findIndex((i) => i.handle === item.handle);
  const next = idx >= 0 ? items.filter((i) => i.handle !== item.handle) : [...items, item];
  writeTray(next);
  return next;
}

export function inTray(handle: string): boolean {
  return readTray().some((i) => i.handle === handle);
}

export function clearTray(): void {
  sessionStorage.removeItem(TRAY_KEY);
}
