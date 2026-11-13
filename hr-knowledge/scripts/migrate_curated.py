#!/usr/bin/env python3
"""Curated, evidence-preserving migration for the HR knowledge repository.
Only explicitly selected document batches are read. Raw exports, secrets,
node_modules, old drafts and personal case files are not opened or uploaded.
"""
from __future__ import annotations
import csv, hashlib, json, os, re, shutil, subprocess
from collections import Counter
from pathlib import Path

SRC = Path('/Users/leto/.dsh/bot/workspace/work/hr-data-center')
DST = Path('/Users/leto/WorkBuddy/HR技术中台/hr-knowledge')
REVIEW = Path('/Users/leto/WorkBuddy/HR技术中台/review-inbox/hr-knowledge-migration')
EXTS = {'.md', '.markdown', '.txt', '.doc', '.docx', '.xls', '.xlsx', '.pptx', '.pdf'}
KNOWN_NAMES = ('钱凯芸', '刘杨', '倪国楷', '陈信克')
RESTRICTED_RE = re.compile(r'(?:人事核实问询|职工代表大会代表增补情况说明|人员名单|员工名单|未公示名单|花名册|通讯录|wx_users|hr_persons_all|hr_roster|hr_checkins|密钥|secret|token|hosting-keys)', re.I)
SECRET_RES = [
    re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----', re.I),
    re.compile(r'\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKID[A-Za-z0-9]{12,})\b'),
    re.compile(r'(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|passwd|private[_-]?key)\s*[:=]\s*["\']?[^\s"\',;]{12,}'),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}'),
    re.compile(r'(?i)https?://[^\s/:@]+:[^\s/@]+@'),
]
PERSONAL_RES = [
    # Do not treat ordinary document dates or blank form labels as personal
    # data. Look for values/identifiers, not the existence of a form field.
    re.compile(r'(?<![0-9])1[3-9][0-9]{9}(?![0-9])'),
    re.compile(r'(?<![0-9])[0-9]{17}[0-9Xx](?![0-9])'),
    re.compile(r'(?i)(?:工号|身份证号|身份证|手机号|手机号码|银行账号|银行卡号|leaveReasonRemarks|leaveDate|leaveType)\s*[:：=]\s*[^\s,，;；|]{1,80}'),
    re.compile(r'(?i)(?:薪级|工资|薪酬|津贴|薪资)\s*[:：=]\s*[0-9]+(?:\.[0-9]+)?'),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def extract(path: Path) -> tuple[str, str | None]:
    ext = path.suffix.lower()
    try:
        if ext in {'.md', '.markdown', '.txt'}:
            return path.read_text(encoding='utf-8', errors='replace'), None
        if ext == '.docx':
            from docx import Document
            d = Document(str(path))
            chunks = [p.text for p in d.paragraphs]
            for t in d.tables:
                for row in t.rows:
                    chunks.append(' | '.join(c.text for c in row.cells))
            return '\n'.join(chunks), None
        if ext == '.pptx':
            from pptx import Presentation
            p = Presentation(str(path))
            chunks = []
            for slide in p.slides:
                for shape in slide.shapes:
                    if hasattr(shape, 'text'):
                        chunks.append(shape.text)
            return '\n'.join(chunks), None
        if ext == '.xlsx':
            from openpyxl import load_workbook
            w = load_workbook(str(path), read_only=True, data_only=True)
            chunks = []
            for s in w.worksheets:
                chunks.append('## sheet: ' + s.title)
                for row in s.iter_rows(values_only=True):
                    chunks.append(' | '.join('' if v is None else str(v) for v in row))
            w.close()
            return '\n'.join(chunks), None
        if ext == '.pdf':
            p = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True, errors='replace', timeout=60)
            if p.returncode:
                return '', 'pdftotext exit ' + str(p.returncode)
            return p.stdout, None
        return '', 'legacy_office_requires_manual_conversion'
    except Exception as e:
        return '', type(e).__name__ + ': ' + str(e)


