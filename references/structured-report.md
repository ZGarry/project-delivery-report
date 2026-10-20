# 结构化报告契约 v1

Python 3.10+，仅标准库，无依赖、网络调用、调度和通知。输入示例见 [合成案例](../examples/partial-delivery.json)；该案例数据为演示构造，不能当作真实业务结果。

## 字段

顶层字段全部必填；不允许未知字段，避免误拼写悄悄失效。

| 字段 | 含义 |
|---|---|
| schema_version | 整数 1 |
| task_id / title / goal | 稳定任务编号、标题、目标 |
| as_of | 带 UTC 偏移的 ISO 时间；如 2026-10-20T10:00:00+08:00 |
| environment / revision | 当前验收环境和确切版本；工具文档任务可用 local-package 与提交/内容版本 |
| status | completed / partial / blocked / failed |
| delivery | code、deployment 各为 verified / unverified / not_applicable |
| acceptance | 非空数组：id、criterion、status、evidence_ids；status 为 passed / failed / unverified / blocked |
| evidence | 数组：id、kind、location、observed_at、environment、revision、summary、collector；所有值非空字符串 |
| outcomes | 数组：claim、basis、evidence_ids；basis 为 observed / estimated / unmeasured |
| metrics | 数组，见下节；无可比数据用 [] |
| blockers | 数组：summary、impact、next_action、severity(normal/critical)、requires_user(布尔) |
| decision | 无决策用 null；否则 question、recommendation、impact、deadline 全部必填 |
| next_step | 下一步与汇报节点；结束可写“本次任务结束，后续业务收益尚待持续观察” |

证据 kind 为 source / build / test / runtime / deployment / business / review。

passed、failed、observed 必须引用当前环境和版本的证据。量化旧新值可引用各自版本的证据。所有引用必须存在，证据时间不得晚于报告。

completed 要求所有验收通过、无阻塞、无待决策、交付状态无 unverified。verified 源码需要当前 source/build/test 证据；verified 部署需要当前 runtime/deployment 证据。环境版本匹配只代表结构一致，不代表证据足以支持具体业务断言，必须人工或由独立验收工具核对。

## metrics

每项含 name、unit、direction(lower/higher)、before、after。两侧都必须含：

- value：有限数值，布尔值不算数值。
- sample_size：正整数；environment、revision、window、statistic、workload：非空字符串。
- evidence_ids：对应侧环境/版本的证据 ID 数组。

environment、statistic、workload 任一不一致时只并列展示，不计算改善率。版本和测量窗口自然可以不同，必须在报告中保留。未建模的硬件、数据分布、并发等条件由调用者放进 workload 并检查；同字符串不能证明条件真实相同。零基线不计算百分比。该工具不做显著性检验和因果推断。

## 调用与返回

```text
python scripts/report.py examples/partial-delivery.json --output digest.md
python scripts/report.py examples/partial-delivery.json --previous examples/partial-delivery.json --output digest.md
python -m unittest discover -s tests -v
```

有效输入退出 0，输出 JSON 中 verification 固定为 structural_only；无效输入退出 1。output 指定时保存摘要，可能覆盖同名文件；调用方为历史快照选择唯一名称。未指定 output 时在 stdout 输出 JSON 及非 quiet 的 Markdown。

attention 是发送建议：

- urgent：存在决策、需用户处理的阻塞或关键异常。
- summary：首次报告或内容有实质变化。
- quiet：同一 task_id 的内容未变化；仅 as_of、证据 observed_at 变化不算实质变化，证据/验收顺序也不影响。

若调用方设置了证据过期、期限提醒和升级策略，应在调用前重新核验并更新状态；脚本不读取时钟，不实现证据 TTL、通知送达或升级。quiet 不能覆盖这些策略。

--previous 必须是同一任务的已保存有效报告，不能拿失败报告伪装历史。脚本既不修改输入，也不保存发送记录。确需发送时，由已获授权的调用方记录指纹、渠道回执、重试次数和去重键；发送失败不得标记已通知。

## 验收限制

链接未打开、文件内容未验证、测试真实性未检查、凭据未扫描。任何人都可以构造一个结构正确的 JSON；不能把脚本的 valid=true 用作独立业务验收。输出按普通文本/Markdown 编写；不应用作处理不可信输入的 HTML 安全过滤器。
