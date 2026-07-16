/**
 * ReportControl (#1098) — the public report affordance on a shared Story. A reader can flag a story
 * for admin review (spam / abuse / misinfo / copyright / other). Collapsed to a quiet link by
 * default; expands to a small form. The endpoint is rate-limited + Turnstile-gated server-side; this
 * only collects a reason + optional detail. Never changes the story — an admin takedown does that.
 */
import { useState } from "react";
import { type ReportReason, reportStory } from "./client";
import { mono } from "./parts";

const REASONS: { value: ReportReason; label: string }[] = [
  { value: "abuse", label: "Abusive or harassing" },
  { value: "spam", label: "Spam" },
  { value: "misinformation", label: "Misleading about the record" },
  { value: "copyright", label: "Copyright" },
  { value: "other", label: "Something else" },
];

export default function ReportControl({ shareId }: { shareId: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason>("abuse");
  const [detail, setDetail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");

  async function submit() {
    setState("sending");
    const res = await reportStory(shareId, reason, detail);
    setState(res.ok ? "done" : "error");
  }

  if (state === "done") {
    return (
      <p style={{ fontSize: 12.5, color: "var(--ink-faint)" }}>
        Thanks — this story has been flagged for review.
      </p>
    );
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        style={{
          border: "none",
          background: "transparent",
          cursor: "pointer",
          fontFamily: mono,
          fontSize: 11.5,
          color: "var(--ink-faint)",
          textDecoration: "underline",
          padding: 0,
        }}
      >
        Report this story
      </button>
    );
  }

  return (
    <div
      style={{
        border: "1px solid var(--line-hair)",
        background: "var(--bone-surface)",
        padding: "14px 16px",
        maxWidth: 520,
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
          marginBottom: 8,
        }}
      >
        Report this story
      </div>
      <label style={{ display: "block", fontSize: 12.5, color: "var(--ink-muted)", marginBottom: 6 }}>
        Reason
        <select
          value={reason}
          onChange={(e) => setReason(e.target.value as ReportReason)}
          style={{
            display: "block",
            marginTop: 4,
            width: "100%",
            boxSizing: "border-box",
            border: "1px solid var(--line-hair)",
            background: "var(--bone-page)",
            padding: "7px 8px",
            fontSize: 13,
            color: "var(--ink-prose)",
          }}
        >
          {REASONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </label>
      <textarea
        value={detail}
        onChange={(e) => setDetail(e.target.value)}
        rows={2}
        placeholder="Anything else the reviewer should know (optional)"
        style={{
          width: "100%",
          boxSizing: "border-box",
          border: "1px solid var(--line-hair)",
          background: "var(--bone-page)",
          padding: "7px 8px",
          fontSize: 13,
          color: "var(--ink-prose)",
          resize: "vertical",
          marginBottom: 10,
        }}
      />
      {state === "error" && (
        <div style={{ fontSize: 12, color: "var(--ev-gap-fg)", marginBottom: 8 }}>
          Couldn't send the report. Try again.
        </div>
      )}
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button
          type="button"
          onClick={() => setOpen(false)}
          style={{
            border: "1px solid var(--line-2)",
            background: "var(--bone-surface)",
            color: "var(--ink-muted)",
            fontSize: 13,
            fontWeight: 700,
            padding: "7px 12px",
            cursor: "pointer",
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={state === "sending"}
          style={{
            border: "1px solid var(--forest)",
            background: "var(--forest)",
            color: "var(--bone-surface)",
            fontSize: 13,
            fontWeight: 700,
            padding: "7px 12px",
            cursor: state === "sending" ? "default" : "pointer",
            opacity: state === "sending" ? 0.6 : 1,
          }}
        >
          {state === "sending" ? "Sending…" : "Submit report"}
        </button>
      </div>
    </div>
  );
}
