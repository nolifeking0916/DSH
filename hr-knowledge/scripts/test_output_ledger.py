#!/usr/bin/env python3
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import output_ledger

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.workspace = self.base / "workspace"
        self.desktop = self.base / "Desktop"
        self.source = self.workspace / "outputs" / "task" / "demo.final.md"
        self.source.parent.mkdir(parents=True)
        self.desktop.mkdir()
        self.source.write_text("safe synthetic final\n", encoding="utf-8")
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.config_path = self.base / "sources.json"
        self.db_path = self.base / "ledger.sqlite3"
        self.summary = self.base / "public.md"
        self.pending = self.base / "pending.md"
        self.raw = self.base / "raw.json"
        self.patches = [
            patch.object(output_ledger, "SUMMARY", self.summary),
            patch.object(output_ledger, "PENDING", self.pending),
            patch.object(output_ledger, "RAW_REPORT", self.raw),
            patch.object(output_ledger, "existing_repo_hashes", return_value={}),
        ]
        for item in self.patches:
            item.start()
        self.write_config([self.workspace, self.desktop])

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.tmp.cleanup()

    def write_config(self, roots):
        self.config_path.write_text(json.dumps({
            "version": 1,
            "ai_workspace_roots": [str(self.workspace)],
            "scan_roots": [str(p) for p in roots],
            "excluded_roots": [str(self.repo)],
            "excluded_dir_names": [".git", "node_modules", "Photos Library.photoslibrary"],
            "allowed_extensions": [".md", ".txt", ".png"],
            "max_auto_hash_bytes": 104857600,
            "auto_intake": False,
        }), encoding="utf-8")

    def scan(self):
        return output_ledger.scan(self.config_path, self.db_path, self.repo)

    def test_move_same_inode_and_source_unchanged(self):
        original_sha = output_ledger.sha256(self.source)
        first = self.scan()
        artifact = first["records"][0]["artifact_id"]
        self.assertEqual(first["records"][0]["status"], "eligible_reviewed_intake")
        moved = self.desktop / "renamed.final.md"
        self.source.rename(moved)
        second = self.scan()
        self.assertEqual(second["stats"]["candidate_count"], 1)
        self.assertEqual(second["records"][0]["artifact_id"], artifact)
        self.assertEqual(second["records"][0]["match_reason"], "same_inode")
        self.assertEqual(output_ledger.sha256(moved), original_sha)
        self.assertFalse(self.source.exists())
        db = sqlite3.connect(self.db_path)
        old_present = db.execute("SELECT present FROM locations WHERE path=?", (str(self.source),)).fetchone()[0]
        self.assertEqual(old_present, 0)
        db.close()

    def test_duplicate_uses_same_artifact(self):
        first = self.scan()
        artifact = first["records"][0]["artifact_id"]
        duplicate = self.desktop / "copy.final.md"
        duplicate.write_bytes(self.source.read_bytes())
        second = self.scan()
        self.assertEqual(second["stats"]["unique_artifact_count"], 1)
        copied = next(r for r in second["records"] if r["path"] == str(duplicate))
        self.assertEqual(copied["artifact_id"], artifact)
        self.assertEqual(copied["match_reason"], "same_unique_sha256")

    def test_unknown_and_image_are_held(self):
        unknown = self.desktop / "ordinary.md"
        unknown.write_text("not proven AI\n", encoding="utf-8")
        image = self.workspace / "outputs" / "task" / "image.final.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n")
        report = self.scan()
        states = {r["path"]: r["status"] for r in report["records"]}
        self.assertEqual(states[str(unknown)], "held_origin_review")
        self.assertEqual(states[str(image)], "held_binary_review")

    def test_sensitive_path_is_held(self):
        sensitive = self.workspace / "outputs" / "人员" / "example.final.md"
        sensitive.parent.mkdir(parents=True)
        sensitive.write_text("synthetic held\n", encoding="utf-8")
        report = self.scan()
        record = next(r for r in report["records"] if r["path"] == str(sensitive))
        self.assertEqual(record["status"], "held_sensitive_path")

    def test_dataless_file_is_held_without_reading_content(self):
        original = output_ledger.sha256
        def must_not_read(path):
            raise AssertionError("dataless file content must not be opened")
        with patch.object(output_ledger, "sha256", must_not_read):
            real_stat = self.source.stat()
            class DatalessStat:
                st_size = real_stat.st_size
                st_mtime_ns = real_stat.st_mtime_ns
                st_dev = real_stat.st_dev
                st_ino = real_stat.st_ino
                st_flags = output_ledger.SF_DATALESS
            db = output_ledger.init_db(self.db_path)
            digest, note, hit = output_ledger.cached_hash(db, self.source, DatalessStat(), 1024)
            db.close()
        self.assertIsNone(digest)
        self.assertEqual(note, "dataless_cloud_file_not_downloaded")
        self.assertFalse(hit)

    def test_dataless_rescan_does_not_append_observations(self):
        with patch.object(output_ledger, "cached_hash", return_value=(None, "dataless_cloud_file_not_downloaded", False)):
            first = self.scan()
            second = self.scan()
        self.assertEqual(first["records"][0]["status"], "held_cloud_not_local")
        self.assertEqual(second["stats"]["observations_written"], 0)
        db = sqlite3.connect(self.db_path)
        self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 1)
        db.close()

    def test_hash_cache_is_reused(self):
        self.scan()
        second = self.scan()
        self.assertEqual(second["stats"]["cache_hits"], 1)
        self.assertEqual(second["stats"]["same_inode_count"], 1)
        self.assertEqual(second["stats"]["observations_written"], 0)
        db = sqlite3.connect(self.db_path)
        self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 1)
        db.close()

    def test_path_escape_and_symlink_are_rejected(self):
        with self.assertRaises(ValueError):
            output_ledger.contained(self.base, "../outside.md")
        outside = self.base / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        link = self.workspace / "outputs" / "task" / "link.final.md"
        link.symlink_to(outside)
        report = self.scan()
        self.assertNotIn(str(link), [r["path"] for r in report["records"]])

    def test_photos_library_derivatives_are_not_candidates(self):
        library = self.base / "Pictures" / "Photos Library.photoslibrary" / "originals"
        library.mkdir(parents=True)
        derivative = library / "ordinary.png"
        derivative.write_bytes(b"not an AI candidate")
        report = self.scan()
        self.assertNotIn(str(derivative), [r["path"] for r in report["records"]])

    def test_hardlink_is_not_marked_as_missing_or_moved(self):
        first = self.scan()
        artifact = first["records"][0]["artifact_id"]
        link = self.desktop / "hardlink.final.md"
        import os
        os.link(self.source, link)
        second = self.scan()
        self.assertEqual(second["stats"]["unique_artifact_count"], 1)
        db = sqlite3.connect(self.db_path)
        states = dict(db.execute("SELECT path,present FROM locations WHERE artifact_id=?", (artifact,)).fetchall())
        db.close()
        self.assertEqual(states[str(self.source)], 1)
        self.assertEqual(states[str(link)], 1)
        self.assertNotEqual(second["records"][0]["status"], "missing_observed_not_deleted")

if __name__ == "__main__":
    unittest.main()
