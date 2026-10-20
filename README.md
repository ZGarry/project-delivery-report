# 项目交付与主动汇报 Skill

让 AI 主动交付结果、异常和必要决策，让负责人通过摘要与证据管理任务。

这是一个可安装的 Codex/Claude skill，附带无依赖的结构化检查与摘要生成工具。它不会自行定时运行、发送通知或验收外部业务。

- **[使用规则](SKILL.md)**：何时汇报、汇报什么、完成结论的证据要求。
- **[前后对比与实测结果](COMPARISON.md)**：原版已有能力、新版改动、实际测试及未验证收益。
- **[固定汇报格式](references/report-contract.md)**：交付、异常、周期业绩与静默规则。
- **[实际生成的示例摘要](examples/after.md)**：来自明确标注的合成输入，不是真实项目业绩。
- **[机器可读验证结果](evaluation/results.json)** / [测试原始记录](evaluation/unittest.txt)。

## 从哪里开始

日常直接让代理使用 `$project-delivery-report` 汇报当前授权任务。大需求交付网页，小改动简短说明。可复制的指令见 [通用提示词](references/reusable-prompt.md)。

汇报结构：**结论 → 目标 → 实际结果 → 验收证据 → 业务价值 → 异常与处理 → 需要你决定 → 下一步**。无决策明确写“无”。用户已有格式优先。

## 安装

将本仓库的 `SKILL.md`、`agents/`、`references/`、`scripts/report.py`、`examples/`、`tests/` 放入目标代理的 `skills/project-delivery-report/`，例如 `~/.codex/skills/project-delivery-report/` 或 `~/.claude/skills/project-delivery-report/`。已有版本先备份，保留历史材料；不必复制 Git 元数据、仓库评测结果或 CI 文件。

在已有技能分发机制的项目中，将这些文件纳入受控 skills 目录，并沿用项目同步流程。仅上传 GitHub 不会自动更新某台机器的安装，也不会自动把每个运行中的任务改成新规则。

## 可选结构化工具

Python 3.10+，无需 pip 安装，离线运行：

```text
python scripts/report.py examples/partial-delivery.json --output digest.md
python scripts/report.py examples/partial-delivery.json --previous examples/partial-delivery.json --output digest.md
python -m unittest discover -s tests -v
```

第一条生成摘要，第二条演示同任务重复状态返回 `quiet`。完整字段和退出码见 [数据契约](references/structured-report.md)。本工具检查状态矛盾、引用关系和对比口径，**valid=true 只代表结构检查通过**，不等于业务验收。

要主动定时推送，需要已有调度器、授权渠道、发送回执与去重台账。调用方应处理证据过期、决策期限和异常升级；本仓库不暗示这些系统已部署。

## 复现本次评测

在包含 `v0.1.0` 标签的完整仓库中运行：

```text
python scripts/evaluate.py
```

结果写入 `evaluation/` 并重新生成 `examples/after.md`。这是确定性的契约回放，不是模型前后盲测，不得据此宣称真实业绩或 AI 修复成功率提升。GitHub Actions 同时运行 Python 3.10/3.12 的契约测试；是否通过以对应提交的实际运行记录为准。

## 版本与证据

- `v0.1.0`：本地原版四个技能文件原样发布，保留可追溯基线。
- `v0.2.0`：增加主动汇报、管理摘要、价值口径、结构化检查、测试和比较结果。
- [原版与新版代码差异](https://github.com/ZGarry/project-delivery-report/compare/v0.1.0...v0.2.0)。

公开仓库只包含通用规则、合成案例和工具验证结果，不包含内部业务证据、账号或凭据。
