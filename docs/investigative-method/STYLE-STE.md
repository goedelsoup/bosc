# STYLE-STE — the impact study's writing register

This document fixes the writing register for the **impact study**: the per-site chapter
notes under `web/src/content/study/<site>/*.mdx` and the site-generic lead paragraphs
inside `web/src/components/study/chapters/*.astro`.

It is a **house adaptation of ASD-STE100** (Simplified Technical English), not the standard
verbatim. The standard's approved-word list is aerospace-maintenance vocabulary; applied
literally it would strip this domain of the words it needs. What this document keeps is the
standard's *mechanism*: a fixed vocabulary, short declarative sentences, one idea per
sentence, and a named actor for every verb.

## Why a separate register

The rest of the platform writes in a documentary register — long sentences, stacked em-dash
asides, a deliberate accumulation of qualification. That register is right for the walk, the
reports, and the long-form under `docs/`, and the
[investigative-writing-and-editorial](../../.claude/skills/investigative-writing-and-editorial/SKILL.md)
skill governs it.

The study is different. It is the artifact a township trustee, a school-board member, or a
resident reads **once**, under time pressure, to decide something. It is also the artifact
most likely to be translated, quoted in a hearing, or read by someone for whom English is a
second language. It therefore trades cadence for comprehension.

This register does **not** relax
[evidentiary-discipline](../../.claude/skills/evidentiary-discipline/SKILL.md). Simpler
sentences make an unsupported claim *more* exposed, not less. Every rule below is subordinate
to the discipline; where they conflict, the discipline wins and the sentence gets longer.

## The rules

| # | Rule | Instead of | Write |
|---|---|---|---|
| 1 | One meaning per word. Fix a term's sense on first use in a chapter and never vary it. | "draw" meaning both withdrawal and demand | pick one; use the glossary term |
| 2 | Sentences of 25 words or fewer. One idea per sentence. | a 60-word sentence with three clauses | three sentences |
| 3 | Active voice, present tense. Name the actor. | "the limit is set at the 7Q10" | "Ohio EPA sets the limit at the 7Q10" |
| 4 | Paragraphs of 6 sentences or fewer. One topic. Topic sentence first. | a paragraph that arrives at its point | the point, then the support |
| 5 | No noun cluster longer than 3 words. | "campus cooling water makeup rate" | "the makeup rate for campus cooling water" |
| 6 | Keep the articles. | "7Q10 is 0.2 cfs" | "the 7Q10 is 0.2 cfs" |
| 7 | At most **one** em-dash aside per paragraph. | three stacked asides | a second sentence |
| 8 | "because" for cause. Never "as" or "since" for cause. | "since the river is low" | "because the river is low" |
| 9 | Numbers as digits. Spell the unit at first use in a chapter, then use the symbol. | "4.9 cfs" cold | "4.9 cubic feet per second (cfs)", then "cfs" |
| 10 | Define a term on first use, then link it **once** to `/wiki/<term>`. | repeated glossary links | one link, first use |

Rule 7 is the real change from the house voice. The current prose stacks em-dash
sub-clauses; that is the single habit this register asks writers to break.

Two carve-outs, so the rules stay checkable rather than merely strict:

- **Rule 2 limits clauses, not list items.** A sentence whose length comes from an
  enumeration — five facility names, four questions — counts as one idea and is exempt.
- **Rule 7 applies per paragraph, not per list.** Each `<li>` in a bulleted list is its own
  paragraph for the purpose of the em-dash count.

## Vocabulary — reconcile, never compete

The wiki glossary is the **one** owner of term definitions. It ships as the `concepts` feed
and renders at `/wiki/`. A study note does not redefine a term the glossary already holds; it
links to it. (No count is quoted here on purpose — the feed grows, and a number in this
sentence would be wrong within a release and guarded by nothing.)

Terms the study leans on that the glossary **already carries**: `7Q10`, `Assimilative
capacity`, `Consumptive cooling`, `Curve number`, `Dilution`, `DMR`, `Effluent`, `HSG`,
`NPDES`, `Once-through cooling`, `Closed-loop cooling`, `PTI`, `PUE`, `POTW`, `Tax
abatement`, `PILOT`, `CRA`, `Enterprise zone`, `Rezoning`, `WUE`, `WWTP`, `OPSB`, `PJM`,
`RSEI`, `TRI`, `SWCD`.

