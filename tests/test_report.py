import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('report', ROOT / 'scripts/report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/partial-delivery.json').read_text(encoding='utf-8'))

    def rejected(self):
        with self.assertRaises(report.ReportError):
            report.validate(self.data)

    def metric(self):
        side = {'value': 100, 'sample_size': 10, 'environment': 'demo-local', 'revision': 'demo-v2',
                'window': 'synthetic-window', 'statistic': 'mean', 'workload': 'synthetic-identical-load', 'evidence_ids': ['E1']}
        metric = {'name': 'synthetic latency', 'unit': 'ms', 'direction': 'lower', 'before': side, 'after': copy.deepcopy(side)}
        metric['after']['value'] = 80
        self.data['metrics'] = [metric]
        return metric

    def test_valid_partial(self):
        report.validate(self.data)

    def test_false_completed_rejected(self):
        self.data['status'] = 'completed'
        self.rejected()

    def test_missing_evidence_rejected(self):
        self.data['acceptance'][0]['evidence_ids'] = []
        self.rejected()

    def test_unknown_evidence_rejected(self):
        self.data['outcomes'][0]['evidence_ids'] = ['missing']
        self.rejected()

    def test_old_environment_rejected(self):
        self.data['evidence'][0]['environment'] = 'old-env'
        self.rejected()

    def test_old_revision_rejected(self):
        self.data['evidence'][0]['revision'] = 'old-rev'
        self.rejected()

    def test_deployment_needs_runtime(self):
        self.data['delivery']['deployment'] = 'verified'
        self.rejected()

    def test_future_evidence_rejected(self):
        self.data['evidence'][0]['observed_at'] = '2026-10-21T10:00:00+08:00'
        self.rejected()

    def test_timezone_required(self):
        self.data['as_of'] = '2026-10-20T10:00:00'
        self.rejected()

    def test_duplicate_evidence_rejected(self):
        self.data['evidence'].append(copy.deepcopy(self.data['evidence'][0]))
        self.rejected()

    def test_unknown_field_rejected(self):
        self.data['complete_rate'] = 100
        self.rejected()

    def test_observed_needs_evidence(self):
        self.data['outcomes'][1]['basis'] = 'observed'
        self.rejected()

    def test_complete_valid_for_local_scope(self):
        self.data['status'] = 'completed'
        self.data['delivery']['deployment'] = 'not_applicable'
        self.data['acceptance'] = self.data['acceptance'][:1]
        self.data['blockers'] = []
        report.validate(self.data)

    def test_blocked_needs_blocker(self):
        self.data['status'] = 'blocked'
        self.data['blockers'] = []
        self.rejected()

    def test_requires_user_is_bool(self):
        self.data['blockers'][0]['requires_user'] = 'false'
        self.rejected()

    def test_metric_improvement_calculation(self):
        metric = self.metric()
        report.validate(self.data)
        self.assertIn('+20.00%', report.comparison(metric))
        metric['direction'] = 'higher'
        self.assertIn('-20.00%', report.comparison(metric))

    def test_zero_baseline(self):
        metric = self.metric()
        metric['before']['value'] = 0
        self.assertNotIn('%', report.comparison(metric))

    def test_changed_workload_not_comparable(self):
        metric = self.metric()
        metric['after']['workload'] = 'different'
        self.assertNotIn('%', report.comparison(metric))

    def test_changed_statistic_not_comparable(self):
        metric = self.metric()
        metric['after']['statistic'] = 'p95'
        self.assertNotIn('%', report.comparison(metric))

    def test_metric_evidence_mismatch(self):
        self.metric()['before']['revision'] = 'unknown-rev'
        self.rejected()

    def test_nan_not_measurement(self):
        self.metric()['before']['value'] = float('nan')
        self.rejected()

    def test_bool_not_measurement(self):
        self.metric()['before']['value'] = True
        self.rejected()

    def test_zero_sample_rejected(self):
        self.metric()['before']['sample_size'] = 0
        self.rejected()

    def test_duplicate_snapshot_quiet(self):
        previous = copy.deepcopy(self.data)
        self.data['as_of'] = '2026-10-20T12:00:00+08:00'
        self.data['evidence'][0]['observed_at'] = '2026-10-20T11:00:00+08:00'
        self.assertEqual('quiet', report.attention(self.data, previous))

    def test_change_gets_summary(self):
        previous = copy.deepcopy(self.data)
        self.data['next_step'] = 'changed result'
        self.assertEqual('summary', report.attention(self.data, previous))

    def test_critical_blocker_urgent(self):
        self.data['blockers'][0]['severity'] = 'critical'
        self.assertEqual('urgent', report.attention(self.data))

    def test_decision_urgent(self):
        self.data['decision'] = {'question': 'demo', 'recommendation': 'demo', 'impact': 'demo', 'deadline': self.data['as_of']}
        report.validate(self.data)
        self.assertEqual('urgent', report.attention(self.data))

    def test_pending_decision_cannot_complete(self):
        self.test_complete_valid_for_local_scope()
        self.data['decision'] = {'question': 'demo', 'recommendation': 'demo', 'impact': 'demo', 'deadline': self.data['as_of']}
        self.rejected()

    def test_different_task_previous_rejected(self):
        previous = copy.deepcopy(self.data)
        previous['task_id'] = 'other'
        with self.assertRaises(report.ReportError):
            report.attention(self.data, previous)

    def test_cli_valid_and_invalid_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.json'
            output = Path(folder) / 'digest.md'
            path.write_text(json.dumps(self.data), encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT / 'scripts/report.py'), str(path), '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(0, run.returncode, run.stderr)
            self.assertEqual('structural_only', json.loads(run.stdout)['verification'])
            self.assertTrue(output.exists())
            self.data['status'] = 'completed'
            path.write_text(json.dumps(self.data), encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT / 'scripts/report.py'), str(path)], capture_output=True, text=True)
            self.assertEqual(1, run.returncode)
            self.assertFalse(json.loads(run.stdout)['valid'])


if __name__ == '__main__':
    unittest.main()
