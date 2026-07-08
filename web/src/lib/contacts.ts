/**
 * Site-level contacts — the presentation vocabulary + helpers for a site's contacts directory.
 *
 * The contact DATA is a per-site bundle feed (`contacts`), read from each site's committed
 * `data/site/contacts.yaml` — so a peer carries its own contacts, not Lima's. This module is the
 * `Contact` shape (the feed row type), the kind presentation map, the filter list, and the
 * `contactCount` reducer.
 *
 * PROVENANCE DISCIPLINE (enforced in the feed model `bosc.site.feeds.ContactItem`): every contact
 * names a real committed `source`, and `links` carry only *public* routing — private hand-off
 * addresses (where a petition-connect is delivered) never enter the bundle. No fabricated people.
 */

/** The kinds of contact point a site carries. */
export type ContactKind = "petitioner" | "organizer" | "official" | "group" | "outlet";

/** A public way to reach or read about a contact — the parent `Contact` carries the `source`. */
export interface ContactLink {
  label: string;
  url: string;
}

export interface Contact {
  /** Stable local id (kebab slug) — the catalog handle's local_id (shown mono). */
  id: string;
  kind: ContactKind;
  name: string;
  /** Affiliated organization, when distinct from the name. */
  org?: string;
  /** Title / relationship ("lead organizer", "county commissioner"). */
  role?: string;
  /** What they work on / the cause — one honest sentence. */
  summary: string;
  /** Public routing only (petition page, website, social). */
  links: ContactLink[];
  /** Where they're based, when documented. */
  place?: string;
  /** The real citation — where this contact is documented. */
  source: string;
  tags: string[];
  /** A linked GitHub tracking issue, when one exists. */
  issue?: number;
}

/** Presentation vocab per kind: the directory label + a CSS modifier key. `petitioner` and
 *  `organizer` are the community-side contacts a reader connects with; the rest are the bodies
 *  the record names. */
export const KIND_META: Record<ContactKind, { label: string; mod: string }> = {
  petitioner: { label: "Petitioner", mod: "petitioner" },
  organizer: { label: "Organizer", mod: "organizer" },
  official: { label: "Official body", mod: "official" },
  group: { label: "Community group", mod: "group" },
  outlet: { label: "Outlet", mod: "outlet" },
};

/** The directory filters, in order (All first). Only kinds actually present are rendered by the
 *  page, so this is the full ordered vocabulary, not a fixed toolbar. */
export const CONTACT_FILTERS: { key: "all" | ContactKind; label: string }[] = [
  { key: "all", label: "All" },
  { key: "petitioner", label: "Petitioners" },
  { key: "organizer", label: "Organizers" },
  { key: "official", label: "Officials" },
  { key: "group", label: "Groups" },
  { key: "outlet", label: "Outlets" },
];

/** Count of contacts in a filter bucket (`all` = every contact). */
export function contactCount(contacts: Contact[], key: "all" | ContactKind): number {
  return key === "all" ? contacts.length : contacts.filter((c) => c.kind === key).length;
}
