/**
 * StoryEditor (#1096) — the block-by-block authoring canvas for the closed SDM vocabulary. A reader
 * arranges the preordained blocks (heading 2–4 / paragraph / blockquote / list / callout) and cites
 * catalog atoms grabbed from the panel; there is no free-form HTML/JSX affordance by construction.
 *
 * Compile-once-store-run-many: the editor never ships SDM. On save it serializes the blocks to **DSL
 * source** (`serializeBlocksToDsl`) and POST/PUTs that to `/api/stories`, where the server recompiles,
 * re-validates every handle, and lowers to the SDM it persists. So author-facing errors are surfaced
 * two ways: cheaply on the client (raw-HTML paste blocked, unsafe-link flagged, dangling atom marked)
 * and authoritatively from the server response (unknown-handle / unsafe-link / unsupported).
 *
 * Seeds from, in order: an existing Story (`?id=`, edit mode), the grab tray (atoms grabbed while
 * reading), or `?preview` (the design sample). The atom previews reuse the runtime `StoryAtom`.
 */
import { useEffect, useMemo, useState } from "react";
import { CATALOG_KINDS, type CatalogKind } from "~/lib/catalog";
import { currentUser } from "~/lib/auth";
import {
  type EditorBlock,
  type HydratedAtom,
  type HydratedCatalog,
  sdmToEditorBlocks,
  serializeBlocksToDsl,
} from "~/lib/storyAtoms";
import { FIXTURE_CATALOG, FIXTURE_DANGLING } from "~/lib/storyAtoms.fixture";
import StoryAtom from "./StoryAtom";
import {
  type AuthorError,
  type StoryInput,
  createStory,
  getStory,
  loadRenderCatalog,
  updateStory,
} from "./client";
import { mono } from "./parts";
import { type TrayItem, readTray } from "./tray";

