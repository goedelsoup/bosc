/**
 * PetitionConnect — the "connect me with this petitioner" affordance on a contact card. The platform's
 * job here is to CONNECT a potential signer with the petitioner, not to warehouse a signature: the
 * reader leaves a private routing email (+ an optional public display name and note), and it lands on
 * the petitioner's hand-off queue. The public surface is only a running count + the opt-in names.
 *
 * Public (no account). Server-authoritative: the count shown is the server's tally, refreshed after a
 * successful submit. Turnstile is rendered only when a site key is configured (the server enforces it
 * only when its secret is set), so the widget is absent in the dark-launch state.
 */
import { type CSSProperties, useEffect, useState } from "react";
import { type ConnectTally, getConnectTally, submitConnect } from "./client";
import { useTurnstile } from "./useTurnstile";

interface Props {
  site: string;
  contactId: string;
  contactName: string;
  turnstileSiteKey?: string;
}

const wrap: CSSProperties = {
  marginTop: "0.7rem",
  borderTop: "1px solid var(--bosc-rule)",
  paddingTop: "0.7rem",
};
const mono: CSSProperties = { fontFamily: "var(--bosc-mono)", fontSize: "0.68rem", letterSpacing: "0.02em" };
const label: CSSProperties = {
  ...mono,
  color: "var(--bosc-muted)",
  display: "block",
  marginBottom: "0.2rem",
};
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

export default function PetitionConnect({ site, contactId, contactName, turnstileSiteKey }: Props) {
  const [tally, setTally] = useState<ConnectTally | null>(null);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [error, setError] = useState<string>("");
  const turnstile = useTurnstile(turnstileSiteKey);

  useEffect(() => {
    let live = true;
    getConnectTally(site, contactId).then((r) => {
      if (live && r.ok) setTally(r.value);
    });
    return () => {
      live = false;
    };
  }, [site, contactId]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("sending");
    setError("");
    const res = await submitConnect({
      site,
      contactId,
      email,
      displayName: name,
      message,
      turnstileToken: turnstile.token,
    });
    if (res.ok) {
      setStatus("done");
      // Server-authoritative: re-read the tally rather than guessing it locally, so the count + names
      // shown are ground truth (e.g. a blank display name isn't optimistically added to the roster).
      const fresh = await getConnectTally(site, contactId);
      if (fresh.ok) setTally(fresh.value);
    } else {
      setStatus("error");
      setError(res.error ?? "Something went wrong — try again.");
      turnstile.reset();
    }
  };

  const count = tally?.count ?? 0;

  return (
    <div style={wrap}>
      <div
        style={{
          ...mono,
          color: "var(--bosc-forest)",
          display: "flex",
          gap: "0.6rem",
          alignItems: "baseline",
        }}
      >
        <span>
          {count} {count === 1 ? "person wants" : "people want"} to connect
        </span>
        {!open && status !== "done" && (
          <button type="button" style={{ ...btn, padding: "0.2rem 0.5rem" }} onClick={() => setOpen(true)}>
            Connect with {contactName} →
          </button>
        )}
      </div>

      {tally && tally.names.length > 0 && (
        <div style={{ ...mono, color: "var(--bosc-faint)", marginTop: "0.3rem" }}>
          {tally.names.slice(0, 6).join(" · ")}
          {tally.names.length > 6 ? " · …" : ""}
        </div>
      )}

      {status === "done" ? (
        <p style={{ ...mono, color: "var(--bosc-forest)", marginTop: "0.5rem" }}>
          Thanks — we'll pass your interest to {contactName}. Your email stays private.
        </p>
      ) : (
        open && (
          <form
            onSubmit={submit}
            style={{ marginTop: "0.6rem", display: "grid", gap: "0.5rem", maxWidth: "26rem" }}
          >
            <div>
              <label style={label} htmlFor={`pc-email-${contactId}`}>
                Your email (private — shown only to the petitioner)
              </label>
              <input
                id={`pc-email-${contactId}`}
                style={input}
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label style={label} htmlFor={`pc-name-${contactId}`}>
                Display name (optional — shown publicly beside the count)
              </label>
              <input
                id={`pc-name-${contactId}`}
                style={input}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label style={label} htmlFor={`pc-msg-${contactId}`}>
                A note to the petitioner (optional)
              </label>
              <textarea
                id={`pc-msg-${contactId}`}
                style={{ ...input, minHeight: "3rem", resize: "vertical" }}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>
            {turnstileSiteKey && <div ref={turnstile.ref} />}
            {status === "error" && <p style={{ ...mono, color: "var(--bosc-danger)" }}>{error}</p>}
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button type="submit" style={btn} disabled={status === "sending"}>
                {status === "sending" ? "Sending…" : "Connect me"}
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
        )
      )}
    </div>
  );
}
