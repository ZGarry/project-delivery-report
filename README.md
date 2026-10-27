# 项目交付与主动汇报 Skill

让 AI 主动交付结果、异常和必要决策，让负责人通过摘要与证据管理任务。

这是一个可安装的 Codex/Claude skill，附带无依赖的结构化检查与摘要生成工具。它不会自行定时运行、发送通知或验收外部业务。

- **[下载 ZIP](https://github.com/ZGarry/project-delivery-report/archive/refs/heads/main.zip)** / [安装与更新](#下载与安装)。
- **[四类用户认可的案例写法](examples/demo-catalog.md)**：流程验收、替换对照、功能交付、性能优化。
- **[使用规则](SKILL.md)**：何时汇报、汇报什么、完成结论的证据要求。
- **[前后对比与实测结果](COMPARISON.md)**：原版已有能力、新版改动、实际测试及未验证收益。
- **[固定汇报格式](references/report-contract.md)**：交付、异常、周期业绩与静默规则。
- **[实际生成的示例摘要](examples/after.md)**：来自明确标注的合成输入，不是真实项目业绩。
- **[机器可读验证结果](evaluation/results.json)** / [测试原始记录](evaluation/unittest.txt)。

## 从哪里开始

日常直接让代理使用 `$project-delivery-report` 汇报当前授权任务。大需求交付网页，小改动简短说明。可复制的指令见 [通用提示词](references/reusable-prompt.md)。

汇报结构：**结论 → 目标 → 实际结果 → 验收证据 → 业务价值 → 异常与处理 → 需要你决定 → 下一步**。无决策明确写“无”。用户已有格式优先。

## 下载与安装

### 方式一：下载 ZIP，无需 Git

1. 点击 **[下载最新版 ZIP](https://github.com/ZGarry/project-delivery-report/archive/refs/heads/main.zip)**，或在仓库页面点 **Code → Download ZIP**。
2. 解压，把文件夹 `project-delivery-report-main` 改名为 `project-delivery-report`。保留 `SKILL.md`、`agents/`、`references/`、`scripts/`、`examples/` 等配套文件；不要只下载一个 `SKILL.md`。
3. 将整个文件夹放到所用代理的技能目录。若已有同名安装，先保存原版本，再按下方更新说明处理。

| 使用方式 | 安装后入口 |
| --- | --- |
| Codex 当前文档列出的用户全局目录 | `~/.agents/skills/project-delivery-report/SKILL.md` |
| Codex 当前文档列出的项目目录 | `<项目>/.agents/skills/project-delivery-report/SKILL.md` |
| Claude Code 用户全局目录 | `~/.claude/skills/project-delivery-report/SKILL.md` |

Windows 中 `~` 表示用户目录，例如 `C:\Users\你的用户名`。文件夹中应直接有 `SKILL.md`，避免多套一层 `project-delivery-report-main`。

Codex 路径与发现行为见 [OpenAI 官方文档](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。已有安装器或旧环境可能使用 `~/.codex/skills`；更新时沿用当前能被发现的安装位置，不在两个目录重复安装。同样的 skill 在多个位置出现时可能显示重复项。

### 方式二：让 Codex 安装

直接在 Codex 中发送：

```text
使用 $skill-installer 从 https://github.com/ZGarry/project-delivery-report 安装 project-delivery-report。技能位于仓库根目录；如已安装，先保留原版本，再更新。
```

安装器可使用根目录参数 `--repo ZGarry/project-delivery-report --path . --name project-delivery-report`；具体脚本路径由所在环境提供。新安装后开始下一轮使用；若技能列表尚未出现，重启 Codex。已有同名目录时安装器会停止，避免静默覆盖。

### 方式三：Git 安装，便于后续更新

以下以全新 Codex 用户全局安装为例；已有同名目录时不要重复 clone。

Windows PowerShell：

```powershell
$skillDir = Join-Path $env:USERPROFILE '.agents\skills\project-delivery-report'
New-Item -ItemType Directory -Force (Split-Path $skillDir) | Out-Null
git clone https://github.com/ZGarry/project-delivery-report.git $skillDir
```

macOS / Linux：

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/ZGarry/project-delivery-report.git ~/.agents/skills/project-delivery-report
```

### 更新已有安装

- 通过 Git 安装且没有本地修改：在原安装目录执行 `git pull --ff-only`。存在本地修改或分支分叉时先保存、核对差异，不使用强制重置。
- 通过 ZIP 或分发脚本安装：先把旧版本另存为备份，再下载新版到新的临时目录，核对后替换技能文件；本地定制、报告和证据单独保留。
- 项目有受控 skills 分发机制时，沿用其同步流程。GitHub 更新不等于其他机器或已运行任务自动更新。

### 安装后怎么用

在对话中输入：

```text
使用 $project-delivery-report 汇报本次交付：提供成果入口、实际结果、验收证据、重要缺口和下一步。大需求生成可打开的网页，小改动简短汇报。
```

此 skill 不依赖额外 API Key。可选结构化工具需要 Python 3.10+，基础汇报规则无需执行该工具。

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
