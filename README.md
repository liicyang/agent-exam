# 素材审核与发布排期 Agent

题号：1。帮助内容团队审核合成素材、处理排期冲突，并保存可确认的排期草稿。**不接入真实发布**。

## 当前验证状态

离线验收 8/8、真实 DeepSeek 验收 8/8、自动化测试 19/19 通过。真实模型为 deepseek-flash，记录见 `examples/real/report.json`。保留首次参数错误记录与改进过程；一次验收通过不代表所有输入均可靠。Mock 仅验证流程，不作为真实模型决策效果证据。

## 环境和快速运行

Python 3.7+，仅标准库；本机验证版本 Python 3.7.4。无需 pip 依赖、MySQL 或独立 SQLite 服务。建议新环境使用 Python 3.11+。全部命令从仓库根目录执行。

```powershell
python -m src.evaluate --mode mock
python -m unittest discover -s tests -v
python -m src.cli --input examples/inputs/conflict.json --mode mock --output examples/manual-conflict.json
```

最后一条应返回 needs_confirmation，建议 19:00，未保存、未发布。CLI 每次接受一个素材请求；多个素材分别执行，以避免部分成功状态含糊。

## 使用真实 DeepSeek

复制 `.env.example` 为 `.env`（已有文件请勿覆盖），在本机编辑填入密钥。`.env` 已被 Git 忽略。

```text
DEEPSEEK_API_KEY=填写自己的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

```powershell
python -m src.cli --input examples/inputs/conflict.json --mode real --output examples/real/smoke-conflict.json
python -m src.evaluate --mode real
```

真实验收会调用付费 API，多步执行；每个模型请求超时 45 秒，每次任务最多 10 步，不自动重试。模型名可通过环境变量修改。模型不可用时明确失败，不偷偷切换 Mock。正式提交前检查 `examples/real/report.json` 和各 Trace，更新评估文档。

## 用户确认与重复提交

请求字段：`request_id`（幂等键）、`material_id`、`requested_slot`；可选 `confirmed_slot` 是用户明确批准的新时间，不能由模型生成授权。演示日期均采用北京时间、精确到分钟，输入格式 `YYYY-MM-DDTHH:MM`。

发生冲突后，由用户确认，将同一请求加入 `confirmed_slot` 再执行。查看 `examples/inputs/confirmed.json`。相同请求和同一时段重复保存返回同一个草稿；已保存请求改变内容会返回 `idempotency_conflict`，新任务应使用新 ID。

```powershell
python -m src.cli --input examples/inputs/confirmed.json --mode mock
python -m src.cli --input examples/inputs/confirmed.json --mode mock
python -m src.cli --input examples/inputs/save_failure.json --mode mock --fail-save --db failure-demo.db
```

本地草稿默认存在 `drafts.db`，不进 Git。该演示将草稿占用时段视为排期占用。评估器使用隔离临时库，不受手动运行残留数据影响。CLI 的 failed/incomplete 返回退出码 1，业务成功或等待用户输入返回 0。

## 评审入口

- `src/agent.py`：有界模型决策循环及基于工具证据的结果汇总。
- `src/models.py`：真实 JSON 动作选择；单独标注的离线替身。
- `src/tools.py`：素材读取、规则检查、时段查询、事务性草稿保存。
- `tests/`：验收和越权/虚报/幂等边界测试。
- `examples/mock/report.json`、`examples/mock/tests.txt`：实际离线验证结果；逐用例 JSON 含输入、输出、Trace 和故障注入条件。
- `docs/01-requirements.md` 至 `docs/05-retrospective.md`：需求、设计、评估、AI 使用和复盘。

## 提交

仓库：https://github.com/liicyang/agent-exam

最终提交题号 1、仓库 URL 和 `git rev-parse HEAD` 返回的完整 SHA。检查评审账号能访问。不要提交 `.env`、真实素材或考试原始文档。实际耗时、个人验证和学习记录须本人据实补全。
