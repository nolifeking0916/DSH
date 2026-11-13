#!/usr/bin/env python3
"""Independent local verification of the curated migration.
No cloud writes. Full source paths stay in the outside review directory.
"""
from __future__ import annotations
import hashlib, json, re
from collections import Counter
from pathlib import Path
import migrate_curated as m

ROOT = m.DST
REVIEW = m.REVIEW

def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def main():
    records = json.loads((REVIEW / 'curated-manifest.json').read_text(encoding='utf-8'))
    errors = []
    checked_originals = 0
    checked_companions = 0
    for r in records:
        if r['migration_status'] != 'migrated':
            continue
        src = Path(r['source'])
        for rel in r['destinations']:
            dst = ROOT / rel
            if not dst.is_file():
                errors.append('missing:' + rel)
                continue
            generated = dst.suffix.lower() == '.md' and src.suffix.lower() not in {'.md', '.markdown'}
            if generated:
                body = dst.read_text(encoding='utf-8')
                if 'source_sha256: ' + r['sha256'] not in body:
                    errors.append('companion_hash_header:' + rel)
                text, error = m.extract(src)
                if error or text not in body:
                    errors.append('companion_content:' + rel)
                checked_companions += 1
            else:
                if digest(dst) != r['sha256']:
                    errors.append('original_hash:' + rel)
                checked_originals += 1
    # Scan every text-like online file independently; report paths only.
    sensitive = []
    for p in ROOT.rglob('*'):
        if not p.is_file() or '.git' in p.parts or p.suffix.lower() not in {'.md', '.markdown', '.txt', '.json', '.yml', '.yaml', '.py'}:
            continue
        text = p.read_text(encoding='utf-8', errors='replace')
        # Hashes are opaque identifiers, not phone/ID values. The migration
        # script also contains its deliberate blocklist literals; it is code,
        # not migrated HR content, so only scan it for secret patterns.
        scan_text = re.sub(r'(?m)^.*(?:source_)?sha256.*$', '', text)
        reasons = []
        if any(x.search(scan_text) for x in m.SECRET_RES): reasons.append('possible_secret')
        if p.relative_to(ROOT).parts[0] != 'scripts':
            if any(x.search(scan_text) for x in m.PERSONAL_RES): reasons.append('possible_personal_data')
            if any(n in scan_text for n in m.KNOWN_NAMES): reasons.append('known_person_name')
        if reasons: sensitive.append({'path': str(p.relative_to(ROOT)), 'reasons': reasons})
    # A held source basename must not have been copied into the online root.
    held_leaks = []
    for r in records:
        if r['migration_status'] == 'held':
            name = Path(r['source']).name
            for p in ROOT.rglob(name):
                if '.git' not in p.parts:
                    held_leaks.append(str(p.relative_to(ROOT)))
    status = 'pass' if not errors and not sensitive and not held_leaks else 'fail'
    report = {
        'status': status,
        'source_records': len(records),
        'migrated_sources': sum(r['migration_status'] == 'migrated' for r in records),
        'held_sources': sum(r['migration_status'] == 'held' for r in records),
        'checked_original_destinations': checked_originals,
        'checked_markdown_companions': checked_companions,
        'errors': errors,
        'sensitive_hits': sensitive,
        'held_artifact_leaks': held_leaks,
    }
    (REVIEW / 'migration-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {k: v for k, v in report.items() if k not in {'sensitive_hits', 'held_artifact_leaks', 'errors'}}
    summary['error_count'] = len(errors)
    summary['sensitive_hit_count'] = len(sensitive)
    summary['held_artifact_leak_count'] = len(held_leaks)
    (ROOT / 'migration' / 'verification-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if status != 'pass':
        print(json.dumps({'errors': errors, 'sensitive_hits': sensitive, 'held_artifact_leaks': held_leaks}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
