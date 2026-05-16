# Edge 会话隔离实库审计 Spec

## Why
当前需要直接针对真实数据库与现有会话配置做一次实库审计，确认哪些店铺已经出现 Profile 目录共用、目录漂移或落到 `real_profile` 的情况，以判断多店铺并行时的真实隔离风险。

## What Changes
- 增加一次只读实库审计流程，对 `edge_sessions`、`capture_tasks`、店铺配置与默认推导目录进行逐店核对
- 输出逐店审计结果，明确标记“共用目录”“漂移目录”“real_profile 落点”“正常隔离”
- 给出每项结果的证据链，包括 session_id、debug_port、user_data_dir、绑定来源与差异说明
- 不修改数据库、不自动迁移目录、不自动修复配置

## Impact
- Affected specs: Edge 会话隔离诊断、店铺 Profile 审计、运行态风险识别
- Affected code: `data/gmv_livelens.sqlite3`、`data/shops_default.json`、`backend/services/store.py`、`backend/services/shop_config.py`

## ADDED Requirements
### Requirement: 实库逐店会话隔离审计
系统 SHALL 提供一次基于当前真实数据库与现有会话配置的逐店隔离审计，并输出每家店的实际会话模式与 Profile 目录状态。

#### Scenario: 审计当前店铺会话
- **WHEN** 触发实库审计
- **THEN** 系统逐店列出 `platform`、`shop_name`、`edge_session_id`、`debug_port`、`user_data_dir`、`session_mode`
- **AND** 对每家店标记是否为“正常隔离”“共用目录”“目录漂移”或“落到 real_profile”

### Requirement: 目录共用识别
系统 SHALL 识别两个或以上店铺会话是否指向同一个非空 `user_data_dir`，并将其标记为目录共用风险。

#### Scenario: 两家店共用同一目录
- **WHEN** 审计发现多个不同 `session_id` 或不同店铺指向同一非空 `user_data_dir`
- **THEN** 结果中明确列出所有相关店铺
- **AND** 标记为“共用目录”

### Requirement: 目录漂移识别
系统 SHALL 将当前会话目录与按现有店铺配置推导的期望目录进行对比，并标记不一致情况。

#### Scenario: 当前目录与期望目录不一致
- **WHEN** 店铺当前 `user_data_dir` 与按当前配置推导出的目录不同
- **THEN** 结果中标记为“目录漂移”
- **AND** 输出当前目录、期望目录和绑定来源

### Requirement: real_profile 落点识别
系统 SHALL 识别哪些店铺任务或会话当前落在 `real_profile` 模式，并明确列出风险范围。

#### Scenario: 店铺使用真实个人环境
- **WHEN** 审计发现某店铺会话或任务绑定到 `session_mode=real_profile`
- **THEN** 结果中标记该店铺为“落到 real_profile”
- **AND** 说明其不具备项目级独立资料目录隔离

## MODIFIED Requirements
### Requirement: Edge 会话诊断输出
现有会话诊断从“只展示当前单条会话信息”扩展为“可用于逐店实库审计和跨店对比的证据集合”，但仍保持只读。

## REMOVED Requirements
### Requirement: 审计过程中自动修复异常绑定
**Reason**: 本次目标是先查清真实现状，避免在未确认风险前改写真实登录态或目录绑定。  
**Migration**: 审计结果输出后，再决定是否单独做修复规格与最小改动方案。
