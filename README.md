# grindr-export

Small, local-first tooling for archiving a Grindr Web conversation that is already open in an authenticated Chrome session.

The repository deliberately separates two phases:

1. **Acquisition** — Codex Desktop controls the existing Grindr Web tab, reads `[data-testid="chat-container"]`, scrolls through the conversation, and writes `raw/dom_snapshots.json`. See `GRINDR_EXPORT_MINIPROMPT.md`.
2. **Normalization** — `grindr_dom_archive.py` converts those raw snapshots into a searchable offline viewer plus JSON, CSV, and SQLite.

It does **not** store cookies, login tokens, session secrets, or signed asset query strings. Media download is best-effort and only uses assets normally exposed by the browser. Private albums or protected/unavailable media remain recorded as non-exportable.

Some current Grindr Web chats omit the textual history-start marker. Acquisition remains fail-closed: unchanged reverse-scroll position or height may be retained as diagnostic evidence, but cannot establish the oldest history boundary or a passing export. A complete export requires the actual terminal history-start marker in the Grindr UI.

That marker applies to the Web client's history, not proof of the Android
conversation's absolute beginning. Pixel chat selection, the supported manual
fallback and the separate Android history gate are documented in
[PIXEL_CHAT_VERIFICATION.md](PIXEL_CHAT_VERIFICATION.md).

## Requirements

- Fedora/Linux with Python 3 available globally.
- Google Chrome with an already-authenticated Grindr Web session.
- Codex Desktop browser control for the acquisition phase.
- No virtual environment is required or used.

Canonical local checkout for this environment:

```bash
/home/daniele/projects/grindr-export
```

## Quick start

Open the target conversation in Grindr Web and ensure the oldest available point can be reached. In Codex Desktop, use the instructions from `GRINDR_EXPORT_MINIPROMPT.md`. The acquisition phase should create:

```text
/home/daniele/Documents/ChatGPT/Pixel 8a/grindr_archive/<chat_name>_<timestamp>/
└── raw/
    └── dom_snapshots.json
```

Then normalize it:

```bash
python3 /home/daniele/projects/grindr-export/grindr_dom_archive.py \
  "/home/daniele/Documents/ChatGPT/Pixel 8a/grindr_archive/<chat_name>_<timestamp>"
```

A successful run produces:

- `index.html` — offline full-text viewer;
- `archive.sqlite` — canonical SQLite archive;
- `messages.json` — structured messages;
- `messages.csv` — flat message list;
- `README.md` — per-export summary;
- `raw/acquisition_summary.json` — validation result and warnings.
- `raw/export_manifest.json` — last-write receipt of source and output SHA256s.

## Normally obtained media and readback

The acquisition tool may save a rendered chat image/video using its supported
`downloadMedia` method or bundle narrowly selected observed `pageAssets`. It must
not recover expired assets through browser caches, private APIs or authentication
bypasses. Ingest the returned file without recompression or conversion:

```bash
python3 grindr_media.py ARCHIVE_DIR --source-file BROWSER_RETURNED_FILE \
  --url-redacted OBSERVED_URL_WITHOUT_QUERY_OR_FRAGMENT \
  --kind image --provider browser-download
python3 grindr_media.py ARCHIVE_DIR --verify
python3 grindr_dom_archive.py ARCHIVE_DIR
python3 grindr_dom_archive.py ARCHIVE_DIR --verify
```

The ingest verifies source magic type, exact copied byte count and SHA256, binds
the manifest to the immutable acquisition hash, deduplicates storage by content
hash and preserves individual message associations. Magic recognition is not a
full codec/decode validator. Identical retries are no-ops; changed source bytes,
corruption and cross-acquisition media fail closed. A failure after object copy
but before manifest commit can resume using the same acquired file. Never mutate
a historical raw acquisition to attach another conversation; use a fresh folder.

Saved files are the unchanged **browser-served representation**, not proof of
the sender's original upload or full resolution. Unavailable media remains
explicitly missing. Local message IDs are synthetic, not native Grindr IDs.

Snapshots are reconciled in acquisition order through unambiguous overlaps, not
by choosing the largest page or globally deduplicating repeated message text.
Gaps and ambiguous repeated-event overlaps fail instead of silently losing data.
New captures use `acquisitionSchemaVersion: 2`, `acquisitionComplete: true` and
`completionEvidence.newestReached: true` only after reaching both real bounds.

Normalization preserves a prior SQLite file if its replacement fails. The output
set is not a multi-file transaction: the last-write export receipt detects an
interrupted or changed generation. `--verify` checks current source, manifest,
output and media bytes; rerun normalization from the preserved capture to recover.
The static viewer wiring check does not prove live browser search or rendering.
An overall Pn remains PARTIAL when required media or live acceptance is missing,
even if this one archive reports `PASS WITH WARNINGS`.

Open the viewer with:

```bash
xdg-open "/home/daniele/Documents/ChatGPT/Pixel 8a/grindr_archive/<chat_name>_<timestamp>/index.html"
```

Interpret the final status as follows:

- `PASS`: archive checks passed and no media remained non-exportable.
- `PASS WITH WARNINGS`: message/archive checks passed, but some normally unavailable media or album UI could not be saved.
- `FAIL`: at least one integrity/validation check failed.

## Tests

Run the focused stdlib test suite:

```bash
python3 -m unittest discover -s tests -v
```

## Limits

This workflow depends on Grindr Web's current DOM structure and on Codex Desktop being able to control the already-open Chrome tab. A Grindr UI change can require updating the acquisition selectors or sender inference. Reply previews can be present inside the visible bubble text because the raw DOM snapshot does not currently expose a separate canonical reply-message identifier.

Do not commit exported conversations or media to this repository. `.gitignore` excludes common archive outputs for that reason.
