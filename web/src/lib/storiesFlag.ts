/**
 * The build-time feature gate for the user-authored Stories UI (#1096/#1097). The pages render the
 * live islands only when both Cognito auth *and* the Stories kill switch are enabled at build time —
 * otherwise an honest placeholder (the same discipline as the submit / ask pages). The server-side
 * peer is `STORIES_ENABLED` on the `/api/stories` Functions; this only governs whether the UI is
 * shown, never whether a write is accepted (that stays server-authoritative).
 */
export function storiesUiEnabled(): boolean {
  return (
    Boolean(import.meta.env.PUBLIC_COGNITO_DOMAIN && import.meta.env.PUBLIC_COGNITO_CLIENT_ID) &&
    import.meta.env.PUBLIC_STORIES_ENABLED === "true"
  );
}
