/**
 * MyStories (#1096) — a reader's account view of their own Stories, surfaced under the site chrome
 * ("Your stories"). Owner-scoped by construction (`GET /api/stories` returns only the caller's), so
 * this never lists anyone else's. Lists by status with edit / share / delete and an honest empty
 * state; `?preview` renders a bundled sample so the design shows without auth.
 *
 * Chain of custody framing carried through: a reader's prose is plainly theirs; every cited record
 * keeps its own source + evidence tag and is never forked here.
 */
import { type CSSProperties, useEffect, useState } from "react";
import { currentUser } from "@watermark/viz/auth";
import { type StorySummary, deleteStory, listStories } from "./client";
import { mono } from "./parts";

const base = { catalog_version: "", published_at: null, created_at: "", stale: false };
const PREVIEW: StorySummary[] = [
  {
    ...base,
    id: "draft-1",
    site: "lima",
    slug: "whos-paying",
    title: "Who's actually paying for water here?",
    dek: "",
    status: "draft",
    share_id: null,
    updated_at: new Date().toISOString(),
  },
  {
    ...base,
    id: "pub-1",
    site: "lima",
    slug: "parcels-nobody-named",
    title: "The parcels nobody named",
    dek: "",
    status: "published",
    share_id: "s7k2-9pxq",
    published_at: new Date(Date.now() - 5 * 86400000).toISOString(),
    // a cited record was renamed in the corpus — the author is nudged to re-check (#1099).
    stale: true,
    updated_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  },
  {
    ...base,
    id: "draft-2",
    site: "lima",
    slug: "untitled",
    title: "",
    dek: "",
    status: "draft",
    share_id: null,
    updated_at: new Date(Date.now() - 14 * 86400000).toISOString(),
  },
];

export interface MyStoriesProps {
  newHref: string;
  composeHref: string;
  readHref: string;
}

export default function MyStories({ newHref, composeHref, readHref }: MyStoriesProps) {
  const [state, setState] = useState<{
    status: "loading" | "ready" | "error";
    stories?: StorySummary[];
    message?: string;
  }>({ status: "loading" });
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const preview = new URLSearchParams(window.location.search).has("preview");
    if (preview) {
      setState({ status: "ready", stories: PREVIEW });
      return;
    }
    if (!currentUser()) {
      setState({ status: "error", message: "Sign in to see your stories." });
      return;
    }
    (async () => {
      const res = await listStories();
      if (!live) return;
      if (res.ok) setState({ status: "ready", stories: res.value.stories });
      else
        setState({
          status: "error",
          message: res.status === 503 ? "Stories aren't enabled yet." : "Couldn't load your stories.",
        });
    })();
    return () => {
      live = false;
    };
  }, []);

  async function onDelete(id: string) {
    if (!window.confirm("Delete this story? This can't be undone.")) return;
    setActionError(null);
    const res = await deleteStory(id);
    // Optimistic removal only on success; on failure keep the story and surface the error (the same
    // kind of feedback the editor's save flow gives) rather than silently leaving the list unchanged.
    if (res.ok) {
      setState((s) => ({ ...s, stories: (s.stories ?? []).filter((x) => x.id !== id) }));
    } else {
      setActionError(
        res.status === 401 ? "Sign in to delete this story." : "Couldn't delete the story. Try again.",
      );
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 8,
          gap: 20,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: mono,
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: "1px",
              textTransform: "uppercase",
              color: "var(--forest)",
            }}
          >
            Your stories
          </div>
          <h1
            style={{
              fontFamily: "var(--font-sans)",
              fontWeight: 800,
              fontSize: 34,
              letterSpacing: "-0.8px",
              margin: "6px 0 0",
              color: "var(--ink)",
            }}
          >
            A curated read through the record — in your words.
          </h1>
        </div>
        <a href={newHref} style={forestBtn}>
          + New story
        </a>
      </div>
      <div
        style={{
          fontSize: 13.5,
          color: "var(--ink-muted)",
          margin: "8px 0 26px",
          maxWidth: 600,
          lineHeight: 1.5,
        }}
      >
        Your prose is plainly yours. Every record you cite keeps its own source and its own evidence tag —
        nothing here forks the record.
      </div>

      {actionError && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            border: "1px solid var(--ev-gap-border)",
            background: "var(--ev-gap-bg)",
            color: "var(--ev-gap-fg)",
            fontSize: 13,
            padding: "10px 14px",
            marginBottom: 18,
          }}
        >
          <span>{actionError}</span>
          <button
            type="button"
            onClick={() => setActionError(null)}
            style={{
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--ev-gap-fg)",
              fontSize: 13,
            }}
          >
            ✕
          </button>
        </div>
      )}

      {state.status === "ready" && (state.stories ?? []).some((s) => s.stale) && (
        <div
          style={{
            border: "1px solid var(--ev-inference-border)",
            background: "var(--ev-inference-bg)",
            color: "var(--ev-inference-fg)",
            fontSize: 13,
            lineHeight: 1.5,
            padding: "11px 14px",
            marginBottom: 18,
          }}
        >
          A reference in one of your stories needs attention — a cited record changed in the archive. Open the
          story to re-check it; until then it shows a placeholder where the citation was.
        </div>
      )}

      {state.status === "loading" && (
        <div style={{ padding: "40px 0", textAlign: "center", color: "var(--ink-muted)" }}>Loading…</div>
      )}
      {state.status === "error" && (
        <div style={{ padding: "40px 0", textAlign: "center", color: "var(--ink-muted)" }}>
          {state.message}
        </div>
      )}

      {state.status === "ready" &&
        (state.stories?.length ? (
          <div style={{ border: "1px solid var(--line-hair)", background: "var(--bone-surface)" }}>
            {state.stories.map((s) => (
              <StoryRow
                key={s.id}
                story={s}
                composeHref={composeHref}
                readHref={readHref}
                onDelete={() => onDelete(s.id)}
              />
            ))}
          </div>
        ) : (
          <div
            style={{
              border: "1px dashed var(--line-2)",
              background: "var(--bone-sunk)",
              padding: "48px 32px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 6, color: "var(--ink)" }}>
              You haven't started a Story yet.
            </div>
            <div
              style={{
                fontSize: 13.5,
                color: "var(--ink-muted)",
                maxWidth: 420,
                margin: "0 auto 18px",
                lineHeight: 1.5,
              }}
            >
              Grab any record, timeline event, or figure as you read the site — they'll wait here for you to
              arrange into a walkthrough.
            </div>
            <a href={newHref} style={forestBtn}>
              + New story
            </a>
          </div>
        ))}
    </div>
  );
}