def add_selection(selection, pattern, batch, category, status):
    for p in SRC.glob(pattern):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        rel = p.relative_to(SRC).as_posix()
        old = selection.get(rel)
        item = {'path': p, 'relative': rel, 'batch': batch, 'category': category, 'status': status}
        if old is None:
            selection[rel] = item
        else:
            # Preserve the more specific/final classification on overlaps.
            selection[rel] = {**old, **item}


def build_selection():
    s = {}
    # Exact current outputs set: 12 main artifacts, 12 receipts and 8
    # provenance/evidence files. Unrelated snapshots and roster provenance
    # are deliberately not selected.
    final_stems = [
        '云上文旅集团人事档案管理办法',
        '人事核实问询-刘杨-2026-10-28',
        '人事核实问询-钱凯芸与刘杨-2026-10-28',
        '关于召开第四届第一次工会会员代表大会的通知-2026-10-29',
        '关于召开职工代表大会的通知-2026-10-28',
        '关于规范文件归档管理的通知',
        '职代会代表选举办法-2026-10-28',
        '职代会报备件-2026-10-28',
        '职工代表大会代表增补情况说明-2026-10-29',
        '职工代表大会拟审议议案清单-2026-10-28',
        '附件五-结构比例测算表-2026-10-28',
        '附件六-职工总数口径说明-2026-10-28',
    ]
    for stem in final_stems:
        add_selection(s, 'outputs/' + stem + '.final.*', 'batch1', 'final', 'final')
    for stem in ('附件五-结构比例测算表-2026-10-28', '附件六-职工总数口径说明-2026-10-28'):
        add_selection(s, 'outputs/' + stem + '.provenance.md', 'batch1', 'final', 'evidence')

    employee = 'build/干部制度审阅-20261104/员工版-20261106'
    add_selection(s, employee + '/_正式套docx-甲案改名-20261106/*', 'batch1', 'employee', 'approved-draft')
    # Current semantic source: the twelve S1-S6 documents plus the directory.
    add_selection(s, employee + '/S[1-6]-*/第0[1-6]号-*.md', 'batch1', 'employee', 'approved-draft')
    add_selection(s, employee + '/00-员工版总目录.md', 'batch1', 'employee', 'approved-draft')
    for rel in (
        '/_正式套docx-甲案改名-20261106/_交付清单-甲案改名-20261106.md',
        '/_秘书终审回执-员工版docx正式套-甲案改名-20261106.md',
        '/_秘书审校结案总单-员工版-20261106.md',
        '/员工版实质规则对照-S3至S6.md',
    ):
        add_selection(s, employee + rel, 'batch1', 'employee', 'approved-draft')

    add_selection(s, 'build/面板/PPT-旧新制度对比-20261106/干部管理制度新旧对比-20261106.*', 'batch1', 'ppt', 'approved-draft')
    add_selection(s, 'build/面板/最终件清单-PPT-20261106.md', 'batch1', 'ppt-evidence', 'evidence')
    add_selection(s, 'build/行文/PPT页面文案-20261106.md', 'batch1', 'ppt', 'approved-draft')
    add_selection(s, 'build/_秘书终审回执-PPT成品-20261106.md', 'batch1', 'ppt-evidence', 'evidence')
    add_selection(s, 'build/干部制度审阅-20261104/31-PPT数据底稿-20261106/*', 'batch1', 'ppt-evidence', 'evidence')
    add_selection(s, 'build/职代会/浙江省职工代表大会操作规程试行-浙总工发2014-41号.pdf', 'batch1', 'regulation', 'reference')
    add_selection(s, 'build/职代会/浙江省企业民主管理条例-官方PDF.pdf', 'batch1', 'regulation', 'reference')
    add_selection(s, 'build/职代会/浙江省企业民主管理条例-现取原文与核读-2026-10-28.md', 'batch1', 'regulation', 'reference')
    add_selection(s, 'build/职代会/条例版本核实-官方目录证据-2026-10-28.md', 'batch1', 'regulation', 'reference')

    add_selection(s, 'build/核心人才管理-生命周期分类-20261104/*', 'batch2', 'research', 'working')
    add_selection(s, 'build/干部制度新稿-20261104/*.md', 'batch2', 'revision', 'working')
    add_selection(s, 'build/干部制度新稿-20261104/S[1-6]-*/*审校修订.md', 'batch2', 'revision', 'working')
    add_selection(s, 'build/职代会-机构填报表空表包-2026-10-29/*', 'batch2', 'templates', 'working')
    add_selection(s, 'build/机构填报表空表包-清单-2026-10-29.md', 'batch2', 'templates', 'working')
    add_selection(s, 'build/议题审议情况报告单-2026-10-30/*', 'batch2', 'meeting-templates', 'working')
    add_selection(s, 'build/议题二审议情况报告单-清单-2026-10-29.md', 'batch2', 'meeting-templates', 'working')
    add_selection(s, 'build/会后文件-2026-10-30/*待填*.docx', 'batch2', 'meeting-templates', 'working')
    v5 = 'build/干部制度审阅-20261104/重建v5'
    for name in ('_工具写法规范.md', '_待拍板决策单.md', '_进度台账.md', 'v5两件体例与留痕规则-20261105.md', 'v5两件体例与留痕规则-v2-20261105.md'):
        add_selection(s, v5 + '/' + name, 'batch2', 'revision-v5', 'working')
    add_selection(s, v5 + '/S[1-6]-*/*修订说明.md', 'batch2', 'revision-v5', 'working')
    add_selection(s, 'build/面板/PPT-新旧三列对照-20261106/集团本部25件范围确认定稿-20261107.md', 'batch2', 'research', 'working')
    add_selection(s, 'build/面板/PPT-新旧三列对照-20261106/本次整合核心逻辑关键词-20261107.md', 'batch2', 'research', 'working')

    # Never select archives, raw exports, or drafts even if a broad pattern
    # changes later. Keep the expected curated count visible as a hard gate.
    for rel in list(s):
        p = Path(rel)
        if any(part.startswith('_留档') or part.startswith('_旧件') or part == 'drafts' for part in p.parts):
            del s[rel]
    counts = Counter(x['batch'] for x in s.values())
    if counts != Counter({'batch1': 87, 'batch2': 73}):
        raise RuntimeError('curated selection count mismatch: ' + repr(counts))
    return s


