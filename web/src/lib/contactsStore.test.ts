// Unit tests for the interactive site-contacts store (petition-connect + bulletin) against an
// in-memory Postgres (pglite) with the committed 0006 migration — so the private-vs-public split,
// the count/opt-in-name tally, and bulletin moderation are exercised on the real engine (Postgres)
// production uses. The harness applies every committed migration, so a schema/store drift fails here.

import { describe, expect, it } from "vitest";
import {
  insertBulletinPost,
  insertPetitionConnect,
  listBulletinPostsForAdmin,
  listConnectsForAdmin,
  listPublicBulletinPosts,
  publicConnectTally,
  setBulletinModeration,
} from "@fn/api/_lib/contactsStore";
import { fakePg } from "./_routeHarness";

const NOW = "2026-07-03T00:00:00.000Z";

function connect(over: Partial<Parameters<typeof insertPetitionConnect>[1]> = {}) {
  return {
    id: crypto.randomUUID(),
    site: "lima",
    contactId: "allen-county-commissioners",
    displayName: "Jane Q.",
    email: "jane@example.com",
    message: "count me in",
    now: NOW,
    ...over,
  };
}

function post(over: Partial<Parameters<typeof insertBulletinPost>[1]> = {}) {
  return {
    id: crypto.randomUUID(),
    site: "lima",
    contactId: "",
    authorName: "Sam",
    authorContact: "sam@example.com",
    title: "Meeting Thursday",
    body: "Organizing meeting at the library, 7pm.",
    now: NOW,
    ...over,
  };
}

describe("petition-connect store", () => {
  it("tallies connects publicly by count + opt-in names, and never the private email", async () => {
    const db = await fakePg();
    await insertPetitionConnect(db, connect({ displayName: "Jane Q." }));
    await insertPetitionConnect(db, connect({ displayName: "", email: "anon@example.com" })); // opted out of a public name
    await insertPetitionConnect(db, connect({ contactId: "ohio-epa-dapc", displayName: "Other" })); // different petitioner

    const tally = await publicConnectTally(db, "lima", "allen-county-commissioners");
    expect(tally.count).toBe(2); // both connects to this petitioner
    expect(tally.names).toEqual(["Jane Q."]); // the blank display name is dropped, not shown empty
    // The tally shape carries no email field at all — private routing never reaches the public rail.
    expect(JSON.stringify(tally)).not.toContain("example.com");
  });

  it("gives an admin the full hand-off queue (with the private email) scoped to their site", async () => {
    const db = await fakePg();
    await insertPetitionConnect(db, connect({ email: "jane@example.com" }));
    await insertPetitionConnect(db, connect({ site: "fort-wayne", email: "elsewhere@example.com" }));

    const lima = await listConnectsForAdmin(db, "lima");
    expect(lima).toHaveLength(1);
    expect(lima[0].email).toBe("jane@example.com"); // the petitioner can act on the hand-off
    // Site-scoped: another site's connects never leak into this queue.
    expect(lima.every((c) => c.site === "lima")).toBe(true);
  });

  it("can filter the admin queue to one petitioner", async () => {
    const db = await fakePg();
    await insertPetitionConnect(db, connect({ contactId: "allen-county-commissioners" }));
    await insertPetitionConnect(db, connect({ contactId: "ohio-epa-dapc" }));
    const scoped = await listConnectsForAdmin(db, "lima", { contactId: "ohio-epa-dapc" });
    expect(scoped).toHaveLength(1);
    expect(scoped[0].contact_id).toBe("ohio-epa-dapc");
  });
});

describe("bulletin board store", () => {
  it("lists un-removed posts publicly without the private reply-to", async () => {
    const db = await fakePg();
    const p = post({ authorContact: "sam@example.com" });
    await insertBulletinPost(db, p);

    const posts = await listPublicBulletinPosts(db, "lima");
    expect(posts).toHaveLength(1);
    expect(posts[0].title).toBe("Meeting Thursday");
    // The private reply-to is never in the public projection.
    expect(JSON.stringify(posts)).not.toContain("sam@example.com");
  });

  it("hides a removed post from the public board but keeps it for the admin", async () => {
    const db = await fakePg();
    const p = post();
    await insertBulletinPost(db, p);
    expect(await setBulletinModeration(db, p.id, "removed")).toBe(true);

    expect(await listPublicBulletinPosts(db, "lima")).toHaveLength(0);
    const adminView = await listBulletinPostsForAdmin(db, "lima");
    expect(adminView).toHaveLength(1);
    expect(adminView[0].moderation).toBe("removed");
  });

  it("scopes the public board to its own site", async () => {
    const db = await fakePg();
    await insertBulletinPost(db, post({ site: "lima" }));
    await insertBulletinPost(db, post({ site: "fort-wayne" }));
    expect(await listPublicBulletinPosts(db, "lima")).toHaveLength(1);
    expect(await listPublicBulletinPosts(db, "fort-wayne")).toHaveLength(1);
  });

  it("reports a no-op moderation of a missing post", async () => {
    const db = await fakePg();
    expect(await setBulletinModeration(db, "does-not-exist", "removed")).toBe(false);
  });
});
