# 效果评估

## 已执行：离线验证

命令：`python -m src.evaluate --mode mock`。8/8 业务场景通过；19/19 自动化测试通过。实际记录见 `../examples/mock/report.json` 与 `../examples/mock/tests.txt`。环境 Python 3.7.4，Windows。接口适配测试替换 HTTP 传输，检查观察结果进入请求及 JSON 响应解析，不属于真实网络验证。

| 验收点 | 输入 | 预期与实际结果 | 运行记录 |
| --- | --- | --- | --- |
| 正常排期 | M01，19:00 | saved，一份草稿 | ../examples/mock/normal.json |
| 信息缺失 | M02，无版权字段 | missing_information，无草稿 | ../examples/mock/missing_information.json |
| 规则风险 | M03，版权未知且审核拒绝 | blocked，无草稿 | ../examples/mock/risk.json |
| 时段冲突 | M01，18:00 已占用 | needs_confirmation，建议 19:00，不保存 | ../examples/mock/conflict.json |
| 保存失败 | 注入存储错误 | failed，零行数据 | ../examples/mock/save_failure.json |
| 用户确认 | 用户确认 19:00 | saved | ../examples/mock/confirmed.json |
| 重复提交 | 同请求连续执行两次 | 同一草稿，duplicate=true，总行数 1 | ../examples/mock/repeat_first.json 与 repeat.json |
| 修改占用 | 18:00、19:00 均占用 | 建议随之变成 20:00 | ../examples/mock/changed_occupancy.json |

各 JSON 包含 request、最终输出、每一步参数/返回值/简短依据，以及实际使用的 catalog 和故障开关。所有时段是独立合成演示数据。

测试另覆盖：未知素材、请求字段缺失、同 ID 修改内容、无可用时段、两个请求占用同一时段、步数耗尽、模型错误脱敏、模型虚报成功。不同连接的顺序竞争已测；多进程并发压测未做。

## 已执行：真实模型验收

2026-11-05 使用 DeepSeek 官方 API、deepseek-flash，执行 `python -m src.evaluate --mode real`，8/8 场景通过。实际汇总见 `../examples/real/report.json`，每个用例的 JSON 与上表同名，位于 `../examples/real/`。重复提交包含 repeat_first.json 和 repeat.json 两次实际运行。

实际 normal 路径读取、审核、查询后保存并观察成功结果；conflict 路径观察 18:00 占用后返回待确认、建议 19:00，未保存；changed_occupancy 在额外占用 19:00 后建议 20:00。save_failure 观察存储故障后明确失败，零草稿。每一步 action 均由远端模型返回，运行时仅执行工具与结果校验。

首次 smoke 调用失败：模型额外传入 material_id，与零参数工具不符，重复后结束。原记录见 initial-argument-failure.json（smoke-conflict.json 为同次原始输出）。改进是明确提示参数必须为 {}，错误反馈返回 expected_arguments，并新增测试。不放宽请求身份约束，不隐藏失败。该旧版本把此类结束报告为 incomplete；现已补充“有真实工具错误证据时允许 failed”的汇总规则。

本轮为单次固定场景评估，不是统计性成功率评测；未报告多次独立重复的模型稳定性。

限制：合成规则不识别真实视频风险；固定时间槽不表达时长；未实现多用户身份认证、取消草稿、生产故障恢复。实时模型可能产生非法 JSON、错误参数或过早停止，均需真实验收进一步观察。
