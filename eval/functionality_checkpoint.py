"""One consolidated, immutable cross-suite checkpoint; no assessment starts here."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT/'console/office'
TARGET = Path(os.environ.get('CARGO_TARGET_DIR', str(ROOT/'.build/rust')))


def run(label):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', label):
        raise ValueError('Use a safe unique checkpoint label')
    output = ROOT/'eval/reports/checkpoints'/label
    output.mkdir(parents=True, exist_ok=False)
    npm = shutil.which('npm.cmd') or shutil.which('npm')
    if not npm:
        raise RuntimeError('npm unavailable')
    env = dict(os.environ, TRUSTGATE_TEST_REAL='1', TRUSTGATE_URL='http://127.0.0.1:8000',
        TRUSTGATE_BRIDGE_KEY_FILE=str(ROOT/'data/roe_signing_key'))
    pattern = 'Test(Binding|ContextRequires|ActualArguments|UntrustedTarget|TargetLineage|ResumedFlow|UnsupportedShell|ClientRejects|ExecutionProjection|CedarLive|Governance)'
    jobs = [
        ('rust', ['cargo','test','--offline','--manifest-path','trustgate/service/Cargo.toml','--target-dir',str(TARGET)], ROOT),
        ('python', [sys.executable,'-B','-m','pytest','tests','-q','-p','no:cacheprovider'], ROOT),
        ('go_boundary', ['go','test','-json','./pkg/trustgate','./pkg/tools','./pkg/providers','-run',pattern,'-count=1'], ROOT/'pentagi_upstream/backend'),
        ('go_embedding_none', ['go','test','./pkg/providers/embeddings','-run','TestEmbedder_New_BuildsAnAvailableEmbedderForEveryProvider/none','-count=1'], ROOT/'pentagi_upstream/backend'),
        ('go_config', ['go','test','-json','./pkg/config','-count=1'], ROOT/'pentagi_upstream/backend'),
        ('frontend_3d_build', [npm,'run','build'], SCENE),
        ('frontend_ta', [npm,'run','check:ta-alignment'], SCENE),
        ('frontend_audit', [npm,'run','check:audit'], SCENE),
        ('frontend_transport', [npm,'run','check:trustgate'], SCENE),
        ('frontend_session', [npm,'run','check:session-panel'], SCENE),
        ('frontend_office', [npm,'run','check:office'], SCENE),
        ('frontend_picking', [npm,'run','check:actor-picking'], SCENE),
        ('frontend_visual_feedback', [npm,'run','check:visual-feedback'], SCENE),
        ('frontend_metric_math', [npm,'run','check:performance-metrics'], SCENE),
        ('frontend_redesign', [npm,'run','check:redesign'], SCENE),
        ('adversarial', [sys.executable,'-B','-m','eval.scope_violation_tests.run_eval'], ROOT),
    ]
    result = {'started_at':datetime.now(timezone.utc).isoformat(), 'label':label,
        'status':'running', 'checks':[], 'limits':'Suite/data checks are not rendered acceptance. Go tests are the focused boundary profile, not all upstream Go tests.'}
    def execute(job):
        name,args,cwd = job
        start = time.monotonic()
        try:
            completed = subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                encoding='utf-8',errors='replace',timeout=240)
            text,code = completed.stdout,completed.returncode
        except subprocess.TimeoutExpired as exc:
            text = str(exc.stdout or '')+'\nCHECKPOINT TIMEOUT after 240s'
            code = 124
        (output/(name+'.log')).write_bytes(text.encode('utf-8'))
        check = {'name':name,'command':args,'cwd':str(cwd),'exit_code':code,
            'passed':code==0,'elapsed_seconds':round(time.monotonic()-start,3),'log':name+'.log'}
        if name == 'rust':
            match = re.search(r'test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed',text)
            if match: check.update(passed_tests=int(match[1]),failed_tests=int(match[2]))
        elif name == 'python':
            match = re.search(r'(\d+) passed',text)
            if match: check['passed_tests'] = int(match[1])
        elif name in ('go_boundary','go_config'):
            events = []
            for line in text.splitlines():
                try: events.append(json.loads(line))
                except json.JSONDecodeError: pass
            check['passed_top_level_tests'] = sum(e.get('Action')=='pass' and bool(e.get('Test')) and '/' not in e['Test'] for e in events)
            if name == 'go_boundary':
                check['real_cedar_test_passed'] = any(e.get('Test')=='TestCedarLiveProfile' and e.get('Action')=='pass' for e in events)
        elif name == 'adversarial':
            match = re.search(r'Results: (\d+)/(\d+) passed',text)
            if match: check.update(passed_tests=int(match[1]),total_tests=int(match[2]))
        print(json.dumps(check),flush=True)
        return check
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(execute,job) for job in jobs]):
            result['checks'].append(future.result())
            (output/'results.json').write_bytes(json.dumps(result,indent=2).encode('utf-8'))
    # Budget validation reads generated chunks, so it must follow the build.
    if any(c['name']=='frontend_3d_build' and c['passed'] for c in result['checks']):
        result['checks'].append(execute(('frontend_bundle', [npm,'run','check:bundle'], SCENE)))
    else:
        result['checks'].append({'name':'frontend_bundle','passed':False,'exit_code':1,
                                'reason':'Production build failed; stale chunks cannot establish the budget'})
    result.update(finished_at=datetime.now(timezone.utc).isoformat(),status='passed' if all(c['passed'] for c in result['checks']) else 'failed')
    (output/'results.json').write_bytes(json.dumps(result,indent=2).encode('utf-8'))
    scope = ROOT/'eval/reports/scope_violation_results.json'
    if scope.is_file(): shutil.copyfile(scope,output/'adversarial_results.json')
    print(json.dumps({'checkpoint':str(output),'status':result['status'],'passed_checks':sum(c['passed'] for c in result['checks']),'total_checks':len(result['checks'])}),flush=True)
    return 0 if result['status']=='passed' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    raise SystemExit(run(parser.parse_args().label))