def safe_name(name):
    name = re.sub(r'[\x00-\x1f/\\]', '_', name)
    return name or 'document'


def primary_dest(item, companion=False):
    p = Path(item['relative'])
    n = safe_name(p.name)
    cat = item['category']
    ext = p.suffix.lower()
    if cat == 'final':
        if '.receipt' in n or '.provenance' in n:
            return Path('docs/evidence/final') / n
        if ext in {'.md', '.markdown'}:
            return Path('docs/current/final') / n
        return Path('docs/current/final') / (p.stem + '.md')
    if cat == 'employee':
        if ext in {'.md', '.markdown'}:
            folder = 'docs/evidence/employee' if any(k in n for k in ('回执', '结案', '待确认', '清单')) else 'docs/current/employee'
            return Path(folder) / n
        return Path('assets/employee') / n
    if cat == 'ppt':
        if ext in {'.md', '.markdown'}:
            return Path('docs/current/ppt') / n
        return Path('assets/ppt') / n
    if cat == 'ppt-evidence':
        return Path('docs/evidence/ppt') / n if ext in {'.md', '.markdown'} else Path('assets/ppt-evidence') / n
    if cat == 'regulation':
        return Path('docs/reference/regulation') / n if ext in {'.md', '.markdown'} else Path('assets/reference/regulation') / n
    if ext in {'.md', '.markdown'}:
        return Path('docs/working') / cat / n
    return Path('assets/working') / cat / n


