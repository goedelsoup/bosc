/** Shared shape for the Profile Header (design "Profile Header") — one identity
 *  strip for all profile kinds (entity / person / place / concept). */
import type { TagKind } from "./teardown";
import type { FigureStatData } from "./viz";

export interface ProfileAttr {
  label: string;
  value: string;
  tag?: TagKind;
}

export interface ProfileRel {
  kind: string;
  label: string;
  href?: string;
}

export interface ProfileHeaderData {
  kindLabel: string;
  name: string;
  variants?: string[];
  descriptor?: string;
  evidence: TagKind;
  seenIn?: { ch: string; label: string; href: string };
  graphHref?: string;
  /** Figure-stat strip (sm). */
  stats?: FigureStatData[];
  /** Key attributes (dl). */
  attrs?: ProfileAttr[];
  relLabel?: string;
  relationships?: ProfileRel[];
  correctHref?: string;
}
