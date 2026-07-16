/**
 * The build-time feature gate for the interactive site-contacts UI (petition-connect + bulletin).
 * The contacts page renders the live islands only when the contacts kill switch is on at build time;
 * otherwise the page stays the read-only directory (Phase 1). Unlike Stories, the interactive
 * contacts surfaces are *public* (no account needed to connect or post), so this gate does not
 * require Cognito — only `PUBLIC_CONTACTS_ENABLED`. The server-side peer is `CONTACTS_ENABLED` on the
 * Functions; this only governs whether the UI is shown, never whether a write is accepted (that stays
 * server-authoritative).
 */
export function contactsUiEnabled(): boolean {
  return import.meta.env.PUBLIC_CONTACTS_ENABLED === "true";
}

/** The Turnstile site key, when configured — the islands render the widget only when it's present
 *  (its server peer `TURNSTILE_SECRET` is what actually enforces verification). */
export function turnstileSiteKey(): string | undefined {
  return import.meta.env.PUBLIC_TURNSTILE_SITE_KEY || undefined;
}
