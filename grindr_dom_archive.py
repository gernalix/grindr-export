#!/usr/bin/env python3
import csv
import hashlib
import html
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
DATE_RE = re.compile(r"^(Today|Yesterday|\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))$")
TIME_RE = re.compile(r"(?:(Delivered)\s+)?(\d{1,2}:\d{2}\s+[AP]M)(?:\s+(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)))?$")


def clean(value):
    return re.sub(r"[ \t\r\f\v]+", " ", (value or "").replace("\u00a0", " ")).strip()


def parse_date(label, exported_at):
    exported_dt = datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
    if exported_dt.tzinfo is not None:
        exported_dt = exported_dt.astimezone()
    base = exported_dt.date()
    if label == "Today":
        return base
    if label == "Yesterday":
        return base - timedelta(days=1)
    day, mon = label.split()
    candidate = base.replace(month=MONTHS[mon], day=int(day))
    if candidate > base:
        candidate = candidate.replace(year=base.year - 1)
    return candidate


def parse_time(text):
    match = TIME_RE.search(text or "")
    if not match:
        return None, None, clean(text)
    time_text = match.group(2)
    date_override = match.group(3)
    message_text = clean((text or "")[: match.start()])
    return time_text, date_override, message_text


def is_twemoji(image):
    return "twemoji" in (image.get("className") or "")


def redacted_hash(url):
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest() if url else None


