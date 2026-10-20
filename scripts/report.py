"""Validate a report, render a management digest, and decide whether it changed.

Standard library only. Structural checks do not verify external evidence.
No network, scheduler, notifications, or execution of evidence locations.
"""
import argparse
import copy
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


class ReportError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReportError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def timestamp(value):
    require(text(value), 'timestamp must be a nonempty string')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ReportError('invalid timestamp') from None
    require(parsed.tzinfo is not None, 'timestamp must include UTC offset')
    return parsed


def fields(obj, required, optional=()):
    require(isinstance(obj, dict), 'expected object')
    require(set(required) <= set(obj), 'missing fields: ' + ', '.join(sorted(set(required) - set(obj))))
    require(set(obj) <= set(required) | set(optional), 'unknown fields: ' + ', '.join(sorted(set(obj) - set(required) - set(optional))))


def validate(report):
    fields(report, ['schema_version', 'task_id', 'title', 'as_of', 'environment', 'revision',
                    'goal', 'status', 'delivery', 'acceptance', 'evidence', 'outcomes',
                    'metrics', 'blockers', 'decision', 'next_step'])
    require(type(report['schema_version']) is int and report['schema_version'] == 1, 'unsupported schema_version')
    for key in ['task_id', 'title', 'environment', 'revision', 'goal', 'next_step']:
        require(text(report[key]), key + ' must be nonempty')
    as_of = timestamp(report['as_of'])
    require(report['status'] in ['completed', 'partial', 'blocked', 'failed'], 'invalid status')
    fields(report['delivery'], ['code', 'deployment'])
    for state in report['delivery'].values():
        require(state in ['verified', 'unverified', 'not_applicable'], 'invalid delivery state')
    evidence = {}
    require(isinstance(report['evidence'], list), 'evidence must be an array')
    for item in report['evidence']:
        fields(item, ['id', 'kind', 'location', 'observed_at', 'environment', 'revision', 'summary', 'collector'])
        for key in item:
            require(text(item[key]), 'evidence.' + key + ' must be nonempty')
        require(item['id'] not in evidence, 'duplicate evidence id')
        require(item['kind'] in ['source', 'build', 'test', 'runtime', 'deployment', 'business', 'review'], 'invalid evidence kind')
        require(timestamp(item['observed_at']) <= as_of, 'evidence is newer than report')
        evidence[item['id']] = item

    def refs(ids, current=False):
        require(isinstance(ids, list) and bool(ids), 'claim needs evidence_ids')
        require(all(text(eid) and eid in evidence for eid in ids), 'unknown evidence id')
        if current:
            require(all(evidence[eid]['environment'] == report['environment'] and
                        evidence[eid]['revision'] == report['revision'] for eid in ids),
                    'current claim uses another environment or revision')

    for key in ['acceptance', 'outcomes', 'metrics', 'blockers']:
        require(isinstance(report[key], list), key + ' must be an array')
    require(bool(report['acceptance']), 'acceptance criteria required')
    seen = set()
    for item in report['acceptance']:
        fields(item, ['id', 'criterion', 'status', 'evidence_ids'])
        require(text(item['id']) and item['id'] not in seen, 'invalid or duplicate acceptance id')
        seen.add(item['id'])
        require(text(item['criterion']), 'criterion must be nonempty')
        require(item['status'] in ['passed', 'failed', 'unverified', 'blocked'], 'invalid acceptance status')
        require(isinstance(item['evidence_ids'], list), 'evidence_ids must be an array')
        if item['evidence_ids']:
            refs(item['evidence_ids'], current=True)
        if item['status'] in ['passed', 'failed']:
            refs(item['evidence_ids'], current=True)
    if report['delivery']['code'] == 'verified':
        require(any(e['kind'] in ['source', 'build', 'test'] and e['revision'] == report['revision']
                    and e['environment'] == report['environment'] for e in evidence.values()),
                'verified code needs current code/build/test evidence')
    if report['delivery']['deployment'] == 'verified':
        require(any(e['kind'] in ['runtime', 'deployment'] and e['revision'] == report['revision']
                    and e['environment'] == report['environment'] for e in evidence.values()),
                'verified deployment needs current runtime/deployment evidence')
    for item in report['outcomes']:
        fields(item, ['claim', 'basis', 'evidence_ids'])
        require(text(item['claim']), 'outcome claim must be nonempty')
        require(item['basis'] in ['observed', 'estimated', 'unmeasured'], 'invalid outcome basis')
        require(isinstance(item['evidence_ids'], list), 'evidence_ids must be an array')
        if item['basis'] == 'observed':
            refs(item['evidence_ids'], current=True)
        elif item['evidence_ids']:
            refs(item['evidence_ids'])
    for metric in report['metrics']:
        fields(metric, ['name', 'unit', 'direction', 'before', 'after'])
        require(text(metric['name']) and text(metric['unit']), 'metric name/unit required')
        require(metric['direction'] in ['lower', 'higher'], 'metric direction must be lower or higher')
        for side in ['before', 'after']:
            item = metric[side]
            fields(item, ['value', 'sample_size', 'environment', 'revision', 'window', 'statistic', 'workload', 'evidence_ids'])
            require(type(item['value']) in [int, float] and math.isfinite(item['value']), 'metric value must be finite')
            require(type(item['sample_size']) is int and item['sample_size'] > 0, 'positive sample size required')
            for key in ['environment', 'revision', 'window', 'statistic', 'workload']:
                require(text(item[key]), 'metric.' + key + ' required')
            refs(item['evidence_ids'])
            require(all(evidence[eid]['environment'] == item['environment'] and
                        evidence[eid]['revision'] == item['revision'] for eid in item['evidence_ids']),
                    'metric evidence does not match its environment/revision')
    for blocker in report['blockers']:
        fields(blocker, ['summary', 'impact', 'next_action', 'severity', 'requires_user'])
        require(all(text(blocker[k]) for k in ['summary', 'impact', 'next_action']), 'blocker details required')
        require(blocker['severity'] in ['normal', 'critical'], 'invalid blocker severity')
        require(type(blocker['requires_user']) is bool, 'requires_user must be boolean')
    if report['decision'] is not None:
        fields(report['decision'], ['question', 'recommendation', 'impact', 'deadline'])
        require(all(text(v) for v in report['decision'].values()), 'decision details required')
        timestamp(report['decision']['deadline'])
    if report['status'] == 'completed':
        require(all(x['status'] == 'passed' for x in report['acceptance']), 'completed requires all acceptance passed')
        require(not report['blockers'], 'completed cannot contain unresolved blockers')
        require(report['decision'] is None, 'completed cannot have a pending decision')
        require(all(v != 'unverified' for v in report['delivery'].values()), 'completed cannot have unverified delivery')
    if report['status'] == 'blocked':
        require(bool(report['blockers']), 'blocked requires a blocker')
    return report


