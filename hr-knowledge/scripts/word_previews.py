#!/usr/bin/env python3
"""Create readable same-name PDF previews without modifying DOCX originals.

OpenKnowledge renders PDF but treats DOCX as opaque bytes. Existing PDFs are
reused on the first baseline; later DOCX changes regenerate their PDF preview.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "migration" / "word-preview-summary.json"
SCAN_ROOTS = (ROOT / "assets", ROOT / "outputs")
SOFFICE = "/opt/homebrew/bin/soffice"
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"
PDFINFO = "/opt/homebrew/bin/pdfinfo"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def docx_units(path: Path) -> list[str]:
    from docx import Document

    doc = Document(str(path))
    units = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            units.extend(cell.text for cell in row.cells)
    return [norm(x) for x in units if len(norm(x)) >= 4]


def is_ordered_subsequence(needle: str, haystack: str) -> bool:
    """Tolerate page headers and table column interleaving in PDF text order."""
    pos = 0
    for char in needle:
        pos = haystack.find(char, pos)
        if pos < 0:
            return False
        pos += 1
    return True


def pdf_text(path: Path) -> str:
    proc = subprocess.run(
        [PDFTOTEXT, "-layout", str(path), "-"],
        capture_output=True, text=True, errors="replace", timeout=90,
    )
    if proc.returncode:
        raise RuntimeError("pdftotext exit " + str(proc.returncode))
    return proc.stdout


def pdf_pages(path: Path) -> int:
    proc = subprocess.run([PDFINFO, str(path)], capture_output=True, text=True, timeout=30)
    if proc.returncode:
        raise RuntimeError("pdfinfo exit " + str(proc.returncode))
    match = re.search(r"(?m)^Pages:\s+(\d+)\s*$", proc.stdout)
    if not match:
        raise RuntimeError("pdf page count unavailable")
    return int(match.group(1))


def verify_pdf(docx: Path, pdf: Path) -> dict:
    if pdf.read_bytes()[:5] != b"%PDF-":
        raise RuntimeError("preview is not a PDF")
    pages = pdf_pages(pdf)
    if pages < 1:
        raise RuntimeError("preview has zero pages")
    text = pdf_text(pdf)
    if len(norm(text)) < 10:
        raise RuntimeError("preview has insufficient readable text")
    units = docx_units(docx)
    pdf_normalized = norm(text)
    total = sum(len(x) for x in units)
    # A whole table cell is often split across visual lines and columns;
    # exact substring matching falsely rejects valid, readable PDF output.
    matched = sum(len(x) for x in units if is_ordered_subsequence(x, pdf_normalized))
    coverage = round(matched / total, 4) if total else None
    return {
        "pdf_pages": pages,
        "pdf_text_chars": len(text),
        "text_coverage": coverage,
        "text_match_method": "ordered_subsequence_v1",
        "pdf_sha256": sha256(pdf),
    }


def convert(docx: Path, target: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="hr-word-preview-") as temp:
        work = Path(temp)
        out = work / "out"
        profile = work / "profile"
        out.mkdir()
        env = os.environ.copy()
        env.pop("ELECTRON_RUN_AS_NODE", None)
        env.pop("NODE_OPTIONS", None)
        proc = subprocess.run(
            [
                SOFFICE, "--headless",
                "-env:UserInstallation=" + profile.as_uri(),
                "--convert-to", "pdf:writer_pdf_Export",
                "--outdir", str(out), str(docx),
            ],
            capture_output=True, text=True, timeout=180, env=env,
        )
        generated = out / (docx.stem + ".pdf")
        if proc.returncode or not generated.is_file():
            raise RuntimeError(
                "LibreOffice conversion failed: exit=" + str(proc.returncode)
                + "; " + (proc.stderr or proc.stdout)[-500:]
            )
        # Verify before replacing any prior derivative preview. The DOCX is
        # never an output target and is never opened for writing.
        verified = verify_pdf(docx, generated)
        if verified["text_coverage"] is not None and verified["text_coverage"] < 0.85:
            raise RuntimeError("PDF text coverage below 0.85: " + str(verified["text_coverage"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(generated, target)
        return verified


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify manifest and previews without conversion")
    args = parser.parse_args()
    previous = {"documents": {}}
    if MANIFEST.is_file():
        previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
    old_entries = previous.get("documents", {})
    docx_files = sorted(
        (p for base in SCAN_ROOTS for p in base.rglob("*.docx") if p.is_file()),
        key=lambda p: p.relative_to(ROOT).as_posix(),
    )
    original_hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in docx_files}
    entries = {}
    errors = []
    counts = {"unchanged": 0, "existing_baseline": 0, "generated": 0, "regenerated": 0, "reverified": 0}
    for docx in docx_files:
        rel = docx.relative_to(ROOT).as_posix()
        pdf = docx.with_suffix(".pdf")
        preview_rel = pdf.relative_to(ROOT).as_posix()
        digest = original_hashes[rel]
        old = old_entries.get(rel)
        try:
            if args.check:
                if not old or old.get("docx_sha256") != digest or not pdf.is_file():
                    raise RuntimeError("manifest/preview is stale or missing")
                if sha256(pdf) != old.get("pdf_sha256"):
                    raise RuntimeError("PDF hash differs from manifest")
                entry = dict(old)
                counts["unchanged"] += 1
            elif old and old.get("docx_sha256") == digest and pdf.is_file():
                if sha256(pdf) != old.get("pdf_sha256"):
                    raise RuntimeError("existing preview differs from manifest; manual review required")
                entry = dict(old)
                if old.get("text_match_method") != "ordered_subsequence_v1":
                    entry.update(verify_pdf(docx, pdf))
                    counts["reverified"] += 1
                else:
                    counts["unchanged"] += 1
            else:
                source = "generated_libreoffice"
                if pdf.is_file() and not old:
                    # First baseline: preserve the curated PDF already present.
                    verified = verify_pdf(docx, pdf)
                    counts["existing_baseline"] += 1
                    source = "existing_curated_pdf"
                else:
                    verified = convert(docx, pdf)
                    counts["regenerated" if pdf.exists() and old else "generated"] += 1
                entry = {
                    "docx_sha256": digest,
                    "preview": preview_rel,
                    "preview_source": source,
                    **verified,
                }
            entry["docx"] = rel
            entry["preview"] = preview_rel
            entries[rel] = entry
        except Exception as exc:
            errors.append({"docx": rel, "error": str(exc)})
    after_hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in docx_files}
    if original_hashes != after_hashes:
        errors.append({"error": "DOCX original hash changed during preview generation"})
    result = {
        "schema_version": 1,
        "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "pass" if not errors and len(entries) == len(docx_files) else "fail",
        "docx_count": len(docx_files),
        "preview_count": len(entries),
        "counts": counts,
        "original_docx_modified": original_hashes != after_hashes,
        "documents": entries,
        "errors": errors,
        "note": "PDF is a reading preview. The DOCX original is unchanged; formal layout is verified in Word/WPS.",
    }
    manifest_unchanged = (
        MANIFEST.is_file()
        and previous.get("documents") == entries
        and previous.get("status") == result["status"]
    )
    if manifest_unchanged:
        # A timer must not create a new Git commit merely because it checked.
        result["verified_at"] = previous.get("verified_at", result["verified_at"])
        result["counts"] = previous.get("counts", counts)
    if not manifest_unchanged:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**{k: v for k, v in result.items() if k != "documents"},
                      "manifest_unchanged": manifest_unchanged}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
