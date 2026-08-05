# van-wert/operator/ — QTS's own public disclosures for the Van Wert campus

Captured web evidence published by the **operator**, not by a public body. Everything here is
`[reference]` as to its content and `[verified]` only as to *what the operator says and when it
said it* — which is the point: several claims about this campus exist nowhere but on the
operator's own page, and one of them ("The City of Van Wert has approved our water usage") asserts
an act by a public body that the public body's own record does not contain.

Ingested for **#1407** (sub-issue of #1267).

## Why a capture and not a citation

#1401 learned this the expensive way. The city-launched microsite `vanwertohiodatacenter.com` was
a client-rendered Next.js application; the Internet Archive holds only its shell ("Loading
topics…"), so its FAQ prose — including a 5,500-gallon fill figure a hearing commenter quoted from
it — is **permanently unrecoverable**. The domain now 301-redirects here.

`q.com/data-centers/van-wert/` is a WordPress page and is **server-rendered**, so a plain HTTP GET
preserves the full text. It was captured as raw response bytes (`.html` files under
`data/documents/**` are `-text` in `.gitattributes` — never normalized).

## Documents

| File | Captured | What it carries |
|---|---|---|
| `2026-08-05-qts-van-wert-project-faq.q-com.html` | 2026-08-05 | The project page and its full FAQ — water, energy, jobs, economy, environment |

## What this capture settles

- **The water claim, still live:** "The City of Van Wert has approved our water usage and we're
  currently in discussions to identify the best solutions to support the initial fill. QTS has no
  intentions of utilizing the aquifer to support the initial fill."
- **A named work product** behind the capacity claim — "The analysis completed by QTS and City
  engineering indicates that there is adequate capacity in the existing system" — which is the
  priority-1 records request on the water thread.
- **The operator states no fill volume:** "The total initial charging volume can vary widely …
  it's hard to predict the exact amount of water needed." Every gallon figure in the corpus's
  fill-vs-annual dispute is therefore a **City** figure or a citizen quoting the dead microsite,
  not a QTS disclosure.
- **The cooling medium, in conflict with the City's own description:** "The closed-loop system
  that cools the data hall uses **only water**", against the Safety-Service Director's sealed
  "water and glycol" loop (2026-04-21 press release, in the hearing record).
- **No megawatt figure**, restated: "we don't disclose specific power capacity for security and
  confidentiality reasons."
- **No "$200 million over 20 years"** — the page says only "millions in local tax revenue
  annually".

## One defect worth recording

The economy answer says the project will "support services and community programs throughout
**Richmond County**." Richmond County is Augusta, Georgia — a different QTS market. This is
boilerplate left in an operator disclosure page for Van Wert County, Ohio, and it is the same
species of defect as the issued Ohio EPA permit that names the "Defiance Van Wert WWTP" (#1406).
Recorded because it bears on how much diligence the page evidences, not because it changes a
figure.

The page also still advertises a **past** event ("Van Wert Community Event, June 11, 5:00-6:30
p.m., Vantage Career Center") as upcoming — the same event Council announced on 2026-06-08.

Extraction: [`data/extracted/van-wert/incentive-water-instruments.yaml`](../../../extracted/van-wert/incentive-water-instruments.yaml),
digest [`incentive-water-instruments.md`](../../../extracted/van-wert/incentive-water-instruments.md).
SHA-256 and the exact request in [`filename-map.yaml`](filename-map.yaml).