Terms the study needs that the glossary **does not yet carry** — the backlog. Until an entry
exists, a note defines the term inline, in one sentence, and does not link it:

- `1Q10` — the acute design low flow, sharper than the 7Q10
- `blowdown` — the concentrated water a cooling tower discharges to control salts
- `makeup` — the water added to a cooling tower to replace evaporation and blowdown
- `upground reservoir` — an off-stream storage basin filled by pumping, not by a stream
- `drawdown` — the fall in a water level caused by pumping
- `design low flow` — the low-flow statistic a permit writer screens a discharge against
- `headroom` — the distance between a present condition and its regulatory limit
- `cycles of concentration` — how many times a cooling tower reuses its water before blowdown
- `load factor` — average electrical demand divided by peak demand
- `time of concentration` — how long runoff takes to reach a point from the farthest part of a catchment
- `§316(a)` — the Clean Water Act provision for an alternative thermal limit
- `CBI` — confidential business information; a trade-secret withholding

## Localizing — a SITE-NOTE rule only

An impact study is read in one place. A quantity with no local referent does not inform
anyone. But the register covers two surfaces with opposite obligations, and conflating them
is how one site's facts leak onto twenty-five others:

| Surface | Obligation |
|---|---|
| a site note (`web/src/content/study/<site>/*.mdx`) | **Localize.** Every abstract quantity gets a referent from *that site's* own record. |
| a chapter lead (`web/src/components/study/chapters/*.astro`) | **Stay site-neutral.** One site's geography, agency, statute, or instrument must never appear — the paragraph renders on every site in the network. |

So a lead names "a permit writer", never "Ohio EPA"; "the state's numeric temperature
criterion", never "Ohio's". A lead may interpolate a resolved value (`{riverName}`,
`{eb.area_name}`), because that is the site's own data reaching the template — but it may not
hard-code the value.

For a site note, the rules are:

- **Anchor every abstract quantity to a referent on that site's own record.** Lima's densest
  shelf is [`docs/HYDROLOGY.md`](../HYDROLOGY.md): the 5 upground reservoirs, the ~14.4
  billion gallons of storage, the 3.92 MGD makeup as 20.7 % of plant production, the
  960.9 → 761.8-day drought reserve. A peer site has its own shelf and none of these figures.
- **Name local entities only from the record.** For Lima: American and Sugar Creek Townships,
  the Ottawa River, the Auglaize River, the Lima WWTP (NPDES 2PE00000), AEP Ohio, the JSMC.
- **Place history is `[reference]`, never `[verified]`.** Physical geography, drainage, and
  historic waterworks may draw on a committed county history — for Lima, Leeson 1885
  (`data/documents/history/allen-oh/historyallencou00leesgoog_text.pdf`; page index at
  `data/extracted/history/allen-oh/leeson-1885-corpus-intersect.yaml`). Cite the page.

## Do not

- **No household-object analogy** unless the comparison is computed and tagged. "About as
  much as a garden hose" is a fabricated figure wearing a friendly coat.
- **No "could" / "might" causal chain.** A speculative mechanism is an `[open]` question with
  a named record that would settle it, or it is cut.
- **No verdict inflation.** A gap is a gap. Write it as a noun phrase that completes
  "Computing it requires ___", matching the gap grammar the chapter already renders.
- **No re-deriving the screen.** The chapter's section already renders the figures. A note
  says what the screen cannot: the local mechanism, the limit of the method, and the record
  that would close it.

## Where the register applies

| Surface | Register |
|---|---|
| `web/src/content/study/**/*.mdx` | STE |
| the lead paragraph in `web/src/components/study/chapters/*.astro` | STE |
| gap findings and caveats (`study.ts` / `impact_study.py`) | **unchanged** — parity-pinned in both languages |
| the walk (`web/src/content/stories/**`), `docs/**`, the reports | the documentary register |

## Checking a draft

There is no gate. Read the draft against this list:

1. Any sentence over 25 words?
2. Any paragraph with more than one em-dash aside?
3. Any passive verb whose actor is unnamed?
4. Any noun cluster over 3 words?
5. Any term used in two senses?
6. Any quantity with no local referent?
7. Any claim whose tag the record does not support?