def main():
    selection = build_selection()
    REVIEW.mkdir(parents=True, exist_ok=True)
    (DST / 'migration').mkdir(parents=True, exist_ok=True)
    records = []
    for item in sorted(selection.values(), key=lambda x: x['relative']):
        path = item['path']
        rel = item['relative']
        digest = sha256(path)
        text, error = extract(path)
        reasons = []
        if RESTRICTED_RE.search(rel):
            reasons.append('restricted_personnel_or_credential_path')
        if error:
            reasons.append(error)
        if not text.strip() and path.suffix.lower() not in {'.pdf'}:
            reasons.append('empty_text_extraction')
        if any(r.search(text) for r in SECRET_RES):
            reasons.append('possible_secret')
        if any(r.search(text) for r in PERSONAL_RES):
            reasons.append('possible_personal_data')
        if any(n in text or n in rel for n in KNOWN_NAMES):
            reasons.append('known_person_name')
        rec = {**{k: v for k, v in item.items() if k != 'path'}, 'source': str(path), 'sha256': digest, 'bytes': path.stat().st_size, 'reasons': reasons, 'destinations': [], 'text_chars': len(text)}
        if reasons:
            rec['migration_status'] = 'held'
            records.append(rec)
            continue
        # Original artifact destination. Markdown is also placed in the
        # semantic tree; Office/PDF originals stay as attachments.
        dest = primary_dest(item)
        targets = []
        if item['category'] == 'final':
            # Preserve the final gate's original artifact under outputs too.
            original = Path('outputs') / safe_name(path.name)
            targets.append(original)
            if path.suffix.lower() in {'.md', '.markdown'}:
                targets.append(dest)
            else:
                # DOCX/PDF final gets a Markdown semantic companion.
                targets.append(dest)
        else:
            targets.append(dest)
            # Working Office files without a same-name Markdown source receive
            # a searchable companion. Employee/PPT/regulation already have
            # curated Markdown or are intentionally attachment-only.
            if path.suffix.lower() not in {'.md', '.markdown'} and item['batch'] == 'batch2':
                targets.append(Path('docs/extracted') / item['category'] / (path.stem + '.md'))
        for target in targets:
            target = DST / target
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix.lower() == '.md' and path.suffix.lower() not in {'.md', '.markdown'}:
                body = '# ' + path.stem + '\n\n'
                body += '> status: ' + item['status'] + '; source_sha256: ' + digest + '\n\n'
                body += text
                target.write_text(body, encoding='utf-8')
            else:
                if target.exists() and sha256(target) != digest:
                    rec['reasons'].append('destination_collision:' + str(target.relative_to(DST)))
                    continue
                shutil.copy2(path, target)
            rec['destinations'].append(str(target.relative_to(DST)))
        rec['migration_status'] = 'migrated' if rec['destinations'] and not rec['reasons'] else 'held'
        records.append(rec)
    counts = Counter(r['migration_status'] for r in records)
    by_batch = {b: dict(Counter(r['migration_status'] for r in records if r['batch'] == b)) for b in ('batch1', 'batch2')}
    reason_counts = Counter(x for r in records for x in r['reasons'])
    summary = {'selection_count': len(selection), 'status_counts': dict(counts), 'by_batch': by_batch, 'exclusion_reason_counts': dict(reason_counts), 'copied_destination_count': sum(len(r['destinations']) for r in records), 'full_manifest_outside_online_root': str(REVIEW / 'curated-manifest.json')}
    (REVIEW / 'curated-manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    (DST / 'migration' / 'curated-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    with (REVIEW / 'curated-held.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f); w.writerow(['source', 'sha256', 'reasons'])
        for r in records:
            if r['migration_status'] == 'held': w.writerow([r['source'], r['sha256'], ';'.join(r['reasons'])])
    with (DST / 'migration' / 'curated-index.md').open('w', encoding='utf-8') as f:
        f.write('# 策选迁移索引\n\n仅列在线仓内路径；源路径、哈希与排除原因见仓外复核清单。\n\n')
        for r in records:
            if r['migration_status'] == 'migrated':
                f.write('- ' + r['relative'] + ' → ' + '; '.join(r['destinations']) + '\n')
    with (DST / 'migration' / 'curated-held-summary.md').open('w', encoding='utf-8') as f:
        f.write('# 策选批次未迁移项\n\n仅列类别和数量，完整源路径在仓外。\n\n')
        for k, n in sorted(reason_counts.items(), key=lambda x: (-x[1], x[0])):
            f.write('- ' + k + ': ' + str(n) + ' 件\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
