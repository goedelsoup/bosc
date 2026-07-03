// Unit tests for the Lakebase (Postgres) Story store (#1095/#1098) against an in-memory Postgres
// (pglite) with the committed schema — so owner-scoping, ref replacement, FK cascade, unique
// constraints, the `begin()` transaction rollback, and the sharing/moderation rails are all
// exercised on the real engine (Postgres) production uses.

import { describe, expect, it } from "vitest";
import {
  type StoryOwner,
  type StoryWrite,
  createStory,
  deleteStory,
  getPublicStory,
  getStory,
  insertReport,
  listReports,
  listStories,
  resolveReport,
  setModeration,
  storyIdForShareId,
  updateStory,
} from "@fn/api/_lib/storiesStore";
import { revalidateAll } from "@fn/api/_lib/revalidateStories";
import { fakePg } from "./_routeHarness";

const owner: StoryOwner = { kind: "user", id: "user-1" };
const other: StoryOwner = { kind: "user", id: "user-2" };
const NOW = "2026-07-03T00:00:00.000Z";
const SHARE = "share-abc";

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
    const db = await fakePg();
    await createStory(db, owner, "s1", write(), NOW, SHARE);
    const got = await getStory(db, owner, "s1");
    expect(got?.story.title).toBe("My Story");
    expect(got?.story.status).toBe("draft");
    expect(got?.refs.map((r) => r.handle)).toEqual(["record:lima:a", "entity:lima:b"]);
  });

  it("lists a user's own stories newest-first", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write({ slug: "one" }), "2026-07-01T00:00:00.000Z", SHARE);
    await createStory(db, owner, "s2", write({ slug: "two" }), "2026-07-03T00:00:00.000Z", "share-2");
    const rows = await listStories(db, owner);
    expect(rows.map((r) => r.id)).toEqual(["s2", "s1"]);
  });

  it("replaces refs wholesale on update", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write(), NOW, SHARE);
    const ok = await updateStory(
      db,
      owner,
      "s1",
      write({ title: "Renamed", refs: [{ ord: 0, handle: "lead:lima:c", kind: "lead", title: "C" }] }),
      "2026-07-04T00:00:00.000Z",
      SHARE,
    );
    expect(ok).toBe(true);
    const got = await getStory(db, owner, "s1");
    expect(got?.story.title).toBe("Renamed");
    expect(got?.refs.map((r) => r.handle)).toEqual(["lead:lima:c"]);
  });

  it("deletes a story and cascades its refs", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write(), NOW, SHARE);
    expect(await deleteStory(db, owner, "s1")).toBe(true);
    expect(await getStory(db, owner, "s1")).toBeNull();
    const orphans = (await db.raw.query<{ n: number }>("SELECT COUNT(*)::int AS n FROM story_refs")).rows[0];
    expect(orphans.n).toBe(0);
  });
});

describe("stories store — owner scoping", () => {
  it("never reads, updates, or deletes another owner's story", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write(), NOW, SHARE);
    expect(await getStory(db, other, "s1")).toBeNull();
    expect(await updateStory(db, other, "s1", write({ title: "hijack" }), NOW, SHARE)).toBe(false);
    expect(await deleteStory(db, other, "s1")).toBe(false);
    // The real owner's story is untouched.
    expect((await getStory(db, owner, "s1"))?.story.title).toBe("My Story");
  });
});

describe("stories store — transactional integrity", () => {
  it("rolls the whole create back when a ref insert violates the PK (atomic batch)", async () => {
    const db = await fakePg();
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
        SHARE,
      ),
    ).rejects.toThrow();
    // The story row must not survive the failed batch.
    expect(await getStory(db, owner, "s1")).toBeNull();
  });

  it("rejects a second story with a duplicate (owner, site, slug)", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write({ slug: "dup" }), NOW, SHARE);
    await expect(createStory(db, owner, "s2", write({ slug: "dup" }), NOW, "share-2")).rejects.toThrow();
    // But a different owner may reuse the slug.
    await expect(
      createStory(db, other, "s3", write({ slug: "dup" }), NOW, "share-3"),
    ).resolves.toBeUndefined();
  });
});

describe("stories store — sharing (#1098)", () => {
  it("mints share_id + published_at only when published; a draft has neither", async () => {
    const db = await fakePg();
    await createStory(db, owner, "draft", write({ slug: "d", status: "draft" }), NOW, SHARE);
    await createStory(db, owner, "pub", write({ slug: "p", status: "published" }), NOW, "share-pub");
    expect((await getStory(db, owner, "draft"))?.story.share_id).toBeNull();
    expect((await getStory(db, owner, "pub"))?.story.share_id).toBe("share-pub");
    expect((await getStory(db, owner, "pub"))?.story.published_at).toBe(NOW);
  });

  it("keeps share_id sticky across publish → unpublish → republish", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write({ status: "published" }), NOW, "first-share");
    // unpublish
    await updateStory(db, owner, "s1", write({ status: "draft" }), "2026-07-04T00:00:00.000Z", "ignored");
    expect((await getStory(db, owner, "s1"))?.story.share_id).toBe("first-share");
    // republish — must reuse the original share_id, not the new candidate
    await updateStory(
      db,
      owner,
      "s1",
      write({ status: "published" }),
      "2026-07-05T00:00:00.000Z",
      "new-candidate",
    );
    expect((await getStory(db, owner, "s1"))?.story.share_id).toBe("first-share");
  });

  it("resolves a published story by share_id, but not a draft or unpublished one", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write({ status: "published" }), NOW, "share-1");
    expect((await getPublicStory(db, "share-1"))?.story.title).toBe("My Story");
    // unpublish → no longer publicly reachable
    await updateStory(db, owner, "s1", write({ status: "draft" }), NOW, "x");
    expect(await getPublicStory(db, "share-1")).toBeNull();
  });

  it("storyIdForShareId finds the row regardless of status", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write({ status: "published" }), NOW, "share-1");
    expect(await storyIdForShareId(db, "share-1")).toBe("s1");
    expect(await storyIdForShareId(db, "nope")).toBeNull();
  });
});

