/**
 * StoryRenderer (#1097) — the runtime renderer for a lowered `StoryDocument`. Walks the closed SDM
 * block vocabulary and renders reader prose **visually distinct** from cited atoms (#1090): prose is
 * plain measure-width type; every cited atom is a bordered card (via `StoryAtom`). The renderer is
 * exhaustive over the vocabulary — an out-of-vocabulary node can't occur (the write path validated
 * the doc), and each atom resolves live against the fetched render catalog.
 *
 * Shared by both Story owners: a site-authored (editorial) Story and a reader-authored one lower to
 * the same SDM and render through this same component. Only the surrounding byline differs.
 */
import type { SdmBlock, SdmInline, StoryDocument } from "@watermark/core/sdm";
import type { HydratedCatalog } from "@watermark/core/storyAtoms";
import StoryAtom from "./StoryAtom";
import { mono } from "./parts";

export interface StoryRendererProps {
  doc: StoryDocument;
  /** Resolved atoms keyed by handle (the `/stories-atoms.json` asset). Missing key ⇒ dangling. */
  atoms: HydratedCatalog;
  /** Handles the island is still resolving — rendered as skeletons until present in `atoms`. */
  loadingHandles?: ReadonlySet<string>;
}

export default function StoryRenderer({ doc, atoms, loadingHandles }: StoryRendererProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {doc.blocks.map((block, i) => (
        <Block key={i} block={block} atoms={atoms} loadingHandles={loadingHandles} />
      ))}
    </div>
  );
}

function Block({
  block,
  atoms,
  loadingHandles,
}: {
  block: SdmBlock;
  atoms: HydratedCatalog;
  loadingHandles?: ReadonlySet<string>;
}) {
  switch (block.type) {
    case "heading": {
      const size = block.level === 2 ? 24 : block.level === 3 ? 20 : 17;
      const weight = block.level === 4 ? 700 : 800;
      const ls = block.level === 2 ? "-0.4px" : block.level === 3 ? "-0.3px" : "-0.1px";
      return (
        <div
          role="heading"
          aria-level={block.level}
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: weight,
            fontSize: size,
            letterSpacing: ls,
            color: "var(--ink)",
          }}
        >
          <Inline nodes={block.children} />
        </div>
      );
    }
    case "paragraph":
      return (
        <p
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 17,
            lineHeight: 1.65,
            color: "var(--ink-prose)",
            margin: 0,
            textWrap: "pretty",
          }}
        >
          <Inline nodes={block.children} />
        </p>
      );
    case "blockquote":
      return (
        <blockquote
          style={{
            margin: 0,
            paddingLeft: 16,
            borderLeft: "2px solid var(--ink-ghost)",
            fontFamily: "var(--font-sans)",
            fontSize: 16.5,
            lineHeight: 1.6,
            color: "var(--ink-muted)",
            fontStyle: "italic",
          }}
        >
          {block.children.map((b, i) => (
            <Block key={i} block={b} atoms={atoms} loadingHandles={loadingHandles} />
          ))}
        </blockquote>
      );
    case "list":
      return block.ordered ? (
        <ol style={listStyle}>
          {block.items.map((item, i) => (
            <li key={i}>
              {item.map((b, j) => (
                <Block key={j} block={b} atoms={atoms} loadingHandles={loadingHandles} />
              ))}
            </li>
          ))}
        </ol>
      ) : (
        <ul style={listStyle}>
          {block.items.map((item, i) => (
            <li key={i}>
              {item.map((b, j) => (
                <Block key={j} block={b} atoms={atoms} loadingHandles={loadingHandles} />
              ))}
            </li>
          ))}
        </ul>
      );
    case "callout":
      return <Callout block={block} atoms={atoms} loadingHandles={loadingHandles} />;
    case "atom": {
      const resolved = atoms[block.handle];
      const loading = loadingHandles?.has(block.handle) && !resolved;
      return (
        <StoryAtom
          handle={block.handle}
          snapshotKind={block.kind}
          snapshotTitle={block.title}
          atom={resolved}
          loading={loading}
        />
      );
    }
  }
}

const listStyle = {
  margin: 0,
  paddingLeft: 22,
  display: "flex",
  flexDirection: "column" as const,
  gap: 6,
  fontFamily: "var(--font-sans)",
  fontSize: 16,
  lineHeight: 1.55,
  color: "var(--ink-prose)",
};

const CALLOUT_STYLE: Record<string, { border: string; bg: string; fg: string; label: string }> = {
  note: { border: "var(--line-2)", bg: "var(--bone-sunk)", fg: "var(--ink-muted)", label: "NOTE" },
  info: { border: "var(--forest-line)", bg: "var(--forest-tint)", fg: "var(--forest)", label: "CONTEXT" },
  warning: {
    border: "var(--ev-gap-border)",
    bg: "var(--ev-gap-bg)",
    fg: "var(--ev-gap-fg)",
    label: "⚠ FLAG",
  },
};

function Callout({
  block,
  atoms,
  loadingHandles,
}: {
  block: Extract<SdmBlock, { type: "callout" }>;
  atoms: HydratedCatalog;
  loadingHandles?: ReadonlySet<string>;
}) {
  const s = CALLOUT_STYLE[block.variant] ?? CALLOUT_STYLE.note;
  return (
    <div style={{ border: `1px solid ${s.border}`, background: s.bg, padding: "13px 16px" }}>
      <div
        style={{
          fontFamily: mono,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: "0.7px",
          textTransform: "uppercase",
          color: s.fg,
          marginBottom: 5,
        }}
      >
        {s.label}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          fontSize: 14.5,
          lineHeight: 1.5,
          color: "var(--ink-prose)",
        }}
      >
        {block.children.map((b, i) => (
          <Block key={i} block={b} atoms={atoms} loadingHandles={loadingHandles} />
        ))}
      </div>
    </div>
  );
}

// --- inline runs ----------------------------------------------------------------------------
function Inline({ nodes }: { nodes: SdmInline[] }) {
  return (
    <>
      {nodes.map((n, i) => (
        <InlineNode key={i} node={n} />
      ))}
    </>
  );
}

function InlineNode({ node }: { node: SdmInline }) {
  switch (node.type) {
    case "text":
      return <span>{node.value}</span>;
    case "strong":
      return (
        <strong>
          <Inline nodes={node.children} />
        </strong>
      );
    case "emphasis":
      return (
        <em>
          <Inline nodes={node.children} />
        </em>
      );
    case "code":
      return (
        <code
          style={{ fontFamily: mono, fontSize: "0.9em", background: "var(--bone-sunk)", padding: "1px 4px" }}
        >
          {node.value}
        </code>
      );
    case "link":
      return (
        <a
          href={node.href}
          style={{ color: "var(--forest)", textDecoration: "underline" }}
          rel="nofollow ugc noopener"
          target="_blank"
        >
          <Inline nodes={node.children} />
        </a>
      );
  }
}
