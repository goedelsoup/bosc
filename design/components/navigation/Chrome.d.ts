import * as React from "react";

export interface ChromeNavChild {
  /** Stable key, matched against `active` to highlight the parent tab. */
  key?: string;
  label?: string;
  href?: string;
  /** Small muted line under the label. */
  sub?: string;
  /** Right-aligned mono meta, e.g. a site count. */
  meta?: string;
  /** Render a divider instead of a link. */
  rule?: boolean;
}

export interface ChromeTab {
  key: string;
  label: string;
  href: string;
  /** Dropdown items. Presence of any makes the tab a menu trigger instead of a direct link. */
  children?: ChromeNavChild[];
}

export interface ChromeProps {
  /** "network" = the directory's own tabs; "site" = inside a site, its tabs + site chip. @default "site" */
  tier?: "network" | "site";
  /** Key of the active tab (or one of its children). */
  active?: string;
  /** Wordmark link target. @default "#" */
  brandHref?: string;
  /** Tab config. Defaults to a sensible Directory/Research/About (network) or Site/Story/Record (site) set. */
  tabs?: ChromeTab[];
  /** Site-tier chip text, e.g. "Lima". @default "Lima" */
  site?: string;
  /** Site-tier mono codename chip, e.g. "BOSC". @default "BOSC" */
  codename?: string;
  /** Site-tier status pill (Live, Building · 58%…). Pass "" to hide. @default "Live" */
  phase?: string;
  /** "Submit" button target. @default "#" */
  submitHref?: string;
  /** Override the right-hand platform cluster (Docs/Wiki/Submit/Ask/Search). */
  rightSlot?: React.ReactNode;
  /** Rendered in-flow below the bar when the site chip is toggled open — wire in your own site-switcher panel. */
  selector?: React.ReactNode;
  style?: React.CSSProperties;
}

/**
 * The global ink bar — two tiers, a site-chip breadcrumb, dropdown and simple nav menus.
 *
 * @startingPoint section="Navigation" subtitle="Network tier + site tier, with dropdown menus" viewport="1180x120"
 */
export function Chrome(props: ChromeProps): JSX.Element;