function StoryRow({
  story,
  composeHref,
  readHref,
  onDelete,
}: {
  story: StorySummary;
  composeHref: string;
  readHref: string;
  onDelete: () => void;
}) {
  const published = story.status === "published";
  const meta = `Updated ${relDay(story.updated_at)}`;
  return (
    <div style={{ display: "flex", alignItems: "stretch", borderBottom: "1px solid var(--line-hair)" }}>
      <div style={{ flex: "0 0 3px", background: published ? "var(--forest)" : "var(--ink-ghost)" }} />
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          padding: "16px 18px",
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div style={{ flex: "1 1 220px", minWidth: 0 }}>
          <div style={{ fontSize: 16.5, fontWeight: 700, letterSpacing: "-0.1px", color: "var(--ink)" }}>
            {story.title || "Untitled draft"}
          </div>
          <div style={{ fontFamily: mono, fontSize: 11, color: "var(--ink-faint)", marginTop: 4 }}>
            {meta}
          </div>
        </div>
        <span
          style={{
            fontFamily: mono,
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.6px",
            textTransform: "uppercase",
            padding: "3px 9px",
            background: published ? "var(--forest-tint)" : "var(--bone-band)",
            color: published ? "var(--forest)" : "var(--ink-muted)",
          }}
        >
          {published ? "Published" : "Draft"}
        </span>
        {story.stale && (
          <span
            title="A cited record changed in the archive — re-check this story"
            style={{
              fontFamily: mono,
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.6px",
              textTransform: "uppercase",
              padding: "3px 9px",
              background: "var(--ev-inference-bg)",
              color: "var(--ev-inference-fg)",
              border: "1px solid var(--ev-inference-border)",
            }}
          >
            ⚠ Needs attention
          </span>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <a href={`${composeHref}?id=${encodeURIComponent(story.id)}`} style={rowLink("var(--ink-muted)")}>
            ✎ Edit
          </a>
          {published && story.share_id && (
            <a
              href={`${readHref}?share=${encodeURIComponent(story.share_id)}`}
              style={rowLink("var(--forest)")}
            >
              ↗ Share
            </a>
          )}
          <button
            type="button"
            onClick={onDelete}
            style={{
              ...rowLink("var(--ink-muted)"),
              border: "none",
              background: "transparent",
              cursor: "pointer",
            }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

const forestBtn: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: 14,
  fontWeight: 700,
  color: "var(--bone-surface)",
  background: "var(--forest)",
  border: "1px solid var(--forest)",
  padding: "11px 18px",
  textDecoration: "none",
};

const rowLink = (color: string): CSSProperties => ({
  fontSize: 12.5,
  fontWeight: 600,
  color,
  textDecoration: "none",
});

function relDay(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "recently";
  const days = Math.floor((Date.now() - then) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return new Date(then).toISOString().slice(0, 10);
}
