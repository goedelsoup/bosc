/// <reference types="astro/client" />

interface ImportMetaEnv {
  /**
   * Cloudflare Turnstile site key (public). Set in the host/CI build env once the
   * submissions endpoint is bootstrapped (docs/submissions-api.md). When unset, the
   * submit form (the shared SubmitForm, served at both /submit and /network/american-sugar-creek-allen-co/submit) renders
   * as a disabled placeholder — so the form's enabled state tracks whether the endpoint
   * is actually live.
   */
  readonly PUBLIC_TURNSTILE_SITE_KEY?: string;
  /**
   * Cognito Hosted UI domain (public — not a secret). Set in the CI build env when
   * AUTH_ENABLED="true". e.g. "auth.watermarkdirectory.org" or the Cognito-provided
   * "{prefix}.auth.{region}.amazoncognito.com". Unset → account pages degrade to a
   * disabled placeholder (same pattern as Turnstile above).
   */
  readonly PUBLIC_COGNITO_DOMAIN?: string;
  /**
   * Cognito app client ID (public). Identifies the app client in PKCE authorize requests.
   */
  readonly PUBLIC_COGNITO_CLIENT_ID?: string;
  /**
   * Browser RUM kill switch (build-time). Set to "true" in the Pages build env to inject
   * the web-vitals beacon script. Also requires RUM_ENABLED="true" in the dashboard; the
   * /api/rum beacon no-ops when that flag is absent. See docs/rum.md.
   */
  readonly PUBLIC_RUM_ENABLED?: string;
  /**
   * Stripe Payment Link URLs for the Donate section of /about/contributing (#969). Public
   * (a payment link is not a secret). Read at build time by `src/lib/donate.ts`; when the
   * three monthly-tier links are unset the whole Donate section is hidden (ships dark, same
   * pattern as Turnstile above). Set as repo vars in the Pages build env once the Stripe
   * account is live — no code change flips the section on.
   */
  readonly PUBLIC_STRIPE_LINK_FOLLOWER?: string;
  readonly PUBLIC_STRIPE_LINK_CONTRIBUTOR?: string;
  readonly PUBLIC_STRIPE_LINK_SUSTAINER?: string;
  /** One-time contribution Payment Link (custom or fixed amount); gates the one-time strip. */
  readonly PUBLIC_STRIPE_LINK_ONETIME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare namespace App {
  /**
   * Per-request locals. `site` is the active network site's registry slug — the seam the
   * multi-site build (#724) routes on. Set by `src/middleware.ts`; today always `"lima"`
   * (the only rendered site), later resolved from the `[site]` route param (#734). Pages
   * that render a known site pass it explicitly to `siteHref(slug, …)`.
   */
  interface Locals {
    site: string;
  }
}
