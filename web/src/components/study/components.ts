/**
 * The MDX `components` map for a per-site study note (`<Content components={STUDY_COMPONENTS} />`)
 * — the walk's curated vocabulary plus the study's own gap panel, so a note can name an ask
 * in the same grammar the chapter does. Islands stay direct imports, as in walk chapters.
 *
 * Deliberately its OWN module, not part of `./index.ts`: that barrel builds `CHAPTER_SECTIONS`
 * and therefore imports all 11 bespoke chapter components. Astro emits a page's CSS from its
 * module graph, so importing the map through the barrel would ship `.air-table`, `.heat-stats`,
 * `.pow-table` … to the study COVER, which renders none of them. The barrel re-exports this
 * for callers that want both.
 */
import { STORY_COMPONENTS } from "../story";
import StudyGap from "./StudyGap.astro";

export const STUDY_COMPONENTS = { ...STORY_COMPONENTS, StudyGap };
