# 步骤1会话列表按最新店铺配置对齐 Spec

## Why
当前采集配置页“步骤 1. 选择当前任务页面”里的“当前店铺 Edge 会话”下拉框直接展示全部 `edge_sessions`，看起来像旧版固定列表，和用户当前在 `shops.csv / shops_default.json` 中填报的最新店铺集合不完全一致。需要把步骤 1 的会话选择收敛到“当前任务 + 最新店铺配置”语义，避免误选旧会话，同时不影响已跑通的采集链路。

## What Changes
- 将步骤 1 的会话候选从“全部非默认 Edge 会话”调整为“基于最新店铺配置与当前任务的受控候选”。
- 当前任务对应的 `edge_session_id` 作为首选会话；若与最新店铺配置映射不一致，给出明确提示并允许受控回退。
- 对不在当前店铺配置中的历史/遗留会话，在步骤 1 下拉框中默认隐藏或降级提示，不再作为主候选。
- 增加会话候选来源与匹配原因展示，帮助用户理解“为什么当前店铺默认指向这个会话”。
- 保持任务管理、Edge 启动/显示、OCR 与调度主链路不变，并补充冒烟测试覆盖“最新版店铺配置驱动”的步骤 1 行为。

## Impact
- Affected specs: 采集配置工作台步骤 1 会话选择、店铺配置与 Edge 会话映射、绑定工作台提示逻辑
- Affected code:
  - `frontend/edge.js`
  - `frontend/config.js`
  - `frontend/core.js`
  - `frontend/index.html`
  - `backend/main.py`
  - `backend/services/store.py`
  - `backend/services/shop_config.py`

## ADDED Requirements
### Requirement: 步骤1会话列表基于最新店铺配置
系统 SHALL 让采集配置页步骤 1 的会话候选优先依据最新 `shops.csv / shops_default.json` 生成的店铺配置，而不是直接平铺全部历史 Edge 会话。

#### Scenario: 当前任务存在最新店铺映射
- **WHEN** 用户进入某个当前任务的采集配置页
- **THEN** 步骤 1 默认选中该任务在最新店铺配置中对应的 `edge_session_id`
- **AND** 下拉框优先展示该任务对应会话，并按最新店铺配置语义展示名称

#### Scenario: 历史会话不在最新店铺配置中
- **WHEN** 数据库里仍存在历史 Edge 会话，但该会话不属于当前最新店铺配置
- **THEN** 步骤 1 不应把该会话作为当前任务的主候选
- **AND** 系统应提供明确提示，而不是让用户误以为这仍是当前店铺应选会话

### Requirement: 当前任务与会话映射可解释
系统 SHALL 在步骤 1 提示区明确说明当前默认会话来自哪里，以及是否与最新店铺配置一致。

#### Scenario: 会话映射一致
- **WHEN** 当前任务的 `edge_session_id` 与最新店铺配置一致
- **THEN** 提示区说明该会话为“当前店铺最新配置对应会话”

#### Scenario: 会话映射不一致
- **WHEN** 当前任务保存的 `edge_session_id` 与最新店铺配置推导结果不一致
- **THEN** 提示区明确说明“当前任务使用旧会话/历史会话”
- **AND** 提供受控回退策略，避免静默切错会话

### Requirement: 旧链路兼容
系统 SHALL 保持现有已跑通链路可继续使用，不因步骤 1 的候选收敛而阻断已保存任务。

#### Scenario: 旧任务仍引用历史会话
- **WHEN** 旧任务仍绑定某个历史 `edge_session_id`
- **THEN** 用户仍可继续查看、重绑和恢复该任务
- **AND** 任务管理与手动重绑入口保持可用

## MODIFIED Requirements
### Requirement: 采集配置步骤1会话选择
步骤 1 的“当前店铺 Edge 会话”从“展示全部店铺会话并手动挑选”调整为“基于当前任务与最新店铺配置给出首选会话，并对非当前配置会话进行收敛或降级提示”。

## REMOVED Requirements
### Requirement: 步骤1默认展示全部非默认 Edge 会话
**Reason**: 会造成旧会话与当前店铺配置混杂，用户难以判断当前任务该选哪一个。  
**Migration**: 改为“当前任务首选会话 + 最新店铺配置候选 + 兼容旧任务回退”的组合策略。
