# P91 — partial acceptance checkpoint

Owner: grindr-export (project 106). P125 centralized-resume steer respected:
no user questions, workers, notifications, physical-device operations, PH/C2/C3
access or lifecycle authority. Existing P90 Pixel manual-boundary confirmation
is retained; the Android criterion is not substituted for the Web marker.

## Verified

- 21 serial stdlib tests: overlap/gap handling, legitimate repeated messages,
  exact bytes, hash/dedup/association, idempotent ingest and normalization,
  interruption recovery, changed-capture/corruption rejection, safe alt text,
  prior SQLite preservation and incomplete-capture failure.
- Authenticated authorized Web conversation: actual history-start marker and
  newest bound, two snapshots, two received-image items correctly associated.
- One normally supported browser download: 59,391 bytes, unchanged SHA256
  `3accaa54d9500f9af3817864fe2ae1b45dc0193ca27d9724dc954e01f2e18aa1`.
  Provenance is browser-served bytes, not sender-upload originality.
- JSON/CSV/SQLite coherence, SQLite integrity/FKs, no active remote viewer
  dependencies, source/output receipt readback and saved-media hash verified.

## Remaining gates

- Second visible JPEG: supported download timed out both in chat and normally
  opened fullscreen view; observed pageAssets inventory did not expose it.
  No private cache or expiry bypass attempted. Result remains 1/2 images.
- Live offline-viewer browser acceptance is blocked by the browser URL policy
  rejecting `file:`. No alternate listener, CDP or other policy workaround.
  Static search wiring is explicitly not live search/render acceptance.
- No account-wide/Android media coverage, native message IDs, videos or private
  albums verified in this run. No universal/full-original promise.
- P91 must not PASS or close issues #2/#3 on these partial results.

## Recovery

The new private acquisition is separate from historical archives:
`P91_web_media_20261013T013534Z` under the existing private archive root.
Keep source, media objects and receipts. `grindr_dom_archive.py ARCHIVE_DIR
--verify` verifies current bytes; identical ingest is a no-op. A newly obtained
normal browser artifact for the missing reference may be ingested into this
unchanged capture, followed by normalization and readback.

Next action: coordinator provides an authorized, normally supported way to
complete the missing media and live viewer acceptance; resume in this chat.
No direct user question or automatic retry cycle is scheduled.
