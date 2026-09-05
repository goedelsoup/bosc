# meetings-text

**Derived text sidecars — not source evidence.**

Plain-text transcriptions of the legacy binary documents (`.doc` / `.dot` / `.xls` / `.rtf`) in
the sibling [`meetings/`](../meetings/), which have no in-process text reader and were
therefore unsearchable. This tree mirrors that one file-for-file: a source `X.DOC` has its text
at the same relative path here, named `X.DOC.txt`.

The sidecars exist so the production is retrievable ([#1757]). They are **regenerable**:

```sh
watermark text-sidecars lima/meetings          # rewrite this tree
watermark text-sidecars lima/meetings --check  # verify it still matches the source bytes
```

`text-sidecars.yaml` records, per source file, its sha256, the converter that read it, and the character
count — or an explicit note where the conversion produced no text. Because the manifest pins the
source hash, a sidecar cannot quietly outlive the bytes it claims to transcribe.

Rules:

- **Never hand-edit a sidecar.** The next run reverts it. A reviewed, cited correction belongs in
  `data/extracted/`, not here.
- **Cite the source, never the sidecar.** The `.DOC` is the record; this is a reading aid.
- The transcription is mechanical and unreviewed. Tables, headers, and footers may be flattened
  or reordered; verify against the source before quoting.
