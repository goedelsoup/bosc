# `tests/fixtures/site/records-baseline.json`

The 137 committed extractions `watermark.site.records._classify` published **before** #1993,
pinned as `rel -> group`.

A classifier addition may only **add** records. A diff to an existing row is a **bug until proven
otherwise** — every fatal defect #1993's triage produced was of exactly that shape: a bare `meta`
whole-document entry (77 files carry a top-level `meta:`) stealing both Fort Wayne IDEM permits and
the OPC summary out of their groups; a `project` entry stealing `idem/fort-wayne/wqc001454.idem.yaml`;
a bare `notice` entry reclassifying an NPDES permit that also carries its public-notice dates.

If a row genuinely must move, regenerate this file **deliberately** and say why in the commit
message:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from watermark.site.records import load_records
rows = {r.rel: r.group for r in load_records(Path("data/extracted"))}
p = Path("tests/fixtures/site/records-baseline.json")
p.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")
PY
```

Regenerating it to make `test_no_committed_extraction_changes_group` pass is how a silent
reclassification ships. Read the diff first.
