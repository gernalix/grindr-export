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

    def assert_visible_dates(self, exported_at, events, expected_datetimes):
        with tempfile.TemporaryDirectory() as td:
            export_dir = self.make_archive(td)
            payload = json.loads((export_dir / "raw" / "dom_snapshots.json").read_text())
            children = []
            for label, body, time in reversed(events):
                children.extend([child(f"{body} {time}" if time else body, 450), child(label)])
            children.append(child("Start of Grindr Web chat history"))
            payload["exportedAt"] = exported_at
            payload["snapshots"][0].update(children=children, childCount=len(children))
            before = json.dumps(payload, sort_keys=True)
            _, _, rows, _, _ = archive.extract_messages(payload, export_dir)
            self.assertEqual([row["text"] for row in rows], [event[1] for event in events])
            self.assertEqual([row["date_label"] for row in rows], [event[0] for event in events])
            self.assertEqual([row["datetime"] for row in rows], expected_datetimes)
            self.assertEqual(json.dumps(payload, sort_keys=True), before)

    def test_infers_year_rollover_from_newest_to_oldest_without_reordering_messages(self):
        self.assert_visible_dates("2026-10-16T12:00:00Z", [
            ("7 Oct", "Older", "6:52 PM"),
            ("18 Oct", "Middle", "11:38 PM"),
            ("12 Oct", "Newest", "3:02 PM"),
        ], ["2025-10-07T18:52:00", "2025-10-18T23:38:00", "2026-10-12T15:02:00"])

    def test_untimed_date_group_still_constrains_older_years(self):
        self.assert_visible_dates("2026-10-16T12:00:00Z", [
            ("7 Oct", "Older", "6:52 PM"),
            ("18 Oct", "Untimed", None),
            ("12 Oct", "Newest", "3:02 PM"),
        ], ["2025-10-07T18:52:00", None, "2026-10-12T15:02:00"])

    def test_year_inference_preserves_leap_day_and_export_relative_labels(self):
        self.assert_visible_dates("2025-03-02T12:00:00Z", [
            ("29 Feb", "Leap day", "2:00 PM"),
            ("Yesterday", "Recent", "3:00 PM"),
            ("Today", "Current", "4:00 PM"),
        ], ["2024-02-29T14:00:00", "2025-03-01T15:00:00", "2025-03-02T16:00:00"])

    def test_date_shaped_bubble_is_a_message_and_keeps_surrounding_date(self):
        for body in ["Today", "Yesterday", "22 May"]:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as td:
                export_dir = self.make_archive(td)
                payload = json.loads((export_dir / "raw" / "dom_snapshots.json").read_text())
                children = [child("After 2:10 PM", 450), child(body, 0),
                            child("Before 2:00 PM", 450), child("22 May"),
                            child("Start of Grindr Web chat history")]
                payload["snapshots"][0].update(children=children, childCount=len(children))
                _, _, rows, _, _ = archive.extract_messages(payload, export_dir)
                self.assertEqual([r["text"] for r in rows], ["Before", body, "After"])
                self.assertEqual([r["date_label"] for r in rows], ["22 May"] * 3)
                self.assertEqual(rows[1]["side"], "other")
                self.assertEqual(rows[2]["datetime"], "2026-05-22T14:10:00")

    def test_history_start_marker_passes(self):
        snapshot = {"startMarkerPresent": True}
        self.assertTrue(archive.history_start_verified({"snapshots": [snapshot]}, snapshot))

    def test_reverse_scroll_stability_without_marker_fails(self):
        snapshot = {"startMarkerPresent": False}
        data = {
            "snapshots": [snapshot],
            "oldestBoundaryReached": True,
            "oldestBoundaryEvidence": {
                "method": "reverse-scroll-stable",
                "repeatedAttempts": 2,
                "scrollTop": -3625.6,
                "scrollHeight": 4254,
                "scrollTopStable": True,
                "scrollHeightStable": True,
            },
        }
        self.assertFalse(archive.history_start_verified(data, snapshot))

    def test_missing_marker_and_unverified_boundary_fails(self):
        snapshot = {"startMarkerPresent": False}
        data = {"snapshots": [snapshot], "oldestBoundaryReached": True}
        self.assertFalse(archive.history_start_verified(data, snapshot))

    def test_65_child_capture_is_preserved_without_promoting_scroll_stability(self):
        with tempfile.TemporaryDirectory() as td:
            export_dir = self.make_archive(td)
            raw = export_dir / "raw" / "dom_snapshots.json"
            data = json.loads(raw.read_text(encoding="utf-8"))
            snapshot = data["snapshots"][0]
            snapshot.update(
                startMarkerPresent=False,
                childCount=65,
                children=[child(f"Fixture {n} 2:05 PM", 0) for n in range(65)],
                oldestBoundaryReached=True,
                oldestBoundaryEvidence={"method": "reverse-scroll-stable"},
            )
            raw.write_text(json.dumps(data), encoding="utf-8")
            before = raw.read_bytes()
            _, chosen, rows, _, _ = archive.extract_messages(data, export_dir)
            self.assertEqual(len(chosen["children"]), 65)
            self.assertEqual(len(rows), 65)
            self.assertFalse(archive.history_start_verified(data, chosen))
            self.assertEqual(raw.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
