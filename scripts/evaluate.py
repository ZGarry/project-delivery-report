"""Reproduce deterministic contract checks; this is not an LLM A/B evaluation."""
import copy
import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

import report

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / 'evaluation'
output.mkdir(exist_ok=True)
run = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                     cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                     env={**__import__('os').environ, 'PYTHONUTF8': '1'})
log = run.stdout + run.stderr
(output / 'unittest.txt').write_text(log, encoding='utf-8')
fixture = json.loads((ROOT / 'examples/partial-delivery.json').read_text(encoding='utf-8'))
cases = []

def record(name, data, expected):
    try:
        report.validate(data)
        actual = 'accepted'
        reason = 'structural_only'
    except report.ReportError as error:
        actual, reason = 'rejected', str(error)
    cases.append({'case': name, 'expected': expected, 'actual': actual, 'reason': reason, 'passed': actual == expected})

record('valid_partial_delivery', fixture, 'accepted')
for name, mutate in [
    ('false_completion', lambda x: x.update(status='completed')),
    ('missing_acceptance_evidence', lambda x: x['acceptance'][0].update(evidence_ids=[])),
    ('wrong_environment', lambda x: x['evidence'][0].update(environment='another-environment')),
    ('wrong_revision', lambda x: x['evidence'][0].update(revision='another-revision')),
    ('code_tests_used_as_deployment', lambda x: x['delivery'].update(deployment='verified')),
    ('invented_evidence_reference', lambda x: x['outcomes'][0].update(evidence_ids=['not-present']))]:
    sample = copy.deepcopy(fixture)
    mutate(sample)
    record(name, sample, 'rejected')
cases.append({'case': 'unchanged_snapshot', 'expected': 'quiet', 'actual': report.attention(fixture, fixture),
              'passed': report.attention(fixture, fixture) == 'quiet'})
sample = copy.deepcopy(fixture)
sample['blockers'][0]['severity'] = 'critical'
cases.append({'case': 'critical_blocker', 'expected': 'urgent', 'actual': report.attention(sample),
              'passed': report.attention(sample) == 'urgent'})
baseline = subprocess.run(['git', 'rev-parse', 'v0.1.0'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
(ROOT / 'examples/after.md').write_text(report.render(fixture, report.attention(fixture)), encoding='utf-8')
hashes = {}
for path in sorted(ROOT.rglob('*')):
    if path.is_file() and path.parts[-1] != '.DS_Store' and not any(x in path.relative_to(ROOT).parts for x in ['.git', '__pycache__', 'evaluation']):
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
result = {'evaluated_at': datetime.now(timezone.utc).isoformat(), 'evaluation_type': 'deterministic_contract_checks',
          'python': platform.python_version(), 'platform': platform.system(), 'baseline_commit': baseline,
          'unittest_exit_code': run.returncode, 'test_count': int(re.search(r'Ran (\d+) tests?', log).group(1)),
          'scenario_checks': cases, 'source_hash_mode': 'sha256 with CRLF normalized to LF', 'source_sha256': hashes,
          'limitations': ['No LLM baseline/candidate trial', 'No production evidence verification',
                          'No measured business ROI or attention-time reduction', 'All scenario inputs are synthetic']}
(output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'tests': result['test_count'], 'unittest_exit_code': run.returncode,
                  'scenario_checks_passed': sum(x['passed'] for x in cases), 'scenario_checks_total': len(cases)}))
raise SystemExit(0 if run.returncode == 0 and all(x['passed'] for x in cases) else 1)
