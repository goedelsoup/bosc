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
import DefaultChapterSection from "./chapters/DefaultChapterSection.astro";
import Discharge from "./chapters/Discharge.astro";
import Groundwater from "./chapters/Groundwater.astro";
import Heat from "./chapters/Heat.astro";
import Stormwater from "./chapters/Stormwater.astro";
import WaterSupply from "./chapters/WaterSupply.astro";

/** Bespoke sections by chapter id — landing chapter by chapter (Environment I–II so far). */
export const CHAPTER_SECTIONS: Record<string, typeof DefaultChapterSection> = {
  "water-supply": WaterSupply,
  discharge: Discharge,
  heat: Heat,
  groundwater: Groundwater,
  stormwater: Stormwater,
  air: Air,
};

/** The section for a chapter id — the bespoke one when registered, the default otherwise. */
export function chapterSection(id: string): typeof DefaultChapterSection {
  return CHAPTER_SECTIONS[id] ?? DefaultChapterSection;
}
