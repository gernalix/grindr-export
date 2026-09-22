# Grindr Web Chat Export Mini-Prompt

Open Grindr Web in the already-authenticated Google Chrome window, select the target conversation, and reach the oldest available point/start marker if it is not already loaded. Do not log out, clear cookies, close the authenticated window, send messages, change Grindr settings, or bypass media protections.

Use Codex Desktop Chrome control on the existing Grindr tab. Acquire the chat with DOM/Playwright from `[data-testid="chat-container"]`. Capture the oldest/start-marker state first, then scroll progressively toward the newest/end position while saving incremental DOM snapshots to:

`/home/daniele/Documents/ChatGPT/Pixel 8a/grindr_archive/<chat_name>_<YYYYMMDDTHHMMSSZ>/raw/dom_snapshots.json`

Each snapshot must preserve, for every visible chat child, the text/innerText, outer rectangle, bubble rectangle and text when present, images/videos with redacted URL paths, role/aria metadata, and `startMarkerPresent`. Preserve the page URL/title and `exportedAt`. Do not store cookies, auth headers, tokens, session secrets, or signed URL query strings.

Use `pageAssets` only for browser-observed image/video assets that can be bundled normally. If an asset or private album cannot be exported normally, record it as non-exportable and continue; do not bypass Grindr protections.

After acquisition, run:

```bash
python3 /home/daniele/projects/grindr-export/grindr_dom_archive.py \
  "/home/daniele/Documents/ChatGPT/Pixel 8a/grindr_archive/<chat_name>_<YYYYMMDDTHHMMSSZ>"
```

Validate `raw/acquisition_summary.json`, `archive.sqlite`, `messages.json`, `messages.csv`, `README.md`, and `index.html`. `PASS` requires every validation check to pass and no non-exportable media. `PASS WITH WARNINGS` is allowed only when validation checks pass but media/album items could not be exported normally. Any failed integrity/validation check is `FAIL`.
