/**
 * The controlled relation-class vocabulary — how each entity relates to Project
 * BOSC (the data-center project), the dimension the legacy entity graph coloured
 * and grouped by (`bosc.site.graph.py` `_RELATION_CLASS_*`, synced with
 * `bosc.pipeline.entities.RELATION_CLASS_ORDER`). Single source of truth for the
 * graph page's legend + grouping and the deck.gl node fill, so the viz and the
 * legend agree. Client-safe (no `node:` imports).
 */
import { hexToRgb } from "./geoStyle";

export interface RelationClass {
  key: string;
  label: string;
  def: string;
  /** Muted fill, matching the legacy Mermaid `classDef` palette. */
  fill: string;
}

/** Canonical display order (matches `RELATION_CLASS_ORDER`). */
export const RELATION_CLASSES: RelationClass[] = [
  {
    key: "bosc_relation",
    label: "Project BOSC",
    def: "Project BOSC itself — its developer + campus entities.",
    fill: "#cde4ff",
  },
  {
    key: "direct_approval",
    label: "Direct approval",
    def: "A body that voted for / permitted the project.",
    fill: "#d7f0d0",
  },
  {
    key: "direct_manage",
    label: "Direct management",
    def: "Builds, operates, or finances the campus, its utilities, or the deal vehicle.",
    fill: "#fff2c9",
  },
  {
    key: "direct_beneficiary",
    label: "Direct beneficiary",
    def: "Named recipient of the public benefit (abatement, captured revenue).",
    fill: "#ffe0c2",
  },
  {
    key: "possible_end_user",
    label: "End user",
    def: "The data-center customer the campus serves (confidence stated in the basis).",
    fill: "#e6d6ff",
  },
  {
    key: "environmental_beneficiary",
    label: "Environmental beneficiary",
    def: "A receiving water / body bearing the project's externality.",
    fill: "#c9eee7",
  },
  {
    key: "govt_relation",
    label: "Government relation",
    def: "A known tie to another government entity.",
    fill: "#eaeaea",
  },
];

export const RELATION_CLASS_BY_KEY = new Map(RELATION_CLASSES.map((c) => [c.key, c]));

/** Display label for a relation-class key, or an em dash when unclassified. */
export function relationClassLabel(key: string | null | undefined): string {
  return key ? (RELATION_CLASS_BY_KEY.get(key)?.label ?? key) : "—";
}

/** Fill as deck.gl RGB; a neutral grey for unclassified / unknown keys. */
export function relationClassRgb(key: string | null | undefined): [number, number, number] {
  const fill = key ? RELATION_CLASS_BY_KEY.get(key)?.fill : undefined;
  return fill ? hexToRgb(fill) : [205, 207, 214];
}
