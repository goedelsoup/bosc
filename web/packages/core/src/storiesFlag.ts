/**
 * The build-time feature gate for the user-authored Stories UI (#1096/#1097). The pages render the
 * live islands only when both Cognito auth *and* the Stories kill switch are enabled at build time —
 * otherwise an honest placeholder (the same discipline as the submit / ask pages). The server-side
 * peer is `STORIES_ENABLED` on the `/api/stories` Functions; this only governs whether the UI is
 * shown, never whether a write is accepted (that stays server-authoritative).
 */
import { selectableSitePaths } from "./sites";

export function storiesUiEnabled(): boolean {
  return (
    Boolean(import.meta.env.PUBLIC_COGNITO_DOMAIN && import.meta.env.PUBLIC_COGNITO_CLIENT_ID) &&
    import.meta.env.PUBLIC_STORIES_ENABLED === "true"
  );
}

/**
 * `getStaticPaths` for the four story TOOLS — compose, read, mine, grab-demo (#1894).
 *
 * Not the story a site publishes: `stories/<codename>/…` is editorial content and is unaffected.
 * These four are the authoring surface of a feature that has been dark since #1090 — `stories:
 * false` in `deploy/features.yaml` — and until now they built on every selectable site regardless,
 * sixteen routes whose entire content was "Reader-authored stories are coming soon." Nothing linked
 * them, because there is nothing to link to yet; the honest shape of a dark feature is a route that
 * does not exist, and appears the day the flag flips.
 *
 * `DEV` keeps them in `astro dev`, where `PUBLIC_STORIES_ENABLED` is never set and the placeholder's
 * `?preview` affordances are how the islands get looked at without auth or a store. Same rule as
 * `pages/showcase/[gallery].astro`: the development surface builds in development, and the deployed
 * artifact holds what it can actually serve.
 */
export function storyToolPaths(): Array<{ params: { site: string }; props: { slug: string } }> {
  return storiesUiEnabled() || import.meta.env.DEV ? selectableSitePaths() : [];
}