const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;
const UNSAFE_LINK_RE = /\]\((?!https?:|\/|mailto:|#)[^)]*\)/;
const HTML_PASTE_RE = /<\/?[a-z][\s\S]*>/i;

type Row = { id: string; block: EditorBlock };
type Snap = { kind: CatalogKind; title: string };

let seq = 0;
const uid = () => `r${seq++}`;
const row = (block: EditorBlock): Row => ({ id: uid(), block });

export interface StoryEditorProps {
  siteSlug: string;
}

export default function StoryEditor({ siteSlug }: StoryEditorProps) {
  const [ready, setReady] = useState(false);
  const [id, setId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [dek, setDek] = useState("");
  const [slug, setSlug] = useState("");
  const [status, setStatus] = useState<"draft" | "published">("draft");
  const [rows, setRows] = useState<Row[]>([]);
  const [snaps, setSnaps] = useState<Record<string, Snap>>({});
  const [catalog, setCatalog] = useState<HydratedCatalog>({});
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<"all" | CatalogKind>("all");
  const [pasteToast, setPasteToast] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<AuthorError[]>([]);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  // Load the render catalog (grab panel + atom previews) and, in edit mode, the Story.
  useEffect(() => {
    let live = true;
    const params = new URLSearchParams(window.location.search);
    const preview = params.has("preview");
    (async () => {
      const cat = preview ? FIXTURE_CATALOG : await loadRenderCatalog();
      if (!live) return;
      setCatalog(cat);

      const editId = params.get("id");
      if (editId && currentUser()) {
        const res = await getStory(editId);
        if (!live) return;
        if (res.ok) {
          const s = res.value.story;
          setId(s.id);
          setTitle(s.title);
          setDek(s.dek);
          setSlug(s.slug);
          setStatus(s.status);
          setRows(sdmToEditorBlocks(s.sdm).map(row));
          setSnaps(
            Object.fromEntries(
              s.refs.map((r) => [r.handle, { kind: r.kind as CatalogKind, title: r.title }]),
            ),
          );
          setReady(true);
          return;
        }
      }

      // new: seed from the grab tray, else the preview sample, else a minimal starter.
      const tray = readTray();
      if (preview) {
        seedPreview(setRows, setSnaps);
      } else if (tray.length > 0) {
        setRows(tray.map((t) => row({ type: "atom", handle: t.handle })));
        setSnaps(Object.fromEntries(tray.map((t: TrayItem) => [t.handle, { kind: t.kind, title: t.title }])));
      } else {
        setRows([row({ type: "heading", level: 2, text: "" }), row({ type: "paragraph", text: "" })]);
      }
      setReady(true);
    })();
    return () => {
      live = false;
    };
  }, []);

  const catalogAtoms = useMemo(() => Object.values(catalog), [catalog]);
  const filtered = useMemo(
    () =>
      catalogAtoms
        .filter((a) => kindFilter === "all" || a.kind === kindFilter)
        .filter((a) => !query || a.title.toLowerCase().includes(query.toLowerCase())),
    [catalogAtoms, kindFilter, query],
  );

  const setBlockText = (rid: string, text: string) =>
    setRows((rs) =>
      rs.map((r) => (r.id === rid && "text" in r.block ? { ...r, block: { ...r.block, text } } : r)),
    );
  const removeRow = (rid: string) => setRows((rs) => rs.filter((r) => r.id !== rid));
  const addBlock = (block: EditorBlock) => setRows((rs) => [...rs, row(block)]);
  const addAtom = (a: HydratedAtom) => {
    setSnaps((s) => ({ ...s, [a.handle]: { kind: a.kind, title: a.title } }));
    addBlock({ type: "atom", handle: a.handle });
  };

  const onPaste = (e: React.ClipboardEvent) => {
    const text = e.clipboardData.getData("text/plain");
    if (HTML_PASTE_RE.test(text)) {
      e.preventDefault();
      setPasteToast(true);
    }
  };

  async function save(nextStatus: "draft" | "published") {
    setErrors([]);
    setSavedNote(null);
    const localErrors: AuthorError[] = [];
    if (!title.trim()) localErrors.push({ kind: "unsupported", message: "Give the story a title." });
    if (!SLUG_RE.test(slug))
      localErrors.push({
        kind: "unsupported",
        message: "Slug must be lowercase letters, numbers, and dashes.",
      });
    if (localErrors.length) {
      setErrors(localErrors);
      return;
    }
    const input: StoryInput = {
      site: siteSlug,
      slug,
      title: title.trim(),
      dek: dek.trim(),
      status: nextStatus,
      source_format: "dsl",
      source_text: serializeBlocksToDsl(rows.map((r) => r.block)),
    };
    setSaving(true);
    const res = id ? await updateStory(id, input) : await createStory(input);
    setSaving(false);
    if (res.ok) {
      if (!id && "value" in res && "id" in (res.value as { id?: string }))
        setId((res.value as { id: string }).id);
      setStatus(nextStatus);
      if (nextStatus === "published") setPublishOpen(true);
      else setSavedNote("Draft saved.");
      return;
    }
    if (res.status === 409)
      setErrors([{ kind: "unsupported", message: "You already have a story with that slug." }]);
    else if (res.status === 401) setErrors([{ kind: "unsupported", message: "Sign in to save." }]);
    else if (res.errors?.length) setErrors(res.errors);
    else setErrors([{ kind: "unsupported", message: res.error ?? "Couldn't save the story." }]);
  }

  if (!ready)
    return (
      <div style={{ padding: "60px 0", textAlign: "center", color: "var(--ink-muted)" }}>Loading editor…</div>
    );

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto" }}>
      <TopBar
        status={status}
        saving={saving}
        onPasteDemo={() => setPasteToast(true)}
        onSaveDraft={() => save("draft")}
        onPublish={() => save("published")}
      />
      {savedNote && <Banner tone="ok">{savedNote}</Banner>}
      {errors.length > 0 && (
        <Banner tone="warn">
          <b>Couldn't save.</b>{" "}
          {errors.map((e) => (
            <span key={`${e.kind}-${e.message}`} style={{ display: "block" }}>
              • {e.message}{" "}
              {e.line ? <span style={{ color: "var(--ink-faint)" }}>(line {e.line})</span> : null}
            </span>
          ))}
        </Banner>
      )}
      {pasteToast && (
        <Banner tone="warn" onDismiss={() => setPasteToast(false)}>
          <b>Paste blocked.</b> The clipboard included raw HTML. A Story can only hold the closed block
          vocabulary — heading, paragraph, blockquote, list, callout, and cited atoms. Nothing was inserted.
        </Banner>
      )}

      {/* title / dek / slug */}
      <input
        type="text"
        placeholder="Story title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        style={{
          width: "100%",
          boxSizing: "border-box",
          border: "none",
          borderBottom: "2px solid var(--ink)",
          background: "transparent",
          fontFamily: "var(--font-sans)",
          fontWeight: 800,
          fontSize: 32,
          letterSpacing: "-0.5px",
          color: "var(--ink)",
          padding: "6px 0 10px",
          marginBottom: 10,
          outline: "none",
        }}
      />
      <textarea
        placeholder="One-line dek — what this story is about"
        value={dek}
        onChange={(e) => setDek(e.target.value)}
        rows={2}
        style={{
          width: "100%",
          boxSizing: "border-box",
          border: "1px solid var(--line-hair)",
          background: "var(--bone-surface)",
          fontFamily: "var(--font-sans)",
          fontSize: 14,
          lineHeight: 1.5,
          color: "var(--ink-prose)",
          padding: "9px 11px",
          outline: "none",
          resize: "vertical",
          marginBottom: 8,
        }}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 24 }}>
        <span style={{ fontFamily: mono, fontSize: 11, color: "var(--ink-faint)" }}>
          /{siteSlug}/stories/
        </span>
        <input
          type="text"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          placeholder="story-slug"
          style={{
            border: "1px solid var(--line-hair)",
            background: "var(--bone-surface)",
            fontFamily: mono,
            fontSize: 11,
            color: "var(--ink-muted)",
            padding: "4px 7px",
            outline: "none",
            width: 220,
          }}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "330px 1fr", gap: 28, alignItems: "start" }}>
        <GrabPanel
          query={query}
          onQuery={setQuery}
          kindFilter={kindFilter}
          onKindFilter={setKindFilter}
          atoms={filtered}
          onAdd={addAtom}
        />

        <div>
          <AddMenu onAdd={addBlock} />
          {rows.map((r) => (
            <BlockRow
              key={r.id}
              row={r}
              snap={r.block.type === "atom" ? snaps[r.block.handle] : undefined}
              atom={r.block.type === "atom" ? catalog[r.block.handle] : undefined}
              onChange={(text) => setBlockText(r.id, text)}
              onRemove={() => removeRow(r.id)}
              onPaste={onPaste}
            />
          ))}
        </div>
      </div>

      {publishOpen && <PublishModal siteSlug={siteSlug} slug={slug} onClose={() => setPublishOpen(false)} />}
    </div>
  );
}

