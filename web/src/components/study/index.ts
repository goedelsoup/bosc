/**
 * The study's chapter render registry (the missing-impact-study epic) — chapter id → the
 * bespoke Astro section that renders its full screen. A chapter with no entry renders
 * `DefaultChapterSection` (the model's stats + caveats), so every chapter ships from day
 * one and bespoke sections land incrementally without touching the shell.
 *
 * The data spine lives in `@watermark/core/study`; sections receive `{ def, model, slug }`
 * and compose the shared palette (charts, FigureStat, EvidenceTag, islands) exactly the way
 * the existing environment/economy pages do.
 */
import Air from "./chapters/Air.astro";
import Balance from "./chapters/Balance.astro";
import DefaultChapterSection from "./chapters/DefaultChapterSection.astro";
import Discharge from "./chapters/Discharge.astro";
import Fiscal from "./chapters/Fiscal.astro";
import Groundwater from "./chapters/Groundwater.astro";
import Heat from "./chapters/Heat.astro";
import Labor from "./chapters/Labor.astro";
import Missing from "./chapters/Missing.astro";
import Power from "./chapters/Power.astro";
import Stormwater from "./chapters/Stormwater.astro";
import WaterSupply from "./chapters/WaterSupply.astro";

/** Bespoke sections by chapter id — every screened chapter + the annex. Four ride the generic
 *  renderer: the two front-matter chapters (method / project) and the two corpus-keyed ones
 *  (assembly / governance, #1969), whose screen is a record count plus the site's authored note —
 *  a bespoke conveyance-chain / roll-call section is the natural follow-up, not a blocker. */
export const CHAPTER_SECTIONS: Record<string, typeof DefaultChapterSection> = {
  "water-supply": WaterSupply,
  discharge: Discharge,
  heat: Heat,
  groundwater: Groundwater,
  stormwater: Stormwater,
  air: Air,
  labor: Labor,
  power: Power,
  fiscal: Fiscal,
  balance: Balance,
  missing: Missing,
};

/** The section for a chapter id — the bespoke one when registered, the default otherwise. */
export function chapterSection(id: string): typeof DefaultChapterSection {
  return CHAPTER_SECTIONS[id] ?? DefaultChapterSection;
}

/** Re-exported for callers that already pull the chapter registry from this barrel. A page
 *  that needs ONLY the MDX map (the cover) must import `./components` directly — importing it
 *  from here drags every chapter component's CSS onto that page. */
export { STUDY_COMPONENTS } from "./components";
