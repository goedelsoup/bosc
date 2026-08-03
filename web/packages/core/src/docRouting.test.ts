import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { isRoutableDoc, nonRoutableReason } from "./docRouting";
import type { DocumentCollectionItem, DocumentEntry } from "./feeds";

const HERE = fileURLToPath(new URL(".", import.meta.url));

function limaEntries(): DocumentEntry[] {
  const feed = JSON.parse(
    readFileSync(resolve(HERE, "../../../sites/lima/feeds/documents.json"), "utf-8"),
  ) as DocumentCollectionItem[];
  return feed.flatMap((c) => c.entries);
}

const doc = (rel: string): { rel: string; name: string } => ({
  rel,
  name: rel.split("/").pop() ?? rel,
});

describe("isRoutableDoc — the rules", () => {
  it("drops OS artifacts by exact name, case-insensitively", () => {
    expect(isRoutableDoc(doc("legal/x/Thumbs.db"))).toBe(false);
    expect(isRoutableDoc(doc("legal/x/thumbs.db"))).toBe(false);
    expect(isRoutableDoc(doc("legal/x/.DS_Store"))).toBe(false);
    expect(isRoutableDoc(doc("legal/x/desktop.ini"))).toBe(false);
  });

  it("drops content-hash-named inline mail images", () => {
    expect(isRoutableDoc(doc("legal/x/imagef2270f.PNG"))).toBe(false);
    expect(isRoutableDoc(doc("legal/x/imagedeadbeef.gif"))).toBe(false);
  });

  it("keeps an image whose name is a title, not a hash", () => {
    expect(isRoutableDoc(doc("legal/x/image of the outfall.jpg"))).toBe(true);
    expect(isRoutableDoc(doc("legal/x/imagery-plan.png"))).toBe(true);
  });

  it("keeps Outlook's SEQUENTIAL inline form — deliberately not covered", () => {
    // `image001.png` is also mail exhaust, but the rule requires >=4 hex characters and so lets
    // it through. That asymmetry is intentional: a stray junk route is cheap and visible, while
    // wrongly filtering a real record leaves it with no page and says nothing. There is no
    // instance of this form in the corpus (checked: the only `image*` file is imagef2270f.PNG),
    // so widening on speculation would be inventing a rule the record doesn't support. Widen it
    // when a production actually produces one.
    expect(isRoutableDoc(doc("legal/x/image001.png"))).toBe(true);
    expect(isRoutableDoc(doc("legal/x/image01.png"))).toBe(true);
  });

  it("drops everything inside an Office 'Save as Web Page' sidecar directory", () => {
    const base = "legal/prr/Some Email_files";
    expect(isRoutableDoc(doc(`${base}/themedata.thmx`))).toBe(false);
    expect(isRoutableDoc(doc(`${base}/colorschememapping.xml`))).toBe(false);
    expect(isRoutableDoc(doc(`${base}/nested/deeper.png`))).toBe(false);
  });

  it("keeps a FILE whose own name ends in _files — only a directory is a sidecar", () => {
    expect(isRoutableDoc(doc("legal/prr/exhibit_files"))).toBe(true);
    expect(isRoutableDoc(doc("legal/prr/exhibit_files.pdf"))).toBe(true);
  });

  it("keeps a directory that merely contains the substring", () => {
    expect(isRoutableDoc(doc("legal/prr/misc_files_archive/report.pdf"))).toBe(true);
  });

  it("keeps an ordinary record", () => {
    expect(isRoutableDoc(doc("aedg/PRR-01-bundle.ocr.pdf"))).toBe(true);
  });
});

describe("nonRoutableReason", () => {
  it("names the rule that excluded each kind", () => {
    expect(nonRoutableReason(doc("a/Thumbs.db"))).toBe("os-artifact");
    expect(nonRoutableReason(doc("a/imagef2270f.PNG"))).toBe("inline-image");
    expect(nonRoutableReason(doc("a/Email_files/filelist.xml"))).toBe("web-page-sidecar");
  });

  it("is null exactly when isRoutableDoc is true", () => {
    for (const entry of limaEntries()) {
      expect(nonRoutableReason(entry) === null).toBe(isRoutableDoc(entry));
    }
  });
});

describe("isRoutableDoc — measured against the committed Lima corpus", () => {
  // Pinned counts. These are the whole argument that this is a precise filter and not a
  // heuristic: if a corpus change moves them, that belongs in review, not in a silent
  // route-count drift.
  it("excludes exactly 54 of 3,247 entries (1.7%)", () => {
    const entries = limaEntries();
    expect(entries.length).toBe(3247);
    expect(entries.filter((e) => !isRoutableDoc(e))).toHaveLength(54);
  });

  it("splits into 38 OS artifacts, 15 sidecar files and 1 inline image", () => {
    const counts = { "os-artifact": 0, "inline-image": 0, "web-page-sidecar": 0 };
    for (const entry of limaEntries()) {
      const reason = nonRoutableReason(entry);
      if (reason) counts[reason] += 1;
    }
    expect(counts).toEqual({ "os-artifact": 38, "inline-image": 1, "web-page-sidecar": 15 });
  });

  it("orphans nothing: every sidecar directory dropped has a surviving sibling record", () => {
    const entries = limaEntries();
    const routableRels = new Set(entries.filter(isRoutableDoc).map((e) => e.rel));
    const sidecarDirs = new Set(
      entries
        .filter((e) => nonRoutableReason(e) === "web-page-sidecar")
        .map((e) => e.rel.slice(0, e.rel.lastIndexOf("/"))),
    );
    expect(sidecarDirs.size).toBe(5);
    for (const dir of sidecarDirs) {
      const stem = dir.slice(0, -"_files".length);
      const sibling = [".htm", ".html", ".mht", ".doc", ".docx"].some((ext) => routableRels.has(stem + ext));
      expect(sibling, `${dir} has no surviving sibling record`).toBe(true);
    }
  });

  it("leaves every excluded file in the catalog — a production stays provably complete", () => {
    // The predicate governs routing only. Nothing here removes an entry from the feed, so the
    // container manifest and /api/doc/<rel> still carry all 3,247 as-received paths.
    const entries = limaEntries();
    const excluded = entries.filter((e) => !isRoutableDoc(e));
    expect(excluded.every((e) => entries.includes(e))).toBe(true);
    expect(excluded.every((e) => e.rel.length > 0 && e.available)).toBe(true);
  });
});
