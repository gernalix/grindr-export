# grindr-export

Read `project-capsule.yaml` and README.md for module, data and command boundaries.
Use global Python, an isolated task worktree and the installed Git single writer.

grindr_snapshots.py reconciles snapshot overlap. grindr_media.py owns local media ingestion, magic/hash validation, manifests and safe associations. grindr_dom_archive.py orchestrates extraction and staged SQLite/JSON/CSV/viewer publication. Browser/Pixel acquisition is a separate, explicitly authorized phase.

- No cookies, tokens, signed media query strings, private chat bodies or real archive data in Git/output.
- Preserve raw acquisition and non-exportable records; do not bypass protected/expired assets.
- Keep Web and Android history gates separate and verify exact media hashes/associations.
- Never open a Grindr tab, Pixel UI, private APIs, caches or live archive for capsule verification.
- The actual UI terminal history-start marker is required for a complete Web export; unchanged scroll geometry alone is insufficient.

Run the declared isolated fixture test commands for verification. Bubblewrap
keeps host home, credentials, runtime sockets, devices and external data outside
the test environment. Do not replace this with a live smoke, installer or data
operation. Preserve all valid work and private originals; source integration
does not prove runtime deployment or application-data completeness.
