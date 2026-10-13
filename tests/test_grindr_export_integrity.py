import base64
import copy
import contextlib
import hashlib
import json
import io
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

import grindr_media as media
import grindr_snapshots as snapshots
from test_grindr_dom_archive import archive, child


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7XkAAAAASUVORK5CYII=")
URL = "https://example.invalid/chat-media/a.png"
URL2 = "https://example.invalid/chat-media/b.png"


def capture(chronological):
    return {"children": list(reversed(chronological)), "childCount": len(chronological),
            "startMarkerPresent": any(c["text"] == "Start of Grindr Web chat history" for c in chronological),
            "url": "https://web.grindr.com/chat"}


class ExportIntegrityTests(unittest.TestCase):
    def make_media_archive(self, directory, urls=(URL,)):
        root = Path(directory) / "capture"
        (root / "raw").mkdir(parents=True)
        rows = []
        for url in urls:
            row = child("Image 2:05 PM", 0)
            row["images"] = [{"src": url, "alt": "image"}]
            rows.append(row)
        payload = {"chatName": "Fixture only", "exportedAt": "2026-07-04T12:00:00Z",
                   "snapshots": [capture([child("Start of Grindr Web chat history"), child("3 Jul"), *rows])]}
        (root / "raw" / "dom_snapshots.json").write_text(json.dumps(payload))
        source = Path(directory) / "browser-artifact.png"
        source.write_bytes(PNG)
        return root, source, payload

    def test_original_bytes_hash_and_idempotent_ingest(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, _ = self.make_media_archive(directory)
            record = media.ingest(root, source, URL, "image", "browser-download")
            path = root / record["local_path"]
            self.assertEqual(path.read_bytes(), PNG)
            self.assertEqual(record["sha256"], hashlib.sha256(PNG).hexdigest())
            before = (root / "raw" / "media_copy_summary.json").read_bytes()
            self.assertEqual(media.ingest(root, source, URL, "image", "browser-page-assets"), record)
            self.assertEqual((root / "raw" / "media_copy_summary.json").read_bytes(), before)
            self.assertFalse(record["originalUploadVerified"])

    def test_shared_bytes_deduplicated_without_losing_message_associations(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, payload = self.make_media_archive(directory, (URL, URL2))
            one = media.ingest(root, source, URL, "image", "browser-download")
            two = media.ingest(root, source, URL2, "image", "browser-download")
            self.assertEqual(one["local_path"], two["local_path"])
            _, _, rows, exported, missing = archive.extract_messages(payload, root)
            self.assertEqual(len(exported), 2)
            self.assertEqual(len({m["message_id"] for m in exported}), 2)
            self.assertEqual(len(rows), 2)
            self.assertEqual(missing, [])

    def test_resume_when_bytes_written_but_manifest_commit_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, _ = self.make_media_archive(directory)
            with mock.patch.object(media, "atomic_manifest", side_effect=OSError("fixture interruption")):
                with self.assertRaises(OSError):
                    media.ingest(root, source, URL, "image", "browser-download")
            objects = list((root / "media" / "objects").iterdir())
            self.assertEqual(len(objects), 1)
            record = media.ingest(root, source, URL, "image", "browser-download")
            self.assertEqual((root / record["local_path"]).read_bytes(), PNG)
            self.assertEqual(len(media.load_verified_map(root)), 1)

    def test_media_corruption_is_detected_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, _ = self.make_media_archive(directory)
            record = media.ingest(root, source, URL, "image", "browser-download")
            target = root / record["local_path"]
            target.write_bytes(b"corrupt fixture")
            with self.assertRaises(ValueError):
                media.load_verified_map(root)
            with self.assertRaises(ValueError):
                media.ingest(root, source, URL, "image", "browser-download")
            self.assertEqual(target.read_bytes(), b"corrupt fixture")

    def test_wrong_chat_or_changed_capture_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, payload = self.make_media_archive(directory)
            with self.assertRaises(ValueError):
                media.ingest(root, source, URL2, "image", "browser-download")
            media.ingest(root, source, URL, "image", "browser-download")
            payload["chatName"] = "Another fixture capture"
            (root / "raw" / "dom_snapshots.json").write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                media.load_verified_map(root)

    def test_signed_url_and_unsupported_provider_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, _ = self.make_media_archive(directory)
            for url, provider in ((URL + "?Signature=fixture", "browser-download"), (URL, "cache-after-expiry")):
                with self.assertRaises(ValueError):
                    media.ingest(root, source, url, "image", provider)

    def test_html_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, _ = self.make_media_archive(directory)
            source.write_bytes(b"<html>login fixture</html>")
            with self.assertRaises(ValueError):
                media.ingest(root, source, URL, "image", "browser-download")
            for value in ("../private.png", "/tmp/private.png", "media/../../private.png"):
                with self.assertRaises(ValueError):
                    media.local_media_path(root, value)

    def test_timestamps_outside_bubble_and_message_ending_in_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, payload = self.make_media_archive(directory)
            row = child("Meet at 9:05 PM 2:05 PM", 0)
            row["bubble"]["text"] = "Meet at 9:05 PM"
            payload["snapshots"] = [capture([child("3 Jul"), row])]
            _, _, rows, _, _ = archive.extract_messages(payload, root)
            self.assertEqual(rows[0]["text"], "Meet at 9:05 PM")
            self.assertEqual(rows[0]["time_text"], "2:05 PM")

    def test_multi_snapshot_overlap_preserves_distinct_repeated_messages(self):
        start, date = child("Start of Grindr Web chat history"), child("3 Jul")
        a, same, b, c = child("A 2:00 PM", 0), child("Same 2:01 PM", 0), child("B 2:02 PM", 0), child("C 2:03 PM", 0)
        result = snapshots.reconcile({"snapshots": [capture([start, date, a, same, same, b]), capture([same, same, b, c])]})
        chronological = list(reversed(result["children"]))
        self.assertEqual([x["text"] for x in chronological], [start["text"], date["text"], a["text"], same["text"], same["text"], b["text"], c["text"]])
        self.assertTrue(result["snapshotContinuityVerified"])

    def test_gap_and_ambiguous_identical_overlap_fail_closed(self):
        cases = ([capture([child("A"), child("B")]), capture([child("C"), child("D")])],
                 [capture([child("Same"), child("Same")]), capture([child("Same"), child("Same")])])
        for pages in cases:
            with self.assertRaises(ValueError):
                snapshots.reconcile({"snapshots": pages})

    def test_failed_sqlite_rebuild_preserves_published_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive.sqlite"
            archive.write_sqlite(path, {}, [], [], [])
            before = path.read_bytes()
            row = {"id": "same", "sequence": 1, "sender": "Other", "side": "other", "date_label": None,
                   "time_text": None, "datetime": None, "text": "fixture", "html_text": "fixture", "raw_kind": "message"}
            with self.assertRaises(sqlite3.IntegrityError):
                archive.write_sqlite(path, {}, [row, copy.deepcopy(row)], [], [])
            self.assertEqual(path.read_bytes(), before)

    def run_export(self, root):
        with mock.patch.object(sys, "argv", ["grindr_dom_archive.py", str(root)]), contextlib.redirect_stdout(io.StringIO()):
            return archive.main()

    def test_repeated_normalization_is_byte_idempotent_and_readback_checks_real_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, _ = self.make_media_archive(directory)
            media.ingest(root, source, URL, "image", "browser-download")
            self.assertEqual(self.run_export(root), 0)
            before = {p: (root / p).read_bytes() for p in archive.OUTPUTS}
            self.assertEqual(self.run_export(root), 0)
            self.assertEqual(before, {p: (root / p).read_bytes() for p in archive.OUTPUTS})
            self.assertEqual(archive.verify_export(root)["status"], "PASS")
            (root / "messages.csv").write_text("interrupted fixture output")
            with self.assertRaises(ValueError):
                archive.verify_export(root)
            self.assertEqual(self.run_export(root), 0)
            self.assertEqual(before, {p: (root / p).read_bytes() for p in archive.OUTPUTS})

    def test_incomplete_capture_cannot_pass_even_with_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, payload = self.make_media_archive(directory)
            payload.update(acquisitionSchemaVersion=2, acquisitionComplete=True,
                           completionEvidence={"newestReached": False})
            (root / "raw" / "dom_snapshots.json").write_text(json.dumps(payload))
            self.assertEqual(self.run_export(root), 1)
            self.assertEqual(archive.verify_export(root)["status"], "FAIL")

    def test_received_image_without_bubble_has_visible_sender_and_no_signed_alt(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, payload = self.make_media_archive(directory)
            media.ingest(root, source, URL, "image", "browser-download")
            row = payload["snapshots"][0]["children"][0]
            row["bubble"] = None
            row["images"][0]["alt"] = "chat image received"
            _, _, rows, _, _ = archive.extract_messages(payload, root)
            self.assertEqual(rows[0]["side"], "other")
            row["images"][0]["alt"] = URL + "?Signature=fixture"
            _, _, _, exported, _ = archive.extract_messages(payload, root)
            self.assertIsNone(exported[0]["alt"])


if __name__ == "__main__":
    unittest.main()
