/**
 * BulletinBoard — the public community board for a site. Anyone can read the posts and add one; the
 * author's reply-to is private (never returned by the public read). Server-authoritative: a new post
 * appears only after the server accepts it (the list is re-fetched). Admin takedown lives server-side
 * (/api/admin/contacts). Turnstile renders only when a site key is configured.
 */
import { type CSSProperties, useEffect, useState } from "react";
import { type BulletinPost, listBulletin, submitBulletin } from "./client";
import { useTurnstile } from "./useTurnstile";

interface Props {
  site: string;
  turnstileSiteKey?: string;
}

const mono: CSSProperties = { fontFamily: "var(--bosc-mono)", fontSize: "0.68rem", letterSpacing: "0.02em" };
const input: CSSProperties = {
  width: "100%",
  fontFamily: "var(--bosc-sans)",
  fontSize: "0.85rem",
  padding: "0.4rem 0.5rem",
  border: "1px solid var(--bosc-rule)",
  background: "var(--bosc-paper)",
  borderRadius: 0,
};
const btn: CSSProperties = {
  ...mono,
  cursor: "pointer",
  color: "var(--bosc-forest)",
  border: "1px solid var(--bosc-rule)",
  background: "var(--bosc-paper)",
  padding: "0.4rem 0.7rem",
};
const label: CSSProperties = {
  ...mono,
  color: "var(--bosc-muted)",
  display: "block",
  marginBottom: "0.2rem",
};

export default function BulletinBoard({ site, turnstileSiteKey }: Props) {
  const [posts, setPosts] = useState<BulletinPost[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ authorName: "", authorContact: "", title: "", body: "" });
  const [status, setStatus] = useState<"idle" | "sending" | "error">("idle");
  const [error, setError] = useState("");
  const turnstile = useTurnstile(turnstileSiteKey);

  const refresh = () =>
    listBulletin(site).then((r) => {
      if (r.ok) setPosts(r.value.posts);
      setLoaded(true);
    });

  // refresh closes over `site`, stable per mount; only re-run when `site` changes.
  useEffect(() => {
    refresh();
  }, [site]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("sending");
    setError("");
    const res = await submitBulletin({ site, ...form, turnstileToken: turnstile.token });
    if (res.ok) {
      setForm({ authorName: "", authorContact: "", title: "", body: "" });
      setOpen(false);
      setStatus("idle");
      turnstile.reset();
      await refresh();
    } else {
      setStatus("error");
      setError(res.error ?? "Something went wrong — try again.");
      turnstile.reset();
    }
  };

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <section style={{ marginTop: "2.5rem", borderTop: "1px solid var(--bosc-rule)", paddingTop: "1.2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "1rem" }}>
        <div>
          <div style={{ ...mono, color: "var(--bosc-muted)", textTransform: "uppercase" }}>
            Community board
          </div>
          <h2
            style={{
              fontFamily: "var(--bosc-sans)",
              fontSize: "1.2rem",
              fontWeight: 650,
              margin: "0.2rem 0 0",
            }}
          >
            Bulletin board
          </h2>
        </div>
        {!open && (
          <button type="button" style={btn} onClick={() => setOpen(true)}>
            Post a notice →
          </button>
        )}
      </div>

      {open && (
        <form
          onSubmit={submit}
          style={{ marginTop: "0.9rem", display: "grid", gap: "0.5rem", maxWidth: "30rem" }}
        >
          <div>
            <label style={label} htmlFor="bb-name">
              Your name
            </label>
            <input id="bb-name" style={input} required value={form.authorName} onChange={set("authorName")} />
          </div>
          <div>
            <label style={label} htmlFor="bb-contact">
              Reply-to (optional, private)
            </label>
            <input id="bb-contact" style={input} value={form.authorContact} onChange={set("authorContact")} />
          </div>
          <div>
            <label style={label} htmlFor="bb-title">
              Title
            </label>
            <input id="bb-title" style={input} required value={form.title} onChange={set("title")} />
          </div>
          <div>
            <label style={label} htmlFor="bb-body">
              Notice
            </label>
            <textarea
              id="bb-body"
              style={{ ...input, minHeight: "4rem", resize: "vertical" }}
              required
              value={form.body}
              onChange={set("body")}
            />
          </div>
          {turnstileSiteKey && <div ref={turnstile.ref} />}
          {status === "error" && <p style={{ ...mono, color: "var(--bosc-danger)" }}>{error}</p>}
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button type="submit" style={btn} disabled={status === "sending"}>
              {status === "sending" ? "Posting…" : "Post"}
            </button>
            <button
              type="button"
              style={{ ...btn, color: "var(--bosc-muted)" }}
              onClick={() => setOpen(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column" }}>
        {loaded && posts.length === 0 && (
          <p style={{ ...mono, color: "var(--bosc-faint)" }}>No notices yet — be the first to post.</p>
        )}
        {posts.map((p) => (
          <article key={p.id} style={{ padding: "0.8rem 0", borderBottom: "1px solid var(--bosc-rule)" }}>
            <h3
              style={{
                fontFamily: "var(--bosc-sans)",
                fontSize: "0.98rem",
                fontWeight: 650,
                margin: "0 0 0.2rem",
              }}
            >
              {p.title}
            </h3>
            <p style={{ margin: "0 0 0.4rem", color: "var(--bosc-ink)", lineHeight: 1.5 }}>{p.body}</p>
            <div style={{ ...mono, color: "var(--bosc-faint)" }}>
              {p.author_name} · {p.created_at.slice(0, 10)}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
