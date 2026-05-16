# 刷新后绑定恢复增强 Spec

## Why
当前系统在前端刷新后会重新校验绑定，若运行时 `page_id` 失效且未自动命中唯一候选页，就会进入“需重绑”流程，影响连续使用体验。需要在不破坏已跑通链路的前提下，将“刷新即重绑”降为“刷新后自动恢复，仅不确定时人工介入”。

## What Changes
- 增强后端绑定自愈：在读取任务与候选页签流程中，优先执行轻量 `reconcile + auto_restore`，自动修复失效 `page_id`。
- 增强前端刷新恢复：持久化最小 UI 上下文（当前配置任务、最近会话），刷新后自动回填并触发候选页预加载。
- 严格安全边界：仅在“唯一高置信候选”时自动改绑；候选不唯一时保持人工确认，禁止盲绑。
- 增加可观测性与回退策略：补充恢复原因与日志字段，便于排障与快速回退。
- 完成全链路冒烟测试（启动/显示 Edge、刷新页面、页签变更、重连、调度采集）并记录结果。

## Impact
- Affected specs: 采集配置工作台绑定恢复、Edge 会话页签恢复、刷新后无感继续操作能力
- Affected code:
  - `backend/main.py`
  - `backend/services/store.py`
  - `frontend/core.js`
  - `frontend/config.js`
  - `frontend/app.js`

## ADDED Requirements
### Requirement: 刷新后无感恢复绑定
系统 SHALL 在前端刷新后自动恢复最近操作上下文，并优先尝试恢复有效页签绑定。

#### Scenario: 刷新后恢复成功
- **WHEN** 用户刷新页面且目标页签仍可通过唯一候选匹配
- **THEN** 系统自动恢复 `page_id` 并进入可继续预览/采集状态
- **AND** 用户无需手动重新绑定

#### Scenario: 刷新后恢复不确定
- **WHEN** 用户刷新页面但候选页签存在多个同分候选或无高置信候选
- **THEN** 系统进入人工确认流程并明确提示“需人工重绑”
- **AND** 不得自动选择任何候选页签

### Requirement: 运行时句柄失效自愈
系统 SHALL 将 `page_id` 视为运行时句柄，并在句柄失效时用 `target_page_url/page_url/page_title` 进行可控重挂载。

#### Scenario: 句柄失效但可唯一恢复
- **WHEN** 任务记录 `page_id` 已失效，且匹配算法仅命中一个高置信候选
- **THEN** 自动更新任务绑定字段（`page_id/page_url/page_title/status`）并继续运行

### Requirement: 稳态优先与兼容保护
系统 SHALL 保持现有已跑通链路不变，不引入破坏性迁移。

#### Scenario: 旧流程兼容
- **WHEN** 自动恢复逻辑未命中
- **THEN** 保持现有手动重绑入口与行为可用
- **AND** 调度采集、OCR、任务管理等既有流程不被阻断

## MODIFIED Requirements
### Requirement: 页面绑定恢复入口
系统从“仅在手动操作时恢复绑定”调整为“读取与配置流程中优先轻量自愈，再决定是否人工重绑”，但自动恢复必须满足唯一高置信命中。

## REMOVED Requirements
### Requirement: 刷新后仅依赖旧 `page_id` 判断可用性
**Reason**: `page_id` 是运行时句柄，单点依赖会导致刷新后高频误判失效。  
**Migration**: 改为 `page_id` 快速命中 + URL/标题多信号恢复的组合策略，失败时回退人工确认。