// --- top bar + banners ----------------------------------------------------------------------
function TopBar({
  status,
  saving,
  onPasteDemo,
  onSaveDraft,
  onPublish,
}: {
  status: string;
  saving: boolean;
  onPasteDemo: () => void;
  onSaveDraft: () => void;
  onPublish: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        marginBottom: 18,
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <a
          href="mine"
          style={{ color: "var(--forest)", fontSize: 13, fontWeight: 700, textDecoration: "none" }}
        >
          ‹ My stories
        </a>
        <StatusPill status={status} />
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <Btn variant="ghost" onClick={onPasteDemo}>
          ▶ simulate: paste raw HTML
        </Btn>
        <Btn variant="ghost" onClick={onSaveDraft} disabled={saving}>
          Save draft
        </Btn>
        <Btn variant="forest" onClick={onPublish} disabled={saving}>
          Publish
        </Btn>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const published = status === "published";
  return (
    <span
      style={{
        fontFamily: mono,
        fontSize: 10,
        fontWeight: 800,
        letterSpacing: "0.6px",
        textTransform: "uppercase",
        padding: "3px 9px",
        background: published ? "var(--forest-tint)" : "var(--bone-band)",
        color: published ? "var(--forest)" : "var(--ink-muted)",
      }}
    >
      {published ? "Published" : "Draft"}
    </span>
  );
}

function Banner({
  tone,
  children,
  onDismiss,
}: {
  tone: "ok" | "warn";
  children: React.ReactNode;
  onDismiss?: () => void;
}) {
  const ok = tone === "ok";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 10,
        border: `1px solid ${ok ? "var(--forest-line)" : "var(--ev-gap-border)"}`,
        background: ok ? "var(--forest-tint)" : "var(--ev-gap-bg)",
        padding: "12px 14px",
        marginBottom: 18,
      }}
    >
      <div
        style={{
          flex: "1 1 auto",
          fontSize: 13,
          lineHeight: 1.5,
          color: ok ? "var(--forest)" : "var(--ev-gap-fg)",
        }}
      >
        {children}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
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
      )}
    </div>
  );
}

