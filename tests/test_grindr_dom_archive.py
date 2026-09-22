import importlib.util
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "grindr_dom_archive.py"
SPEC = importlib.util.spec_from_file_location("grindr_dom_archive", MODULE_PATH)
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


def child(text, bubble_x=None):
    bubble = None
    if bubble_x is not None:
        bubble = {
            "className": "bubble",
            "role": None,
            "aria": None,
            "text": text,
            "rect": {"x": bubble_x, "y": 0, "width": 100, "height": 30},
        }
    return {
        "className": "message",
        "tag": "DIV",
        "role": None,
        "aria": None,
        "text": text,
        "innerText": text,
        "rect": {"x": 0, "y": 0, "width": 600, "height": 40},
        "bubble": bubble,
        "images": [],
        "videos": [],
        "links": [],
    }


class GrindrArchiveTests(unittest.TestCase):
    def make_archive(self, root):
        export_dir = Path(root) / "test_chat_20260704T120000Z"
        raw_dir = export_dir / "raw"
        raw_dir.mkdir(parents=True)
        children = [
            child("Same 2:06 PM", 450),
            child("Same 2:06 PM", 450),
            child("Hello </script><script>alert(1)</script> 2:05 PM", 0),
            child("3 Jul"),
            child("Start of Grindr Web chat history"),
        ]
        payload = {
            "exportedAt": "2026-07-04T12:00:00Z",
            "snapshots": [{
                "snapIndex": 0,
                "scrollTop": 0,
                "scrollHeight": 1000,
                "clientHeight": 500,
                "childCount": len(children),
                "children": children,
                "startMarkerPresent": True,
                "url": "https://web.grindr.com/chat",
                "title": "Grindr Web",
                "header": [],
            }],
        }
        (raw_dir / "dom_snapshots.json").write_text(json.dumps(payload), encoding="utf-8")
        return export_dir

    def test_preserves_legitimate_duplicate_messages_and_writes_consistent_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            export_dir = self.make_archive(td)
            data = json.loads((export_dir / "raw" / "dom_snapshots.json").read_text(encoding="utf-8"))
            exported_at, snapshot, rows, media, missing = archive.extract_messages(data, export_dir)

            self.assertEqual([row["text"] for row in rows], [
                "Hello </script><script>alert(1)</script>",
                "Same",
                "Same",
            ])
            self.assertEqual(len({row["id"] for row in rows}), 3)

            metadata = {
                "source": "test",
                "chat_name": "test chat",
                "source_url": snapshot["url"],
                "exported_at": exported_at,
                "archive_dir": str(export_dir),
                "start_marker_present": True,
                "messages": len(rows),
                "images_saved": 0,
                "image_references": 0,
                "videos_saved": 0,
                "albums": 0,
            }
            archive.write_sqlite(export_dir / "archive.sqlite", metadata, rows, media, missing)
            archive.write_viewer(export_dir / "index.html", metadata, rows, {}, missing)

            db = sqlite3.connect(export_dir / "archive.sqlite")
            try:
                self.assertEqual(db.execute("SELECT count(*) FROM messages").fetchone()[0], 3)
            finally:
                db.close()

    def test_viewer_embeds_valid_json_without_script_breakout(self):
        with tempfile.TemporaryDirectory() as td:
            export_dir = self.make_archive(td)
            data = json.loads((export_dir / "raw" / "dom_snapshots.json").read_text(encoding="utf-8"))
            exported_at, snapshot, rows, media, missing = archive.extract_messages(data, export_dir)
            metadata = {
                "source": "test",
                "chat_name": "test chat",
                "source_url": snapshot["url"],
                "exported_at": exported_at,
                "archive_dir": str(export_dir),
                "start_marker_present": True,
                "messages": len(rows),
                "images_saved": 0,
                "image_references": 0,
                "videos_saved": 0,
                "albums": 0,
            }
            archive.write_viewer(export_dir / "index.html", metadata, rows, {}, missing)
            html = (export_dir / "index.html").read_text(encoding="utf-8")
            match = re.search(
                r'<script id="data" type="application/json">(.*?)</script>',
                html,
                re.S,
            )
            self.assertIsNotNone(match)
            embedded = match.group(1)
            decoded = json.loads(embedded)
            self.assertEqual(len(decoded["messages"]), 3)
            self.assertNotIn("</script>", embedded.lower())

    def test_empty_snapshot_list_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "at least one snapshot"):
            archive.choose_snapshot({"snapshots": []})


if __name__ == "__main__":
    unittest.main()
