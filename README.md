# grindr-export

Small, local-first tooling for archiving a Grindr Web conversation that is already open in an authenticated Chrome session.

The repository deliberately separates two phases:

1. **Acquisition** — Codex Desktop controls the existing Grindr Web tab, reads `[data-testid="chat-container"]`, scrolls through the conversation, and writes `raw/dom_snapshots.json`. See `GRINDR_EXPORT_MINIPROMPT.md`.
2. **Normalization** — `grindr_dom_archive.py` converts those raw snapshots into a searchable offline viewer plus JSON, CSV, and SQLite.

It does **not** store cookies, login tokens, session secrets, or signed asset query strings. Media download is best-effort and only uses assets normally exposed by the browser. Private albums or protected/unavailable media remain recorded as non-exportable.

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