describe("stories store — moderation (#1098)", () => {
  it("an admin takedown makes a published story unreachable; restore brings it back", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write({ status: "published" }), NOW, "share-1");
    expect(await setModeration(db, "s1", "removed")).toBe(true);
    expect(await getPublicStory(db, "share-1")).toBeNull();
    // an owner edit cannot clear the takedown
    await updateStory(db, owner, "s1", write({ status: "published", title: "Edited" }), NOW, "x");
    expect(await getPublicStory(db, "share-1")).toBeNull();
    // admin restore
    expect(await setModeration(db, "s1", "ok")).toBe(true);
    expect((await getPublicStory(db, "share-1"))?.story.title).toBe("Edited");
  });
});

describe("stories store — reports (#1098)", () => {
  it("files reports and lists open ones newest-first, then resolves them", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write({ status: "published" }), NOW, "share-1");
    await insertReport(db, {
      id: "r1",
      storyId: "s1",
      shareId: "share-1",
      reason: "abuse",
      detail: "x",
      now: "2026-07-03T00:00:01.000Z",
    });
    await insertReport(db, {
      id: "r2",
      storyId: "s1",
      shareId: "share-1",
      reason: "spam",
      detail: "",
      now: "2026-07-03T00:00:02.000Z",
    });
    const open = await listReports(db, { openOnly: true });
    expect(open.map((r) => r.id)).toEqual(["r2", "r1"]);
    expect(await resolveReport(db, "r1")).toBe(true);
    expect((await listReports(db, { openOnly: true })).map((r) => r.id)).toEqual(["r2"]);
  });

  it("cascades reports when the story is deleted", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", write({ status: "published" }), NOW, "share-1");
    await insertReport(db, {
      id: "r1",
      storyId: "s1",
      shareId: "share-1",
      reason: "abuse",
      detail: "",
      now: NOW,
    });
    await deleteStory(db, owner, "s1");
    expect((await listReports(db)).length).toBe(0);
  });
});

describe("stories store — revalidation (#1099)", () => {
  // A story citing one handle, with the SDM + refs consistent, at catalog_version `cv`.
  function storyWith(handle: string, cv = "v1", slug = "my-story"): StoryWrite {
    return write({
      slug,
      catalog_version: cv,
      sdm_json: JSON.stringify({
        version: "1.0.0",
        blocks: [{ type: "atom", handle, kind: "record", title: "R" }],
      }),
      refs: [{ ord: 0, handle, kind: "record", title: "R" }],
    });
  }

  it("flags a story whose cited handle no longer resolves; skips current-version stories", async () => {
    const db = await fakePg();
    await createStory(db, owner, "gone", storyWith("record:lima:gone", "v1", "gone"), NOW, "s1");
    await createStory(db, owner, "fresh", storyWith("record:lima:a", "v2", "fresh"), NOW, "s2"); // already at v2

    const summary = await revalidateAll(db, { handles: new Set(["record:lima:a"]), version: "v2" }, {}, NOW);

    expect(summary.checked).toBe(1); // only "gone" is behind v2; "fresh" is skipped (untouched)
    expect(summary.flagged).toBe(1);
    expect(summary.flaggedIds).toEqual(["gone"]);
    expect((await getStory(db, owner, "gone"))?.story.stale).toBe(1);
    expect((await getStory(db, owner, "fresh"))?.story.stale).toBe(0);
  });

  it("auto-heals a renamed handle: rewrites the ref + stored SDM, and does not flag", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", storyWith("record:lima:old", "v1"), NOW, "sh");

    const summary = await revalidateAll(
      db,
      { handles: new Set(["record:lima:new"]), version: "v2" },
      { "record:lima:old": "record:lima:new" },
      NOW,
    );

    expect(summary.healed).toBe(1);
    expect(summary.flagged).toBe(0);
    const got = await getStory(db, owner, "s1");
    expect(got).not.toBeNull();
    if (!got) return;
    expect(got.story.stale).toBe(0);
    expect(got.story.catalog_version).toBe("v2");
    expect(got.refs[0].handle).toBe("record:lima:new");
    const doc = JSON.parse(got.story.sdm_json) as { blocks: { handle: string }[] };
    expect(doc.blocks[0].handle).toBe("record:lima:new");
  });

  it("is idempotent — a second pass over the same catalog checks nothing", async () => {
    const db = await fakePg();
    await createStory(db, owner, "s1", storyWith("record:lima:a", "v1"), NOW, "sh");
    await revalidateAll(db, { handles: new Set(["record:lima:a"]), version: "v2" }, {}, NOW);
    const second = await revalidateAll(db, { handles: new Set(["record:lima:a"]), version: "v2" }, {}, NOW);
    expect(second.checked).toBe(0);
  });
});
