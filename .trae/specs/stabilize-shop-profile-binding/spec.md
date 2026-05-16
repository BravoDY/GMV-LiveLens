# 店铺 Profile 绑定稳定化 Spec

## Why
当前项目的店铺任务默认使用独立 Edge Profile，本身并非不会保存登录态；问题在于服务初始化会按 `shops.csv` 重新推导并回写店铺会话的 `session_mode` 与 `user_data_dir`，导致店铺改名、会话切换或手动改为真实环境后，任务可能悄悄指向新的资料目录，表现为“每次启动都要重新登录”。本次方案以最小风险为原则，优先修复“绑定不稳定”和“启动覆盖”两类根因，不改变现有 OCR、调度和独立多店铺采集主链路。

## What Changes
- 保持“每店铺默认独立 Profile”的现有架构，不改成所有任务共用真实 Edge。
- 为店铺会话引入稳定绑定策略：已有店铺一旦绑定过 Profile 目录，后续同步 `shops.csv` 时默认复用原绑定，而不是仅凭最新店铺名重新生成目录。
- 调整启动/初始化同步逻辑：对已存在的店铺会话，不再无条件覆盖用户已确认的 `session_mode` 和 `user_data_dir`。
- 在任务管理或会话详情接口中暴露“当前实际使用的会话模式、会话 ID、Profile 路径、绑定来源”，让用户能直接看见当前任务到底用的是哪个登录态目录。
- 当检测到“同一店铺存在历史目录与新推导目录不一致”时，提供明确诊断信息；最小风险方案下优先提示，不做静默迁移。
- 补充关闭/重启 Edge 后的登录态保留冒烟验证，确认修复不会破坏已有单店铺和多店铺链路。

## Impact
- Affected specs: 店铺配置同步、Edge 会话持久化、任务与会话绑定、会话诊断展示
- Affected code:
  - `backend/services/store.py`
  - `backend/services/shop_config.py`
  - `backend/main.py`
  - `backend/collectors/remote_edge.py`
  - `frontend/edge.js`
  - `frontend/config.js`

## ADDED Requirements
### Requirement: 店铺 Profile 绑定稳定复用
系统 SHALL 在店铺已存在历史会话绑定时，优先复用原有 `edge_session_id / user_data_dir`，避免因为 `shops.csv` 中店铺名、展示名或排序变化而静默切换到新的 Profile 目录。

#### Scenario: 店铺名称调整但仍是同一店铺
- **WHEN** 用户更新 `shops.csv` 中的店铺名称或展示文案，但该店铺仍可识别为同一业务实体
- **THEN** 系统继续沿用原先已绑定的会话和 Profile 目录
- **AND** 任务再次启动 Edge 时仍复用原登录态

#### Scenario: 首次新增店铺
- **WHEN** `shops.csv` 中出现一个从未绑定过的新店铺
- **THEN** 系统为该店铺创建新的独立 `edge_session_id` 和 `user_data_dir`
- **AND** 不影响其他已存在店铺的 Profile 绑定

### Requirement: 启动同步不覆盖用户已确认配置
系统 SHALL 在初始化或同步店铺会话时，仅补齐缺失字段或创建新会话，不得无条件覆盖已有会话的 `session_mode` 和 `user_data_dir`。

#### Scenario: 用户已手动切换到真实个人环境
- **WHEN** 某店铺会话已被用户手动设置为 `real_profile`
- **THEN** 后续服务启动或同步店铺配置时，不应自动改回 `isolated`
- **AND** 不应把 `user_data_dir` 静默改写为新的独立目录

#### Scenario: 已存在独立店铺目录
- **WHEN** 某店铺会话已存在有效的独立 `user_data_dir`
- **THEN** 后续同步时继续保留该目录
- **AND** 只有在用户明确执行重绑或迁移操作时才允许变更

### Requirement: 当前任务使用的登录态目录可见
系统 SHALL 让用户能够直接看到当前任务实际使用的会话模式、会话 ID 和 Profile 路径，以便快速判断“登录态是否复用到了正确目录”。

#### Scenario: 打开任务会话详情
- **WHEN** 用户查看任务管理页、会话详情或 Edge 诊断信息
- **THEN** 界面或接口返回当前 `session_mode`、`edge_session_id`、`user_data_dir`
- **AND** 同时说明该绑定来自“历史复用”“首次创建”或“用户手动指定”

### Requirement: 目录不一致时提供可解释诊断
系统 SHALL 在发现“历史目录”和“按最新店铺名推导的新目录”不一致时，给出明确诊断提示，而不是静默切换。

#### Scenario: 检测到新旧目录都存在
- **WHEN** 系统发现同一店铺已有历史 Profile 目录，同时按最新规则还能推导出另一个新目录
- **THEN** 系统保留当前生效绑定
- **AND** 返回可见诊断，提示存在可迁移但未自动切换的目录差异

## MODIFIED Requirements
### Requirement: 店铺配置同步
店铺配置同步从“按最新 `shops.csv` 推导结果直接覆盖会话记录”调整为“先识别是否已有稳定绑定；已有绑定则保留原 `session_mode` 与 `user_data_dir`，仅对新增店铺创建默认独立会话，对缺失字段做补齐”。

### Requirement: 店铺会话命名与目录生成
店铺会话的默认生成规则仅用于首次建档和兜底，不再作为后续每次启动都强制重写目录绑定的依据。

## REMOVED Requirements
### Requirement: 启动时无条件按最新店铺名重写会话模式和目录
**Reason**: 会导致任务静默切换到新 Profile 目录，破坏登录态连续性，并制造“每次都要重新登录”的表象。  
**Migration**: 改为保留历史绑定并补充来源说明；若后续需要切换目录，必须通过显式重绑或迁移操作完成。
