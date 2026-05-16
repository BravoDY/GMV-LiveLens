# Tasks
- [x] Task 1: 复盘店铺会话同步与登录态丢失根因边界
  - [x] SubTask 1.1: 梳理 `shops.csv -> load_shop_configs() -> init_db() -> _ensure_shop_edge_sessions()` 的完整同步链路。
  - [x] SubTask 1.2: 明确哪些字段属于“首次建档默认值”，哪些字段属于“用户已确认的持久绑定”，避免修复时误伤现有任务。
  - [x] SubTask 1.3: 确认最小风险边界：不改变多店铺独立 Profile 架构、不删除历史目录、不自动迁移目录。

- [x] Task 2: 实现店铺会话稳定绑定策略
  - [x] SubTask 2.1: 调整店铺会话同步逻辑，让已有会话优先复用现有 `edge_session_id`、`session_mode`、`user_data_dir`。
  - [x] SubTask 2.2: 让默认 `platform + shop_name` 规则仅用于新增店铺首次创建，不再作为后续强制覆盖依据。
  - [x] SubTask 2.3: 为“历史绑定目录”和“新推导目录”不一致的情况补充可解释的诊断字段或返回信息。

- [x] Task 3: 保护用户手动选择的会话模式与目录
  - [x] SubTask 3.1: 修复启动/初始化阶段对 `session_mode=real_profile` 的误覆盖风险。
  - [x] SubTask 3.2: 修复已有独立 `user_data_dir` 在同步时被静默改写到新目录的风险。
  - [x] SubTask 3.3: 保证旧任务、任务管理、Edge 启动/显示/关闭链路继续读取最终保留的绑定结果。

- [x] Task 4: 增加当前任务实际 Profile 绑定的可见性
  - [x] SubTask 4.1: 在后端任务/会话返回结构中补充当前 `edge_session_id`、`session_mode`、`user_data_dir` 与绑定来源。
  - [x] SubTask 4.2: 在前端任务管理或会话诊断区域展示当前实际使用的 Profile 路径与模式说明。
  - [x] SubTask 4.3: 当发现目录差异时，给出“保留当前绑定、未自动迁移”的明确提示。

- [x] Task 5: 做最小风险回归验证
  - [x] SubTask 5.1: 通过临时数据库脚本验证同一店铺在服务重启和会话重建后继续复用原绑定目录；未触碰真实店铺登录环境。
  - [x] SubTask 5.2: 场景 B：店铺名称调整后，系统仍复用原会话目录，不要求重新登录。
  - [x] SubTask 5.3: 场景 C：手动切到 `real_profile` 的店铺会话在重新启动后不会被改回 `isolated`。
  - [x] SubTask 5.4: 场景 D：诊断界面/接口能看到当前任务实际使用的会话模式、会话 ID、Profile 路径与绑定来源。
  - [x] SubTask 5.5: 执行诊断与必要冒烟，确认未破坏现有多店铺、OCR、预览与调度链路。

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 2, Task 3 and Task 4
