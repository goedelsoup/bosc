/**
 * Build-time gate + link config for the Donate section of /about/contributing (#969).
 *
 * Ships dark: the section renders live only when the Stripe Payment Link URLs are set in
 * the Pages build env (PUBLIC_STRIPE_LINK_*) — the same discipline as Turnstile / Cognito /
 * Stories, so the section's visibility tracks whether payment links actually exist rather
 * than a hand-flipped boolean. An operator sets the repo vars when the Stripe account goes
 * live (see .github/workflows/pages.yml) and the section lights up with no code edit.
 *
 * Each tier is independently toggle-able: a tier card renders only when its own link is set,
 * so an operator can ship any subset (e.g. just Contributor + one-time). The section as a
 * whole appears once *any* link is present; the tier grid is suppressed when no recurring
 * tier is configured, so a one-time-only setup doesn't render an empty grid.
 *
 * Payment Links are external redirects — no server-side checkout session, so there is no
 * Pages Function peer. Recurring billing management (cancel, update) stays on Stripe's
 * hosted portal; Watermark ships no subscription-management UI.
 */

export interface DonateLinks {
  /** Follower — $5/mo recurring. */
  follower?: string;
  /** Contributor — $20/mo recurring. */
  contributor?: string;
  /** Sustainer — $50/mo recurring. */
  sustainer?: string;
  /** One-time — any/fixed amount. Rendered independently of the monthly tiers. */
  oneTime?: string;
}

/** The Stripe Payment Link URLs, read from the build-time PUBLIC_STRIPE_LINK_* env vars. */
export function donateLinks(): DonateLinks {
  return {
    follower: import.meta.env.PUBLIC_STRIPE_LINK_FOLLOWER,
    contributor: import.meta.env.PUBLIC_STRIPE_LINK_CONTRIBUTOR,
    sustainer: import.meta.env.PUBLIC_STRIPE_LINK_SUSTAINER,
    oneTime: import.meta.env.PUBLIC_STRIPE_LINK_ONETIME,
  };
}

/** True when at least one recurring tier link is set (governs whether the tier grid renders). */
export function hasRecurringTiers(links: DonateLinks = donateLinks()): boolean {
  return Boolean(links.follower || links.contributor || links.sustainer);
}

/**
 * The Donate section is shown when *any* link is present — each individual tier (and the
 * one-time strip) then gates on its own link, so operators can enable any subset. Wiring a
 * single tier flips the section live; the rest stay hidden until their links land.
 */
export function donateEnabled(links: DonateLinks = donateLinks()): boolean {
  return hasRecurringTiers(links) || Boolean(links.oneTime);
}
