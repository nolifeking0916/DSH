#!/usr/bin/env python3
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import intake_outputs
import sync_online


class IntakeTests(unittest.TestCase):
    def test_binary_atomic_copy_preserves_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.final.docx"
            dest = root / "nested" / "dest.final.docx"
            payload = b"original-final-bytes\x00\xff"
            source.write_bytes(payload)
            before = intake_outputs.sha256(source)
            intake_outputs.write_atomic(dest, None, source)
            self.assertEqual(dest.read_bytes(), payload)
            self.assertEqual(source.read_bytes(), payload)
            self.assertEqual(intake_outputs.sha256(source), before)
            self.assertFalse((root / "source.final.docx.intake-tmp").exists())
            self.assertFalse((dest.parent / "dest.final.docx.intake-tmp").exists())

    def test_semantic_target(self):
        self.assertEqual(intake_outputs.semantic_target("abc.final.docx").as_posix(),
                         "docs/current/final/abc.final.md")
        self.assertEqual(intake_outputs.semantic_target("abc.receipt.md").as_posix(),
                         "docs/evidence/final/abc.receipt.md")
        self.assertEqual(intake_outputs.semantic_target("archive/abc.final.docx").as_posix(),
                         "docs/evidence/nested/archive/abc.final.md")


class SyncTests(unittest.TestCase):
    def test_single_file_uses_exact_stem_uri(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "README.md").write_text("safe", encoding="utf-8")
            old_root = sync_online.ROOT
            sync_online.ROOT = root
            try:
                completed = Mock(returncode=0, stdout=json.dumps({"ok": True, "result": {"task_id": "t1"}}), stderr="")
                with patch.object(sync_online, "run", return_value=completed) as run, \
                     patch.object(sync_online, "wait_task", return_value={"task_id": "t1"}):
                    sync_online.upload_root("README.md", {}, root)
                command = run.call_args.args[0]
                self.assertIn("viking://resources/hr-knowledge/README", command)
                self.assertNotIn("--parent-auto-create", command)
            finally:
                sync_online.ROOT = old_root

    def test_output_ledger_scan_command_is_executable(self):
        completed = Mock(returncode=0, stdout=json.dumps({"status": "pass", "stats": {}}), stderr="")
        with patch.object(sync_online, "run", return_value=completed) as run:
            result = sync_online.scan_output_ledger()
        command = run.call_args.args[0]
        self.assertTrue(command[-2].endswith("output_ledger.py"))
        self.assertEqual(command[-1], "--scan")
        self.assertEqual(result["status"], "pass")

    def test_binary_original_roots_are_not_search_roots(self):
        self.assertNotIn("assets", sync_online.SEARCH_ROOTS)
        self.assertNotIn("outputs", sync_online.SEARCH_ROOTS)
        self.assertIn("docs", sync_online.SEARCH_ROOTS)

    def test_changed_paths_include_new_and_modified_only(self):
        previous = {"files": {"docs/a.md": "a", "docs/b.md": "b"}}
        current = {"files": {"docs/a.md": "a", "docs/b.md": "new", "docs/c.md": "c"}}
        self.assertEqual(sync_online.changed_paths(previous, current), ["docs/b.md", "docs/c.md"])

    def test_deletion_is_detected_before_upload(self):
        previous = {"files": {"docs/a.md": "a", "docs/b.md": "b"}}
        current = {"files": {"docs/a.md": "a"}}
        self.assertEqual(sync_online.deleted_paths(previous, current), ["docs/b.md"])


class ReviewedSourceIntakeTests(unittest.TestCase):
    def test_exact_copy_and_hash_change_hold(self):
        from intake_reviewed_sources import copy_reviewed
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source_root = base / "sources"
            repo = base / "repo"
            source = source_root / "task" / "source.md"
            source.parent.mkdir(parents=True)
            source.write_text("reviewed text\n", encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = base / "reviewed.json"
            manifest.write_text(json.dumps({
                "version": 1, "source_root": str(source_root),
                "target_root": "outputs", "cloud_search": False,
                "records": [{"source": "task/source.md", "target": "task/entry.md", "sha256": digest}],
            }), encoding="utf-8")
            first = copy_reviewed(manifest, repo)
            self.assertEqual(first["status"], "pass")
            self.assertEqual(first["copied"], 1)
            target = repo / "outputs" / "task" / "entry.md"
            self.assertEqual(target.read_bytes(), source.read_bytes())
            source.write_text("changed after review\n", encoding="utf-8")
            second = copy_reviewed(manifest, repo)
            self.assertEqual(second["status"], "fail")
            self.assertEqual(second["held"], 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "reviewed text\n")

    def test_reviewed_target_cannot_escape_outputs(self):
        from intake_reviewed_sources import contained
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                contained(Path(directory), "../outside.md")


if __name__ == "__main__":
    unittest.main()