def message_id(parts):
    return hashlib.sha256("\x1f".join("" if p is None else str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def choose_snapshot(data):
    snapshots = data.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise ValueError("raw/dom_snapshots.json must contain at least one snapshot")
    with_marker = [s for s in snapshots if s.get("startMarkerPresent")]
    pool = with_marker or snapshots
    return max(pool, key=lambda s: s.get("childCount", 0))


def load_media_map(archive_dir):
    path = archive_dir / "raw" / "media_copy_summary.json"
    if not path.exists():
        return {}
    summary = json.loads(path.read_text())
    return {item["urlRedacted"]: item for item in summary.get("copied", [])}


def extract_messages(data, archive_dir):
    snapshot = choose_snapshot(data)
    exported_at = data.get("exportedAt") or data.get("exported_at") or datetime.utcnow().isoformat() + "Z"
    media_map = load_media_map(archive_dir)
    current_date = None
    rows = []
    media = []
    non_exportable = []

    for child in reversed(snapshot["children"]):
        text = clean(child.get("text") or child.get("innerText"))
        if not text:
            continue
        if text == "Start of Grindr Web chat history":
            continue
        if DATE_RE.match(text):
            current_date = text
            continue

        bubble = child.get("bubble")
        useful_images = [
            im for im in child.get("images", [])
            if not is_twemoji(im) and (im.get("src") or im.get("alt") or im.get("rawSrcPresent"))
        ]
        useful_videos = [v for v in child.get("videos", []) if v.get("src") or v.get("rawSrcPresent")]
        is_album = (bubble or {}).get("aria") == "Private Album" or text == "Private Album"
        is_map = "Mapbox" in text or text == "Map"

        if bubble:
            bubble_rect = bubble.get("rect") or {}
            outer_rect = child.get("rect") or {}
            midpoint = (outer_rect.get("x", 0) + outer_rect.get("width", 0) / 2)
            side = "me" if bubble_rect.get("x", 0) > midpoint else "other"
            raw_text = clean(bubble.get("text") or text)
        elif useful_images and "sent by you" in text:
            side = "me"
            raw_text = clean(text)
        else:
            side = "system"
            raw_text = clean(text)

        time_text, date_override, body = parse_time(raw_text)
        date_label = date_override or current_date
        body = body or ("Private Album" if is_album else raw_text)
        if is_map:
            body = "Map/location preview"

        date_value = None
        dt_value = None
        if date_label:
            try:
                date_value = parse_date(date_label, exported_at)
                if time_text:
                    parsed = datetime.strptime(time_text, "%I:%M %p").time()
                    dt_value = datetime.combine(date_value, parsed).isoformat()
            except Exception:
                date_value = None

        seq = len(rows) + 1
        mid = message_id([seq, side, date_label, time_text, body])
        sender = "Me" if side == "me" else ("Other" if side == "other" else "System/visible item")
        rows.append({
            "id": mid,
            "sequence": seq,
            "sender": sender,
            "side": side,
            "date_label": date_label,
            "time_text": time_text,
            "datetime": dt_value,
            "text": body,
            "html_text": html.escape(body).replace("\n", "<br>"),
            "raw_kind": "album" if is_album else ("map" if is_map else ("media" if useful_images or useful_videos else "message")),
        })

        for ordinal, image in enumerate(useful_images, 1):
            src = image.get("src")
            local = media_map.get(src)
            media_id = f"{mid}_m{ordinal}"
            if local:
                media.append({
                    "id": media_id, "message_id": mid, "ordinal": ordinal, "kind": "image",
                    "local_path": local["local_path"], "source_url_redacted": src,
                    "source_url_sha256": redacted_hash(src), "content_type": local.get("contentType"),
                    "bytes": local.get("bytes"), "file_sha256": local.get("sha256"), "alt": image.get("alt"),
                })
            else:
                non_exportable.append({
                    "message_id": mid, "media_id": media_id, "sequence": seq, "type": "image",
                    "reason": "Image was visible/referenced in Grindr Web but could not be saved through normal browser/page asset access.",
                    "source_url_redacted": src,
                })

        for ordinal, video in enumerate(useful_videos, len(useful_images) + 1):
            non_exportable.append({
                "message_id": mid, "media_id": f"{mid}_m{ordinal}", "sequence": seq, "type": "video",
                "reason": "Video was referenced in Grindr Web but no normally exportable browser/page asset file was available.",
                "source_url_redacted": video.get("src"),
            })

        if is_album:
            non_exportable.append({
                "message_id": mid, "media_id": None, "sequence": seq, "type": "album",
                "reason": "Private Album is exposed as a Grindr UI element, not as normally exportable local files.",
                "source_url_redacted": None,
            })

    return exported_at, snapshot, rows, media, non_exportable


def write_sqlite(path, metadata, rows, media, non_exportable):
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript("""
    PRAGMA foreign_keys=ON;
    CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE messages (id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE, sender TEXT, side TEXT, date_label TEXT, time_text TEXT, datetime TEXT, text TEXT, html_text TEXT, raw_kind TEXT);
    CREATE TABLE media (id TEXT PRIMARY KEY, message_id TEXT NOT NULL, ordinal INTEGER NOT NULL, kind TEXT, local_path TEXT, source_url_redacted TEXT, source_url_sha256 TEXT, content_type TEXT, bytes INTEGER, file_sha256 TEXT, alt TEXT, FOREIGN KEY(message_id) REFERENCES messages(id));
    CREATE TABLE non_exportable (id INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT, media_id TEXT, sequence INTEGER, type TEXT, reason TEXT, source_url_redacted TEXT);
    CREATE INDEX idx_messages_datetime ON messages(datetime);
    CREATE INDEX idx_media_message ON media(message_id);
    """)
    db.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", [(k, str(v)) for k, v in metadata.items()])
    db.executemany("INSERT INTO messages VALUES (:id,:sequence,:sender,:side,:date_label,:time_text,:datetime,:text,:html_text,:raw_kind)", rows)
    db.executemany("INSERT INTO media VALUES (:id,:message_id,:ordinal,:kind,:local_path,:source_url_redacted,:source_url_sha256,:content_type,:bytes,:file_sha256,:alt)", media)
    db.executemany("INSERT INTO non_exportable(message_id,media_id,sequence,type,reason,source_url_redacted) VALUES (:message_id,:media_id,:sequence,:type,:reason,:source_url_redacted)", non_exportable)
    db.commit()
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    fk = db.execute("PRAGMA foreign_key_check").fetchall()
    db.close()
    return integrity, fk


def write_viewer(path, metadata, rows, media_by_message, non_exportable):
    payload = json.dumps(
        {"metadata": metadata, "messages": rows, "media": media_by_message, "nonExportable": non_exportable},
        ensure_ascii=False,
    )
    # This script element is raw text: HTML entities such as &quot; are not
    # decoded. Escape only characters that can terminate/confuse the element.
    payload = (
        payload.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    path.write_text(f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Grindr archive - {html.escape(metadata['chat_name'])}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#f6f7f8;color:#171717}}header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px 16px;z-index:2}}h1{{font-size:18px;margin:0 0 8px}}#q{{width:100%;box-sizing:border-box;padding:9px;border:1px solid #bbb;border-radius:6px}}main{{max-width:920px;margin:0 auto;padding:14px}}.msg{{display:flex;margin:7px 0}}.me{{justify-content:flex-end}}.other{{justify-content:flex-start}}.system{{justify-content:center}}.bubble{{max-width:72%;padding:8px 10px;border-radius:8px;background:#fff;border:1px solid #ddd;white-space:pre-wrap;overflow-wrap:anywhere}}.me .bubble{{background:#d8f8d8}}.system .bubble{{background:#eee;color:#555;font-size:13px}}.meta{{font-size:11px;color:#666;margin-top:4px}}img,video{{display:block;max-width:280px;margin-top:6px;border-radius:6px}}.missing{{font-size:12px;color:#8a4b00;margin-top:6px}}mark{{background:#fff19c}}
</style>
<header><h1>{html.escape(metadata['chat_name'])}</h1><input id="q" placeholder="Search full text"></header><main id="chat"></main>
<script id="data" type="application/json">{payload}</script>
<script>
const data=JSON.parse(document.getElementById('data').textContent);const chat=document.getElementById('chat');const q=document.getElementById('q');
function esc(s){{return (s||'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));}}
function render(){{const term=q.value.toLowerCase();chat.innerHTML='';for(const m of data.messages){{const hay=[m.text,m.sender,m.date_label,m.time_text].join(' ').toLowerCase();if(term&&!hay.includes(term))continue;const wrap=document.createElement('div');wrap.className='msg '+m.side;const b=document.createElement('div');b.className='bubble';let text=esc(m.text);if(term)text=text.replace(new RegExp(term.replace(/[.*+?^${{}}()|[\\]\\\\]/g,'\\\\$&'),'ig'),x=>'<mark>'+x+'</mark>');b.innerHTML=text;for(const media of data.media[m.id]||[]){{if(media.kind==='image'&&media.local_path)b.innerHTML+=`<img src="${{esc(media.local_path)}}" alt="${{esc(media.alt||'image')}}">`;if(media.kind==='video'&&media.local_path)b.innerHTML+=`<video src="${{esc(media.local_path)}}" controls></video>`;}}for(const miss of data.nonExportable.filter(x=>x.message_id===m.id))b.innerHTML+=`<div class="missing">${{esc(miss.type)}} not exported: ${{esc(miss.reason)}}</div>`;b.innerHTML+=`<div class="meta">${{esc(m.sender)}} · ${{esc([m.date_label,m.time_text].filter(Boolean).join(' '))}}</div>`;wrap.appendChild(b);chat.appendChild(wrap);}}}}
q.addEventListener('input',render);render();
</script></html>
""", encoding="utf-8")


def main():
    if len(sys.argv) != 2:
        print("usage: grindr_dom_archive.py ARCHIVE_DIR", file=sys.stderr)
        return 2
    archive_dir = Path(sys.argv[1])
    raw_path = archive_dir / "raw" / "dom_snapshots.json"
    if not raw_path.is_file():
        print(f"error: missing {raw_path}", file=sys.stderr)
        return 2
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        exported_at, snapshot, rows, media, non_exportable = extract_messages(data, archive_dir)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"error: invalid acquisition data: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print("error: no messages or visible chat items were extracted", file=sys.stderr)
        return 1
    chat_name = archive_dir.name.rsplit("_", 1)[0].replace("_", " ")
    sender_counts = Counter(row["sender"] for row in rows)
    metadata = {
        "source": "Grindr Web UI via Google Chrome incognito DOM/pageAssets",
        "chat_name": chat_name,
        "source_url": snapshot.get("url"),
        "exported_at": exported_at,
        "archive_dir": str(archive_dir),
        "start_marker_present": bool(snapshot.get("startMarkerPresent")),
        "messages": len(rows),
        "images_saved": sum(1 for m in media if m["kind"] == "image"),
        "image_references": sum(1 for n in non_exportable if n["type"] == "image") + sum(1 for m in media if m["kind"] == "image"),
        "videos_saved": sum(1 for m in media if m["kind"] == "video"),
        "albums": sum(1 for n in non_exportable if n["type"] == "album"),
    }
    (archive_dir / "messages.json").write_text(json.dumps({"metadata": metadata, "messages": rows, "media": media, "nonExportable": non_exportable}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (archive_dir / "messages.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    media_by_message = {}
    for item in media:
        media_by_message.setdefault(item["message_id"], []).append(item)
    integrity, fk = write_sqlite(archive_dir / "archive.sqlite", metadata, rows, media, non_exportable)
    write_viewer(archive_dir / "index.html", metadata, rows, media_by_message, non_exportable)
    (archive_dir / "README.md").write_text(f"""# Grindr chat archive

Chat: {chat_name}
Exported: {exported_at}
Messages: {len(rows)}
Sender counts: {', '.join(f'{k}={v}' for k, v in sender_counts.items())}
Images saved: {metadata['images_saved']}/{metadata['image_references']}
Videos saved: {metadata['videos_saved']}
Albums: {metadata['albums']}

## Files

- index.html: offline searchable chat viewer.
- archive.sqlite: canonical SQLite export.
- messages.json: canonical JSON export.
- messages.csv: flat message list.
- media/images, media/videos, media/albums: local media files when normally accessible.
- raw/: acquisition and validation metadata.

## Limits

Media marked non-exportable was visible or referenced in Grindr Web but could not be saved through normal browser/page asset access. No ephemeral/view-once, anti-capture, login/session, cookie, or API protections were bypassed.
""", encoding="utf-8")
    with (archive_dir / "messages.csv").open(newline="", encoding="utf-8") as fh:
        csv_count = sum(1 for _ in csv.DictReader(fh))
    db = sqlite3.connect(archive_dir / "archive.sqlite")
    sqlite_count = db.execute("SELECT count(*) FROM messages").fetchone()[0]
    db.close()
    viewer_text = (archive_dir / "index.html").read_text(encoding="utf-8")
    visible_datetimes = [r["datetime"] for r in rows if r.get("datetime")]
    required_files = [
        archive_dir / "index.html",
        archive_dir / "archive.sqlite",
        archive_dir / "messages.json",
        archive_dir / "messages.csv",
        archive_dir / "README.md",
    ]
    checks = {
        "start_marker": "PASS" if metadata["start_marker_present"] else "FAIL",
        "duplicate_message_ids": "PASS" if len({r["id"] for r in rows}) == len(rows) else "FAIL",
        "sequence_order": "PASS" if [r["sequence"] for r in rows] == list(range(1, len(rows) + 1)) else "FAIL",
        "date_order_visible_timestamps": "PASS"
        if all(a <= b for a, b in zip(visible_datetimes, visible_datetimes[1:]))
        else "FAIL",
        "sqlite_integrity": integrity,
        "sqlite_foreign_key_check": "PASS" if not fk else "FAIL",
        "json_csv_sqlite_coherence": "PASS" if len(rows) == csv_count == sqlite_count else "FAIL",
        "viewer_search": "PASS" if "addEventListener('input',render)" in viewer_text else "FAIL",
        "no_active_remote_viewer_dependencies": "PASS"
        if not re.search(r"""(?:src|href)=["']https?://""", viewer_text)
        else "FAIL",
        "broken_html_media_links": "PASS"
        if all((archive_dir / m["local_path"]).exists() for m in media if m.get("local_path"))
        else "FAIL",
        "media_nonzero": "PASS"
        if all((archive_dir / m["local_path"]).stat().st_size > 0 for m in media if m.get("local_path"))
        else "FAIL",
        "required_files": "PASS" if all(path.exists() for path in required_files) else "FAIL",
    }
    checks_pass = all(v in ("PASS", "ok") for v in checks.values())
    if not checks_pass:
        status = "FAIL"
    elif non_exportable:
        status = "PASS WITH WARNINGS"
    else:
        status = "PASS"
    summary = {"status": status, "archiveDir": str(archive_dir), "metadata": {**metadata, "sender_counts": dict(sender_counts)}, "nonExportable": non_exportable, "checks": checks}
    (archive_dir / "raw" / "acquisition_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if status in ("PASS", "PASS WITH WARNINGS") else 1


if __name__ == "__main__":
    raise SystemExit(main())