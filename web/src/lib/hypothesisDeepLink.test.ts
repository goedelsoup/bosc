// The hypothesis deep link — `/research/hypotheses?h=<id>` (#1912, epic #1911 phase 0).
//
// `?lens=` was the param before the de-lensing rename, and `nav.ts` emitted it into the Research
// dropdown of every page render for months. It is a public, shared, indexable URL: it must keep
// opening the pane it always opened, forever. `?h=` is only the *canonical* form we emit now.
//
// The page's switch is no-JS (radio + `:checked`), so the param is progressive enhancement: an
// inline script ticks the matching radio before the panes parse. That script ships inline in the
// `.astro` template, which the plain-Node test project can't render — so this reads the shipped
// source, lifts the script out, and runs it against a stub `location` + `document`. It asserts the
// behavior of the real code rather than the presence of a substring in it; a rewrite that broke
// the fallback would still fail here.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { networkTabs } from "@watermark/core/nav";
import type { HypothesisItem } from "@watermark/core/feeds";

const PAGE = join(process.cwd(), "src/pages/research/hypotheses.astro");

/** The body of the page's single `<script is:inline>` block. */
function deepLinkScript(): string {
  const source = readFileSync(PAGE, "utf-8");
  const match = source.match(/<script is:inline>([\s\S]*?)<\/script>/);
  expect(match, "the deep-link script is still inline in the page").toBeTruthy();
  return (match as RegExpMatchArray)[1];
}

/** The radio `id`s and group `name` the page renders, read off the template rather than
 *  hardcoded — so a rename of either side is caught by the ids/name disagreeing, not missed. */
function radioGroup(): { name: string; ids: string[] } {
  const source = readFileSync(PAGE, "utf-8");
  const name = source.match(/name="([a-z-]+)"/)?.[1] ?? "";
  const idTemplate = source.match(/id=\{`([a-z-]+)-\$\{/)?.[1] ?? "";
  expect(name).not.toBe("");
  expect(idTemplate).not.toBe("");
  return { name, ids: ["water", "defense", "surveillance"].map((k) => `${idTemplate}-${k}`) };
}

/** Run the page's script over `?<query>` and report which radio it ticked (null = none). */
function checkedBy(query: string): string | null {
  const { name, ids } = radioGroup();
  // Minimal stand-ins for the two globals the script touches. `HTMLInputElement` has to be a
  // real class so the script's `instanceof` narrowing behaves as it does in a browser.
  class HTMLInputElement {
    checked = false;
    constructor(
      readonly id: string,
      readonly name: string,
    ) {}
  }
  const radios = ids.map((id) => new HTMLInputElement(id, name));
  const document = { getElementById: (id: string) => radios.find((r) => r.id === id) ?? null };
  const location = { search: query };

  new Function("location", "document", "HTMLInputElement", deepLinkScript())(
    location,
    document,
    HTMLInputElement,
  );
  const ticked = radios.filter((r) => r.checked);
  expect(ticked.length, "at most one radio is ticked").toBeLessThanOrEqual(1);
  return ticked[0]?.id ?? null;
}

describe("hypothesis deep link — ?h= canonical, ?lens= honored forever (#1912)", () => {
  it("opens the named pane from the canonical ?h=", () => {
    const { ids } = radioGroup();
    expect(checkedBy("?h=defense")).toBe(ids[1]);
    expect(checkedBy("?h=surveillance")).toBe(ids[2]);
  });

  it("still opens the named pane from the pre-#1912 ?lens=", () => {
    // The whole reason this file exists: links already shared keep working.
    const { ids } = radioGroup();
    expect(checkedBy("?lens=defense")).toBe(ids[1]);
    expect(checkedBy("?lens=surveillance")).toBe(ids[2]);
  });

  it("falls back to ?lens= when ?h= is present but empty", () => {
    // `??` would stop at the empty string and strand the link; the script reads with `||`.
    expect(checkedBy("?h=&lens=defense")).toBe(radioGroup().ids[1]);
  });

  it("leaves the default checked for an absent or unknown value", () => {
    // Nothing is ticked by the script — the template's `checked` on the first radio stands.
    expect(checkedBy("")).toBeNull();
    expect(checkedBy("?h=ownership")).toBeNull();
    expect(checkedBy("?lens=ownership")).toBeNull();
  });
});

describe("the Research dropdown emits the canonical param (#1912)", () => {
  it("links each hypothesis with ?h=, and nothing emits ?lens= any more", () => {
    const hypotheses = [
      { id: "water", number: "H1", name: "Water & Coercion" },
      { id: "defense", number: "H2", name: "Defense & Federal Enclave" },
    ] as HypothesisItem[];
    const research = networkTabs(hypotheses).find((t) => t.section === "research");
    const hrefs =
      research?.kind === "dropdown" ? research.children.map((c) => ("href" in c ? c.href : "")) : [];
    expect(hrefs).toContain("/research/hypotheses?h=water");
    expect(hrefs).toContain("/research/hypotheses?h=defense");
    expect(hrefs.join(" ")).not.toContain("?lens=");
  });
});