function Btn({
  variant,
  children,
  onClick,
  disabled,
}: {
  variant: "ghost" | "forest";
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}) {
  const forest = variant === "forest";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: "var(--font-sans)",
        fontSize: 13,
        fontWeight: 700,
        padding: "8px 14px",
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
        border: forest ? "1px solid var(--forest)" : "1px solid var(--line-2)",
        background: forest ? "var(--forest)" : "var(--bone-surface)",
        color: forest ? "var(--bone-surface)" : "var(--ink-muted)",
      }}
    >
      {children}
    </button>
  );
}

// --- grab panel -----------------------------------------------------------------------------
function GrabPanel({
  query,
  onQuery,
  kindFilter,
  onKindFilter,
  atoms,
  onAdd,
}: {
  query: string;
  onQuery: (v: string) => void;
  kindFilter: "all" | CatalogKind;
  onKindFilter: (v: "all" | CatalogKind) => void;
  atoms: HydratedAtom[];
  onAdd: (a: HydratedAtom) => void;
}) {
  const kinds: ("all" | CatalogKind)[] = ["all", ...CATALOG_KINDS];
  return (
    <div
      style={{
        border: "1px solid var(--line-hair)",
        background: "var(--bone-surface)",
        padding: 16,
        position: "sticky",
        top: 16,
      }}
    >
      <div
        style={{
          fontFamily: mono,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: "0.6px",
          textTransform: "uppercase",
          color: "var(--ink-faint)",
        }}
      >
        The catalog
      </div>
      <div style={{ fontSize: 12, color: "var(--ink-faint)", lineHeight: 1.4, margin: "6px 0 10px" }}>
        Grab an atom — a live pointer, never a copy. Every kind gets its own render slot at read time.
      </div>
      <input
        type="text"
        placeholder="Search records, entities, places…"
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        style={{
          width: "100%",
          boxSizing: "border-box",
          border: "1px solid var(--line-hair)",
          background: "var(--bone-page)",
          fontFamily: "var(--font-sans)",
          fontSize: 13,
          padding: "9px 10px",
          marginBottom: 10,
          outline: "none",
          color: "var(--ink-prose)",
        }}
      />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 14 }}>
        {kinds.map((k) => {
          const active = kindFilter === k;
          return (
            <button
              key={k}
              type="button"
              onClick={() => onKindFilter(k)}
              style={{
                fontFamily: mono,
                fontSize: 9.5,
                fontWeight: 700,
                letterSpacing: "0.4px",
                textTransform: "uppercase",
                padding: "3px 8px",
                cursor: "pointer",
                border: "none",
                background: active ? "var(--ink)" : "var(--bone-band)",
                color: active ? "var(--bone-surface)" : "var(--ink-muted)",
              }}
            >
              {k}
            </button>
          );
        })}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 7, maxHeight: 560, overflow: "auto" }}>
        {atoms.length === 0 && <div style={{ fontSize: 12, color: "var(--ink-faint)" }}>No atoms match.</div>}
        {atoms.map((a) => (
          <div
            key={a.handle}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              border: "1px solid var(--line-hair)",
              padding: "8px 10px",
            }}
          >
            <div style={{ flex: "1 1 auto", minWidth: 0 }}>
              <div
                style={{
                  fontSize: 12.5,
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  color: "var(--ink)",
                }}
              >
                {a.title}
              </div>
              <div style={{ fontFamily: mono, fontSize: 10, color: "var(--ink-faint)", marginTop: 1 }}>
                {a.kindLabel}
              </div>
            </div>
            <button
              type="button"
              onClick={() => onAdd(a)}
              aria-label={`Cite ${a.title}`}
              style={{
                flex: "0 0 auto",
                width: 24,
                height: 24,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: "1px solid var(--forest-line)",
                background: "var(--forest-tint)",
                color: "var(--forest)",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              +
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- add-block menu -------------------------------------------------------------------------
function AddMenu({ onAdd }: { onAdd: (b: EditorBlock) => void }) {
  const items: { label: string; block: EditorBlock }[] = [
    { label: "H2", block: { type: "heading", level: 2, text: "New heading" } },
    { label: "H3", block: { type: "heading", level: 3, text: "New heading" } },
    { label: "H4", block: { type: "heading", level: 4, text: "New heading" } },
    { label: "¶ Paragraph", block: { type: "paragraph", text: "" } },
    { label: "❝ Blockquote", block: { type: "blockquote", text: "" } },
    { label: "• List", block: { type: "list", ordered: false, items: ["New item"] } },
    { label: "◆ Callout · note", block: { type: "callout", variant: "note", text: "" } },
    { label: "◆ Callout · info", block: { type: "callout", variant: "info", text: "" } },
    { label: "◆ Callout · warning", block: { type: "callout", variant: "warning", text: "" } },
  ];
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 6,
        marginBottom: 18,
        padding: "10px 12px",
        border: "1px dashed var(--line-2)",
        background: "var(--bone-sunk)",
      }}
    >
      <span
        style={{
          fontFamily: mono,
          fontSize: 9.5,
          fontWeight: 700,
          letterSpacing: "0.5px",
          textTransform: "uppercase",
          color: "var(--ink-faint)",
          alignSelf: "center",
          marginRight: 4,
        }}
      >
        + add block ·
      </span>
      {items.map((it) => (
        <button
          key={it.label}
          type="button"
          onClick={() => onAdd(it.block)}
          style={{
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 600,
            color: "var(--ink-muted)",
            background: "var(--bone-surface)",
            border: "1px solid var(--line-2)",
            padding: "5px 10px",
          }}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

// --- one editable block ---------------------------------------------------------------------
function BlockRow({
  row: r,
  snap,
  atom,
  onChange,
  onRemove,
  onPaste,
}: {
  row: Row;
  snap?: Snap;
  atom?: HydratedAtom;
  onChange: (text: string) => void;
  onRemove: () => void;
  onPaste: (e: React.ClipboardEvent) => void;
}) {
  const b = r.block;
  const tag = tagLabel(b);
  const tagStyle: React.CSSProperties =
    b.type === "atom"
      ? { color: "var(--bone-surface)", background: "var(--forest)" }
      : b.type === "callout"
        ? { color: "var(--ev-inference-fg)", background: "var(--ev-inference-bg)" }
        : b.type === "heading"
          ? { color: "var(--bone-surface)", background: "var(--ink)" }
          : { color: "var(--ink-muted)", background: "var(--bone-band)" };
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "flex-start", marginBottom: 14 }}>
      <div style={{ flex: "0 0 52px", paddingTop: 6, textAlign: "right" }}>
        <span
          style={{
            fontFamily: mono,
            fontSize: 9,
            fontWeight: 800,
            letterSpacing: "0.3px",
            textTransform: "uppercase",
            padding: "2px 6px",
            ...tagStyle,
          }}
        >
          {tag}
        </span>
      </div>
      <div style={{ flex: "1 1 auto", minWidth: 0 }}>
        {b.type === "atom" ? (
          <>
            <StoryAtom
              handle={b.handle}
              snapshotKind={snap?.kind ?? atom?.kind ?? "record"}
              snapshotTitle={snap?.title ?? atom?.title ?? b.handle}
              atom={atom}
            />
            {!atom && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  fontSize: 12,
                  color: "var(--ink-ghost)",
                  background: "var(--bone-band)",
                  border: "1px solid var(--line-2)",
                  padding: "6px 10px",
                  marginTop: 2,
                }}
              >
                ⚠ This handle no longer resolves.
                <button
                  type="button"
                  onClick={onRemove}
                  style={{
                    border: "none",
                    background: "transparent",
                    color: "var(--forest)",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  Remove
                </button>
              </div>
            )}
          </>
        ) : (
          <EditableBlock block={b} onChange={onChange} onPaste={onPaste} />
        )}
      </div>
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove block"
        style={{
          flex: "0 0 auto",
          border: "none",
          background: "transparent",
          color: "var(--ink-faint)",
          cursor: "pointer",
          fontSize: 13,
          paddingTop: 6,
        }}
      >
        ✕
      </button>
    </div>
  );
}

function EditableBlock({
  block,
  onChange,
  onPaste,
}: {
  block: EditorBlock;
  onChange: (text: string) => void;
  onPaste: (e: React.ClipboardEvent) => void;
}) {
  if (block.type === "list") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 5, padding: "4px 6px" }}>
        {block.items.map((it, i) => (
          <div
            key={i}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 15, color: "var(--ink-prose)" }}
          >
            <span style={{ color: "var(--ink-faint)" }}>•</span>
            {it}
          </div>
        ))}
        <div style={{ fontFamily: mono, fontSize: 10.5, color: "var(--ink-faint)" }}>
          list items edit inline in the full build
        </div>
      </div>
    );
  }
  const text = "text" in block ? block.text : "";
  const isHeading = block.type === "heading";
  const size = isHeading
    ? block.level === 2
      ? 24
      : block.level === 3
        ? 20
        : 17
    : block.type === "blockquote"
      ? 16.5
      : block.type === "callout"
        ? 13.5
        : 17;
  const weight = isHeading ? 800 : 400;
  const wrap =
    block.type === "callout"
      ? {
          border: `1px solid ${calloutBorder(block.variant)}`,
          background: calloutBg(block.variant),
          padding: "11px 13px",
        }
      : {};
  const showUnsafe = block.type === "paragraph" && UNSAFE_LINK_RE.test(text);
  return (
    <div style={wrap}>
      <textarea
        value={text}
        onChange={(e) => onChange(e.target.value)}
        onPaste={onPaste}
        rows={block.type === "paragraph" ? 3 : block.type === "callout" ? 2 : 1}
        placeholder={placeholderFor(block)}
        style={{
          width: "100%",
          boxSizing: "border-box",
          border: "none",
          background: "transparent",
          fontFamily: "var(--font-sans)",
          fontSize: size,
          fontWeight: weight,
          fontStyle: block.type === "blockquote" ? "italic" : "normal",
          lineHeight: 1.5,
          color: isHeading
            ? "var(--ink)"
            : block.type === "blockquote"
              ? "var(--ink-muted)"
              : "var(--ink-prose)",
          resize: "vertical",
          outline: "none",
          padding: block.type === "callout" ? 0 : "4px 6px",
        }}
      />
      {showUnsafe && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            fontSize: 12,
            color: "var(--ev-gap-fg)",
            background: "var(--ev-gap-bg)",
            border: "1px solid var(--ev-gap-border)",
            padding: "6px 10px",
            marginTop: 2,
          }}
        >
          ⚠ Unsafe link — only http(s) links are kept in a Story.
        </div>
      )}
    </div>
  );
}

