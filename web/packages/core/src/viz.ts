/** Shared data shapes for the elevated visual components (FigureStat, Timeline). */
import type { TagKind } from "./teardown";

/** One figure/stat (design "Figure Stat"). grounded → verified, modeled → inference. */
export interface FigureStatData {
  label: string;
  value: string;
  unit?: string;
  evidence: TagKind;
  basis?: "grounded" | "modeled";
  sub?: string;
  source?: string;
  warn?: boolean;
}

/** One timeline event (design "Timeline"). */
export interface TimelineItem {
  date: string;
  kind: string;
  title: string;
  summary?: string;
  evidence: TagKind;
  seenInCh?: string;
  seenInHref?: string;
  connect?: { kind: string; label: string; href?: string }[];
}
