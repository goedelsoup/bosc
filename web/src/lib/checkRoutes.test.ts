// The deploy budget and the orphan guard, watched failing (#1894, epic #1884 phase 10).
//
// `check-routes.mjs` says it out loud in its own header: "a budget guard nobody has watched fail is
// only a guess that it works." Guards 8 and 9 are worse than that if they're wrong — they're the
// only thing standing between the build and a Cloudflare file cap that isn't discovered until a
// deploy, and the only standing proof of this issue's acceptance criterion ("no orphaned non-auth
// route"). A guard that passes on a real build tells you nothing about whether it CAN fail.
//
// So each branch is exercised against a synthetic `dist/` through `CHECK_ROUTES_DIST`, which the
// script exposes for exactly this. A synthetic tree trips the other guards too (no
// `search-coverage.json`, no trail markup) — expected, and why every assertion is on the specific
// message rather than on the exit code.
//
// The size cases use SPARSE files: `ftruncate` to 24 MiB writes no blocks, so a 432 MB tree costs
// nothing and the run stays in milliseconds.
import { execFileSync } from "node:child_process";
import { closeSync, ftruncateSync, mkdirSync, mkdtempSync, openSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";

const roots: string[] = [];
afterAll(() => {
  for (const r of roots) rmSync(r, { recursive: true, force: true });
});

/** Write a synthetic dist and return everything `check-routes.mjs` printed. */
function runGuard(pages: Record<string, string>, sparse: { name: string; bytes: number }[] = []): string {
  const root = mkdtempSync(join(tmpdir(), "check-routes-"));
  roots.push(root);
  for (const [route, html] of Object.entries(pages)) {
    const file = join(root, route === "" ? "index.html" : `${route}/index.html`);
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(file, html);
  }
  for (const { name, bytes } of sparse) {
    const fd = openSync(join(root, name), "w");
    ftruncateSync(fd, bytes);
    closeSync(fd);
  }
  try {
    return execFileSync("node", ["scripts/check-routes.mjs"], {
      encoding: "utf-8",
      env: { ...process.env, CHECK_ROUTES_DIST: root },
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (e) {
    const err = e as { stdout?: string; stderr?: string };
    return `${err.stdout ?? ""}${err.stderr ?? ""}`;
  }
}

/**
 * The control: every route either linked from another page (`/` ↔ `/a`) or matching a declared
 * exemption and matching it for the right reason — `/account/login` and `/pre-launch` are present
 * and deliberately linked from nothing, which is the state UNLINKED_BY_DESIGN exists to describe.
 */
const REACHABLE = {
  "": '<a href="/a/">A</a>',
  a: '<a href="/">home</a>',
  "account/login": "<p>arrived at by redirect</p>",
  "pre-launch": "<p>no chrome</p>",
};

describe("check-routes guard 9 — every built route is reachable", () => {
  it("fails on a route nothing links, and names only that one", () => {
    const out = runGuard({ ...REACHABLE, orphan: '<a href="/">home</a>' });
    expect(out).toContain("linked from no other page");
    // Scoped to guard 9's own paragraph: the synthetic tree also fails the trail guard, whose list
    // names every route, so a bare `toContain` would pass on an over-reporting guard.
    const block = out.slice(out.indexOf("linked from no other page")).split("✗")[0];
    expect(block).toContain("/orphan");
    expect(block).not.toContain("/a\n");
    expect(block).not.toContain("/account/login");
  });

  it("does not count a page's link to ITSELF as an inbound link", () => {
    // Every page carries its own canonical link, its own trail leaf and the switcher's current-site
    // row. Counting those would make every route its own referrer and the guard vacuous — which is
    // the failure mode that reports green forever.
    const out = runGuard({ ...REACHABLE, orphan: '<a href="/orphan/">me</a>' });
    expect(out).toContain("/orphan");
  });

  it("passes when everything is linked or declared", () => {
    const out = runGuard(REACHABLE);
    expect(out).toContain("every route reachable");
    expect(out).not.toContain("linked from no other page");
  });

  it("fails when a declared exemption matches no orphan — a decision outliving its route", () => {
    // `/account/login` is linked here, and there is no `/pre-launch` at all, so both UNLINKED_BY_DESIGN
    // entries are stale. Left standing they would silently excuse the next route that matched them.
    const out = runGuard({
      "": '<a href="/a/">A</a><a href="/account/login/">in</a>',
      a: "<p/>",
      "account/login": "<p/>",
    });
    expect(out).toContain("match no orphan in this build");
  });

  it("resolves a percent-encoded href against the literal directory it was emitted at", () => {
    // The as-received public-record filenames carry `#`, `&`, `%`. Astro emits the DIRECTORY
    // percent-encoded and the href either way; a guard that compared only one spelling would call a
    // linked document an orphan on the sites that have the most of them.
    const out = runGuard({
      ...REACHABLE,
      "": '<a href="/a/">A</a><a href="/doc/A%20%26%20B/">doc</a>',
      "doc/A %26 B": '<a href="/">home</a>',
    });
    expect(out).toContain("every route reachable");
  });

  it("decodes the HTML entities an href is emitted with before resolving it", () => {
    // `Contracts & Agreements` ships as `&#38;`, whose `#` reads as a fragment delimiter and would
    // truncate the target to `.../Contracts ` — the link uncounted, the container reported an orphan.
    // Lima's document tree is full of these, so an undecoded guard would fail on the site with the
    // most records, which is the one it exists to protect.
    const out = runGuard({
      ...REACHABLE,
      "": '<a href="/a/">A</a><a href="/docs/Contracts &#38; Agreements/">c</a>',
      "docs/Contracts & Agreements": '<a href="/">home</a>',
    });
    expect(out).toContain("every route reachable");
  });

  it("never lets a decoded alias shadow a route that literally has that name", () => {
    // Both spellings on disk. `A & B` is linked and `A %26 B` is not, so the orphan is the encoded
    // one — which only holds if the decoded alias didn't overwrite the literal route's own entry.
    const out = runGuard({
      ...REACHABLE,
      "": '<a href="/a/">A</a><a href="/doc/A & B/">doc</a>',
      "doc/A & B": '<a href="/">home</a>',
      "doc/A %26 B": '<a href="/">home</a>',
    });
    const block = out.slice(out.indexOf("linked from no other page")).split("✗")[0];
    expect(block).toContain("/doc/A %26 B");
    expect(block).not.toContain("/doc/A & B\n");
  });
});

describe("check-routes guard 8 — the deploy budget", () => {
  it("fails over the file-count budget before Cloudflare does", () => {
    const pages: Record<string, string> = { ...REACHABLE };
    for (let i = 0; i < 6_001; i++) pages[`p${i}`] = '<a href="/">home</a>';
    const out = runGuard(pages);
    expect(out).toContain("over the 6,000-file budget");
    expect(out).toContain("20,000");
  });

  it("fails over the total-artifact budget", () => {
    // 18 × 24 MiB = 432 MB, and not one file over the per-file limit — so this can only be the
    // total tripping, not the per-file check standing in for it.
    const sparse = Array.from({ length: 18 }, (_, i) => ({ name: `big${i}.bin`, bytes: 24 * 1024 * 1024 }));
    const out = runGuard(REACHABLE, sparse);
    expect(out).toContain("over the 420 MB artifact budget");
    expect(out).not.toContain("per-file limit");
  });

  it("fails on a single file over the Pages 25 MiB per-file limit — a rejected deploy, not a slow one", () => {
    const out = runGuard(REACHABLE, [{ name: "huge.bin", bytes: 26 * 1024 * 1024 }]);
    expect(out).toContain("per-file limit");
    expect(out).toContain("REJECTED");
  });

  it("passes a build inside both budgets, and prints what it measured", () => {
    const out = runGuard(REACHABLE);
    expect(out).toContain("check-routes: deploy 4 files");
    expect(out).not.toContain("budget (Cloudflare");
    expect(out).not.toContain("artifact budget");
  });
});