// --- publish modal --------------------------------------------------------------------------
function PublishModal({ siteSlug, slug, onClose }: { siteSlug: string; slug: string; onClose: () => void }) {
  const link = `${window.location.origin}/network/${siteSlug}/stories/read?slug=${slug}`;
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(22,32,26,0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
      }}
    >
      <div
        style={{
          background: "var(--bone-surface)",
          border: "2px solid var(--ink)",
          maxWidth: 460,
          width: "90%",
          padding: 28,
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            fontFamily: mono,
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: "0.8px",
            textTransform: "uppercase",
            color: "var(--forest)",
          }}
        >
          Published
        </div>
        <div style={{ fontSize: 15, lineHeight: 1.55, color: "var(--ink-prose)", margin: "10px 0 18px" }}>
          Anyone with the link can read it. It stays read-only, carries your byline, and comes down instantly
          via the kill switch if it's flagged.
        </div>
        <div
          style={{
            fontFamily: mono,
            fontSize: 10,
            letterSpacing: "1px",
            textTransform: "uppercase",
            color: "var(--ink-faint)",
            marginBottom: 6,
          }}
        >
          Share link
        </div>
        <div
          style={{
            fontFamily: mono,
            fontSize: 12.5,
            background: "var(--bone-sunk)",
            border: "1px solid var(--line-hair)",
            padding: "10px 12px",
            marginBottom: 20,
            wordBreak: "break-all",
            color: "var(--ink-prose)",
          }}
        >
          {link}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <Btn variant="forest" onClick={onClose}>
            Done
          </Btn>
        </div>
      </div>
    </div>
  );
}