def comparison(metric):
    before, after = metric['before'], metric['after']
    mismatch = [k for k in ['environment', 'statistic', 'workload'] if before[k] != after[k]]
    if mismatch:
        return '条件不一致（' + ', '.join(mismatch) + '），仅并列展示，不计算改善率'
    if before['value'] == 0:
        return '旧值为 0，不计算百分比'
    delta = (after['value'] - before['value']) / abs(before['value'])
    gain = -delta if metric['direction'] == 'lower' else delta
    return f'同口径数值变化：{gain:+.2%}（正值表示改善；因果关系与长期收益仍需验证）'


def fingerprint(report):
    semantic = copy.deepcopy(report)
    semantic.pop('as_of', None)
    for item in semantic['evidence']:
        item.pop('observed_at', None)
    for key in ['evidence', 'acceptance']:
        semantic[key].sort(key=lambda x: x['id'])
    return hashlib.sha256(json.dumps(semantic, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def attention(report, previous=None):
    if previous is not None:
        require(previous['task_id'] == report['task_id'], 'previous report belongs to another task')
        if fingerprint(report) == fingerprint(previous):
            return 'quiet'
    if report['decision'] or any(b['severity'] == 'critical' or b['requires_user'] for b in report['blockers']):
        return 'urgent'
    return 'summary'


def render(report, level):
    labels = {'completed': '已完成', 'partial': '部分完成', 'blocked': '受阻', 'failed': '失败'}
    state = {'verified': '已核验', 'unverified': '未核验', 'not_applicable': '不适用'}
    basis = {'observed': '已观察', 'estimated': '估算，未证实收益', 'unmeasured': '未测量'}
    acceptance_labels = {'passed': '通过', 'failed': '失败', 'unverified': '未验证', 'blocked': '受阻'}
    lines = [f"# {report['title']}", '', f"**结论：{labels[report['status']]}｜汇报级别：{level}**",
             f"截至 {report['as_of']}；环境 {report['environment']}；版本 {report['revision']}", '',
             f"**目标：**{report['goal']}", '', '**实际结果：**', '']
    lines += [f"- {x['claim']}（{basis[x['basis']]}；证据：{', '.join(x['evidence_ids']) or '无'}）" for x in report['outcomes']]
    lines += ['', f"**交付状态：**源码 {state[report['delivery']['code']]}；部署 {state[report['delivery']['deployment']]}", '', '**验收：**', '']
    lines += [f"- {x['criterion']}：{acceptance_labels[x['status']]}（证据：{', '.join(x['evidence_ids']) or '缺少'}）" for x in report['acceptance']]
    lines += ['', '**前后对比：**', '']
    lines += [f"- {m['name']}：{m['before']['value']} → {m['after']['value']} {m['unit']}；{comparison(m)}；样本 {m['before']['sample_size']}/{m['after']['sample_size']}，统计量 {m['before']['statistic']}/{m['after']['statistic']}，环境 {m['before']['environment']}/{m['after']['environment']}，负载 {m['before']['workload']}/{m['after']['workload']}，窗口 {m['before']['window']}/{m['after']['window']}，版本 {m['before']['revision']}/{m['after']['revision']}，证据 {','.join(m['before']['evidence_ids'])}/{','.join(m['after']['evidence_ids'])}" for m in report['metrics']]
    if not report['metrics']:
        lines += ['- 暂无可比较的量化数据。']
    lines += ['', '**异常与处理：**', '']
    lines += [f"- {b['summary']}；影响：{b['impact']}；下一步：{b['next_action']}；需用户处理：{'是' if b['requires_user'] else '否'}" for b in report['blockers']] or ['- 无。']
    d = report['decision']
    lines += ['', '**需要你决定：**' + (f"{d['question']}；建议：{d['recommendation']}；影响：{d['impact']}；期限：{d['deadline']}" if d else '无。'),
              '', '**下一步：**' + report['next_step'], '', '<details><summary>证据索引与核验边界</summary>', '',
              '本工具仅检查结构、引用和状态一致性；未打开证据链接，未证明外部系统真实状态。', '']
    lines += [f"- {e['id']}｜{e['kind']}｜{e['summary']}｜位置：`{e['location']}`｜{e['environment']}｜{e['revision']}｜{e['observed_at']}｜采集者：{e['collector']}" for e in report['evidence']]
    lines += ['', '</details>', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = validate(json.loads(args.report.read_text(encoding='utf-8-sig')))
        previous = validate(json.loads(args.previous.read_text(encoding='utf-8-sig'))) if args.previous else None
        level = attention(report, previous)
        digest = render(report, level)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(digest, encoding='utf-8')
        print(json.dumps({'valid': True, 'attention': level, 'fingerprint': fingerprint(report),
                          'verification': 'structural_only'}, ensure_ascii=False))
        if not args.output and level != 'quiet':
            print(digest)
        return 0
    except (ReportError, ValueError, TypeError, KeyError, OSError) as error:
        print(json.dumps({'valid': False, 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
