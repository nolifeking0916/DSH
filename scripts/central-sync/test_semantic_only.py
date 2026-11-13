#!/usr/bin/env python3
import importlib.util, json, sys, tempfile
from pathlib import Path

SOURCE=Path('/Users/leto/WorkBuddy/HR技术中台/hr-knowledge/scripts/sync_online.py')
sys.path.insert(0,str(SOURCE.parent))
spec=importlib.util.spec_from_file_location('semantic_only',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix='semantic-only-test-') as td:
    state=Path(td)
    m.STATE=state;m.REPORT_FILE=state/'report.json';m.STATE_FILE=state/'state.json'
    m.PUBLISH_ROOTS=();m.ROOT_FILES=()
    m.ensure_word_previews=lambda check_only: {'status':'skipped'}
    m.safety_scan=lambda: {'status':'pass','file_count':0}
    m.load_state=lambda: {'roots':{}}
    m.git_sync=lambda: (_ for _ in ()).throw(AssertionError('Git must not run'))
    m.scan_output_ledger=lambda: (_ for _ in ()).throw(AssertionError('scan must not run'))
    sys.argv=[str(SOURCE),'--openviking-only','--skip-scan','--skip-intake']
    rc=m.main()
    report=json.loads((state/'report.json').read_text())
    assert rc==0 and report['status']=='pass',report
    assert report['git']=={'status':'skipped','reason':'openviking_only'},report
    print(json.dumps({'status':'pass','case':'openviking_only_skips_git_scan_and_intake'}))