// --- helpers --------------------------------------------------------------------------------
function tagLabel(b: EditorBlock): string {
  switch (b.type) {
    case "heading":
      return `H${b.level}`;
    case "paragraph":
      return "¶";
    case "blockquote":
      return "quote";
    case "list":
      return "list";
    case "callout":
      return b.variant;
    case "atom":
      return "cited";
  }
}

function placeholderFor(b: EditorBlock): string {
  if (b.type === "heading") return "Heading";
  if (b.type === "blockquote") return "A quoted aside…";
  if (b.type === "callout") return "An author-framed aside…";
  return "Write in your own voice…";
}

function calloutBorder(v: "note" | "info" | "warning"): string {
  return v === "info" ? "var(--forest-line)" : v === "warning" ? "var(--ev-gap-border)" : "var(--line-2)";
}
function calloutBg(v: "note" | "info" | "warning"): string {
  return v === "info" ? "var(--forest-tint)" : v === "warning" ? "var(--ev-gap-bg)" : "var(--bone-sunk)";
}

function seedPreview(setRows: (r: Row[]) => void, setSnaps: (s: Record<string, Snap>) => void) {
  const blocks: EditorBlock[] = [
    { type: "heading", level: 2, text: "Start with the deed" },
    {
      type: "paragraph",
      text: "Three parcels changed hands inside of a month, all to the same buyer of record.",
    },
    { type: "atom", handle: "record:lima:deed-0008300" },
    {
      type: "paragraph",
      text: "The confirming disclosure sits on the AEDG site — see [the filing](ftp://aedg/x) (an unsafe link, flagged).",
    },
    {
      type: "callout",
      variant: "note",
      text: "This is a lead, not a verdict — the shell's owner wasn't confirmed until a later disclosure.",
    },
    { type: "atom", handle: FIXTURE_DANGLING.handle },
    { type: "blockquote", text: "A Delaware shell. Withheld land prices. Backup generators by the hundred." },
    {
      type: "list",
      ordered: false,
      items: ["Deed recorded, 2025-08-13", "Site clearing begins, 2025-03-11"],
    },
    { type: "atom", handle: "entity:lima:bistrozzi-llc" },
  ];
  setRows(blocks.map(row));
  setSnaps({
    "record:lima:deed-0008300": { kind: "record", title: "Limited Warranty Deed" },
    [FIXTURE_DANGLING.handle]: { kind: FIXTURE_DANGLING.kind, title: FIXTURE_DANGLING.title },
    "entity:lima:bistrozzi-llc": { kind: "entity", title: "Bistrozzi LLC" },
  });
}
