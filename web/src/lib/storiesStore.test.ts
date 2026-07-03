// Unit tests for the D1 Story store (#1095) against an in-memory SQLite (node:sqlite) with the
// committed schema — so owner-scoping, ref replacement, FK cascade, unique constraints, and the
// `batch()` transaction rollback are all exercised on real SQL, not a mock.

import { describe, expect, it } from "vitest";
import {
  type StoryOwner,
  type StoryWrite,
  createStory,
  deleteStory,
  getStory,
  listStories,
  updateStory,
} from "@fn/api/_lib/storiesStore";
import { fakeD1 } from "./_routeHarness";

const owner: StoryOwner = { kind: "user", id: "user-1" };
const other: StoryOwner = { kind: "user", id: "user-2" };
const NOW = "2026-07-03T00:00:00.000Z";

function write(over: Partial<StoryWrite> = {}): StoryWrite {
  return {
    site: "lima",
    slug: "my-story",
    title: "My Story",
    dek: "a dek",
    status: "draft",
    source_format: "dsl",
    source_text: "## hi",
    sdm_json: '{"version":"1.0.0","blocks":[]}',
    catalog_version: "v1",
    refs: [
      { ord: 0, handle: "record:lima:a", kind: "record", title: "A" },
      { ord: 1, handle: "entity:lima:b", kind: "entity", title: "B" },
    ],
    ...over,
  };
}

describe("stories store — CRUD", () => {
  it("creates a story + its refs and reads them back in order", async () => {
    const db = fakeD1();
    await createStory(db, owner, "s1", write(), NOW);
    const got = await getStory(db, owner, "s1");
    expect(got?.story.title).toBe("My Story");
    expect(got?.story.status).toBe("draft");
    expect(got?.refs.map((r) => r.handle)).toEqual(["record:lima:a", "entity:lima:b"]);
  });

  it("lists a user's own stories newest-first", async () => {
    const db = fakeD1();
    await createStory(db, owner, "s1", write({ slug: "one" }), "2026-07-01T00:00:00.000Z");
    await createStory(db, owner, "s2", write({ slug: "two" }), "2026-07-03T00:00:00.000Z");
    const rows = await listStories(db, owner);
    expect(rows.map((r) => r.id)).toEqual(["s2", "s1"]);
  });

  it("replaces refs wholesale on update", async () => {
    const db = fakeD1();
    await createStory(db, owner, "s1", write(), NOW);
    const ok = await updateStory(
      db,
      owner,
      "s1",
      write({ title: "Renamed", refs: [{ ord: 0, handle: "lead:lima:c", kind: "lead", title: "C" }] }),
      "2026-07-04T00:00:00.000Z",
    );
    expect(ok).toBe(true);
    const got = await getStory(db, owner, "s1");
    expect(got?.story.title).toBe("Renamed");
    expect(got?.refs.map((r) => r.handle)).toEqual(["lead:lima:c"]);
  });

  it("deletes a story and cascades its refs", async () => {
    const db = fakeD1();
    await createStory(db, owner, "s1", write(), NOW);
    expect(await deleteStory(db, owner, "s1")).toBe(true);
    expect(await getStory(db, owner, "s1")).toBeNull();
    const orphans = db.raw.prepare("SELECT COUNT(*) AS n FROM story_refs").get() as { n: number };
    expect(orphans.n).toBe(0);
  });
});

describe("stories store — owner scoping", () => {
  it("never reads, updates, or deletes another owner's story", async () => {
    const db = fakeD1();
    await createStory(db, owner, "s1", write(), NOW);
    expect(await getStory(db, other, "s1")).toBeNull();
    expect(await updateStory(db, other, "s1", write({ title: "hijack" }), NOW)).toBe(false);
    expect(await deleteStory(db, other, "s1")).toBe(false);
    // The real owner's story is untouched.
    expect((await getStory(db, owner, "s1"))?.story.title).toBe("My Story");
  });
});

describe("stories store — transactional integrity", () => {
  it("rolls the whole create back when a ref insert violates the PK (atomic batch)", async () => {
    const db = fakeD1();
    await expect(
      createStory(
        db,
        owner,
        "s1",
        write({
          refs: [
            { ord: 0, handle: "record:lima:a", kind: "record", title: "A" },
            { ord: 0, handle: "entity:lima:b", kind: "entity", title: "B" }, // duplicate ord → PK clash
          ],
        }),
        NOW,
      ),
    ).rejects.toThrow();
    // The story row must not survive the failed batch.
    expect(await getStory(db, owner, "s1")).toBeNull();
  });

  it("rejects a second story with a duplicate (owner, site, slug)", async () => {
    const db = fakeD1();
    await createStory(db, owner, "s1", write({ slug: "dup" }), NOW);
    await expect(createStory(db, owner, "s2", write({ slug: "dup" }), NOW)).rejects.toThrow();
    // But a different owner may reuse the slug.
    await expect(createStory(db, other, "s3", write({ slug: "dup" }), NOW)).resolves.toBeUndefined();
  });
});
