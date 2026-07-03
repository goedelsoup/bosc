/**
 * StoryReader (#1097) — the page-level reader island: the Story's title chrome (owner eyebrow, title,
 * dek, byline) over the shared `StoryRenderer`. Both Story owners render through here — the only
 * difference is the eyebrow + byline note (a reader Story vs a site-authored one).
 *
 * Two modes:
 *  - **preview** (`preview="reader"|"editorial"`) — renders a bundled fixture Story with no D1/auth,
 *    so the design renders full-fidelity in the static build and in review.
 *  - **live** — reads `?id=` from the URL, fetches the owner's Story (`GET /api/stories/:id`) and the
 *    render-catalog asset, and renders. Handles loading / not-enabled / sign-in / not-found honestly.
 */
import { useEffect, useState } from "react";
import { currentUser } from "~/lib/auth";
import type { StoryDocument } from "~/lib/sdm";
import type { HydratedCatalog } from "~/lib/storyAtoms";
import { FIXTURE_CATALOG, FIXTURE_EDITORIAL_STORY, FIXTURE_READER_STORY } from "~/lib/storyAtoms.fixture";
import StoryRenderer from "./StoryRenderer";
import { getStory, loadRenderCatalog } from "./client";
import { mono } from "./parts";

interface Loaded {
  ownerKind: "site" | "user";
  title: string;
  dek: string;
  author: string;
  updated: string;
  doc: StoryDocument;
  atoms: HydratedCatalog;
}

export interface StoryReaderProps {
  /** Render a bundled fixture Story instead of fetching (design preview). */
  preview?: "reader" | "editorial";
  /** The per-site render-catalog asset URL (built via `withSite` on the page). */
  atomsUrl?: string;
}

export default function StoryReader({ preview, atomsUrl }: StoryReaderProps) {
  const [state, setState] = useState<{
    status: "loading" | "ready" | "error";
    data?: Loaded;
    message?: string;
  }>({
    status: "loading",
  });

  useEffect(() => {
    let live = true;
    const params = new URLSearchParams(window.location.search);
    // `preview` can come from the prop (a dedicated preview page) or `?preview=` (the reader route).
    const mode = preview ?? (params.get("preview") as "reader" | "editorial" | null);
    if (mode) {
      const fx = mode === "editorial" ? FIXTURE_EDITORIAL_STORY : FIXTURE_READER_STORY;
      setState({
        status: "ready",
        data: {
          ownerKind: fx.ownerKind,
          title: fx.title,
          dek: fx.dek,
          author: fx.author,
          updated: fx.updated,
          doc: fx.doc,
          atoms: FIXTURE_CATALOG,
        },
      });
      return;
    }
    const id = params.get("id");
    if (!id) {
      setState({ status: "error", message: "No story specified." });
      return;
    }
    if (!currentUser()) {
      setState({ status: "error", message: "Sign in to read this story." });
      return;
    }
    (async () => {
      const [res, atoms] = await Promise.all([
        getStory(id),
        loadRenderCatalog(atomsUrl ?? "/stories-atoms.json"),
      ]);
      if (!live) return;
      if (!res.ok) {
        const msg =
          res.status === 404
            ? "This story doesn't exist, or isn't yours."
            : res.status === 503
              ? "Stories aren't enabled yet."
              : "Couldn't load this story.";
        setState({ status: "error", message: msg });
        return;
      }
      if (atoms === null) {
        // The Story loaded but its citations couldn't — don't render every atom as dangling.
        setState({ status: "error", message: "Couldn't load this story's citations. Reload to try again." });
        return;
      }
      const s = res.value.story;
      setState({
        status: "ready",
        data: {
          ownerKind: "user",
          title: s.title,
          dek: s.dek,
          author: currentUser()?.email ?? "You",
          updated: `updated ${relTime(s.updated_at)}`,
          doc: s.sdm,
          atoms,
        },
      });
    })();
    return () => {
      live = false;
    };
  }, [preview]);

  if (state.status === "loading") return <Centered>Loading…</Centered>;
  if (state.status === "error" || !state.data)
    return <Centered>{state.message ?? "Something went wrong."}</Centered>;

  const d = state.data;
  const isUser = d.ownerKind === "user";
  return (
    <article style={{ maxWidth: 720, margin: "0 auto" }}>
      <div
        style={{
          fontFamily: mono,
          fontSize: 11,
          fontWeight: 800,
          letterSpacing: "1px",
          textTransform: "uppercase",
          color: "var(--forest)",
          marginBottom: 8,
        }}
      >
        {isUser ? "Reader story" : "Editorial story"}
      </div>
      <h1
        style={{
          fontFamily: "var(--font-sans)",
          fontWeight: 800,
          fontSize: 38,
          letterSpacing: "-0.9px",
          lineHeight: 1.05,
          margin: "0 0 10px",
          color: "var(--ink)",
          textWrap: "pretty",
        }}
      >
        {d.title}
      </h1>
      <div
        style={{
          fontSize: 16,
          color: "var(--ink-prose)",
          lineHeight: 1.5,
          maxWidth: 620,
          marginBottom: 20,
          textWrap: "pretty",
        }}
      >
        {d.dek}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          paddingBottom: 22,
          borderBottom: "1px solid var(--line-hair)",
          marginBottom: 30,
        }}
      >
        <div
          style={{
            width: 34,
            height: 34,
            background: "var(--ink)",
            color: "var(--bone-surface)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: mono,
            fontWeight: 700,
            fontSize: 14,
            flex: "0 0 auto",
          }}
        >
          {(d.author || "?").charAt(0).toUpperCase()}
        </div>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--ink)" }}>{d.author}</div>
          <div
            style={{
              fontFamily: mono,
              fontSize: 10.5,
              letterSpacing: "0.7px",
              textTransform: "uppercase",
              color: "var(--ink-faint)",
            }}
          >
            {d.updated}
          </div>
        </div>
        <div
          style={{
            marginLeft: "auto",
            fontSize: 12,
            color: "var(--ink-faint)",
            maxWidth: 280,
            textAlign: "right",
            lineHeight: 1.4,
          }}
        >
          {isUser
            ? "Reader-assembled. The prose is theirs; every citation resolves live against the record."
            : "Site-authored — shares the exact same renderer as a reader Story. Only the byline differs."}
        </div>
      </div>

      <StoryRenderer doc={d.doc} atoms={d.atoms} />
    </article>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        maxWidth: 720,
        margin: "0 auto",
        padding: "60px 0",
        textAlign: "center",
        color: "var(--ink-muted)",
        fontSize: 14,
      }}
    >
      {children}
    </div>
  );
}

function relTime(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso;
  const secs = Math.max(0, (Date.now() - then) / 1000);
  const day = 86400;
  if (secs < 3600) return "just now";
  if (secs < day) return `${Math.floor(secs / 3600)}h ago`;
  if (secs < day * 30) return `${Math.floor(secs / day)}d ago`;
  return new Date(then).toISOString().slice(0, 10);
}
