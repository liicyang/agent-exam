# 设计与取舍

## 调用流程

CLI 读请求 → 模型接收任务与已观察 Trace → 模型输出 JSON 动作 → 运行时验证结构并调用白名单工具 → 工具结果加入 Trace → 模型选择下一步或 finish。最多 10 步（CLI 可设 1–30）；超限返回 incomplete。模型异常返回 failed，日志只保存异常类型，不保存 HTTP 响应或密钥。

真实模式每一步重新请求 DeepSeek，模型可补查或结束，不由程序写死成功路径。输出 reason 仅为简短可观察依据，不采集模型内部思维过程。离线 MockModel 的条件分支只用于工具和状态机测试，不当作真实 Agent 证明。

## 工具与安全边界

read_material 读取请求对应素材；check_rules 检查所需字段、版权和审核状态；query_slots 合并已有占用与其他请求的草稿；save_draft 重新检查规则、授权和占用。保存前必须观察前三个工具，否则拒绝。

工具参数不接受新的素材 ID、授权字段或 request_id，避免模型改变请求身份。confirmed_slot 来自可信 CLI 输入；未来 HTTP 接口必须增加身份认证与确认校验。素材内容作为数据，不作为指令。

SQLite 使用 BEGIN IMMEDIATE 在一个事务中检查幂等键和占用并插入。request_id 和 slot 均有唯一约束。相同请求返回旧草稿，不同内容复用 ID 拒绝；保存失败回滚。请求指纹基于规范排序 JSON。当前固定时段被视为不可重叠的单个槽位，未实现任意持续时间区间冲突。

最终状态依赖工具证据，不接受模型无依据声称 saved。输出恒有 published=false，系统根本没有发布工具。未确认替代方案只作为建议，不保存草稿。

## 技术选择

原生 Python，没有 Agent 框架；本项目工具数量少，直接实现循环便于审查授权和状态边界。标准库 urllib 对接 Chat Completions JSON 输出，sqlite3 保存草稿，unittest 验证。零第三方运行依赖。

DeepSeek 配置按官方文档核对：
- https://api-docs.deepseek.com/quick_start/pricing/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/guides/thinking_mode

默认 deepseek-flash，关闭 thinking，仅使用 content JSON，不记录 reasoning_content。实际可用性和决策质量必须通过真实调用验证。
