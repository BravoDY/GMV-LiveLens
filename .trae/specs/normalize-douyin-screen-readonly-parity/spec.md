# 抖音大屏只读规范收口 Spec

## Why
当前抖音“大屏只读”链路虽然已经可读到目标金额，但平台支持名单、只读状态口径和正式调度节奏仍分散在多个模块中，存在与天猫、京东、唯品会不完全一致的风险。需要把抖音只读能力补齐到同一规范层级，并明确抖音正式只读轮询固定为 1 秒。

## What Changes
- 审查并收口抖音大屏只读链路的实现边界，确保与天猫、京东、唯品会使用统一的平台支持判断和返回字段口径
- 固化抖音单店大屏 `screen/shop/single` 的目标指标为 `今日用户支付金额(含异常交易)`
- 统一抖音大屏只读在后端正式采集链路中的等待态、成功态、失败态与 reason code 口径
- 将抖音 `screen_readonly` 正式采集轮询收口为固定 `1 秒`
- 明确前端 WebSocket 失败兜底轮询不属于抖音业务轮询，本次不调整该全局降级节奏

## Impact
- Affected specs: `add-screen-readonly-payamt-mode`, `add-jd-screen-readonly-support`, `add-vip-screen-readonly-support`
- Affected code: `backend/collectors/remote_edge.py`, `backend/services/scheduler.py`, `backend/main.py`, `frontend/config.js`

## ADDED Requirements
### Requirement: 抖音大屏只读平台规范
系统 SHALL 将抖音纳入与天猫、京东、唯品会同层级的正式 `screen_readonly` 平台支持能力，且各模块对白名单判断保持一致。

#### Scenario: 平台支持判断一致
- **WHEN** 用户把抖音任务保存为 `screen_readonly`
- **THEN** 前端配置校验、后端只读接口、正式调度采集都必须一致地判定“抖音已支持”

#### Scenario: 旧模块不再残留旧白名单
- **WHEN** 系统执行抖音任务的只读测试或正式采集
- **THEN** 不应出现某一层判定“支持”、另一层仍判定“未配置平台规则”的不一致结果

### Requirement: 抖音目标指标只读口径
系统 SHALL 在抖音单店大屏 `https://compass.jinritemai.com/screen/shop/single` 中只读取 `今日用户支付金额(含异常交易)` 作为正式采集值。

#### Scenario: 成功读取目标指标
- **WHEN** 当前绑定页已经进入抖音单店大屏，且目标区域已渲染
- **THEN** 系统返回的 `metric_label` 必须是 `今日用户支付金额(含异常交易)`
- **THEN** 返回的 `pay_amt` 必须来自该指标，而不是左侧其它相似金额

#### Scenario: 页面已打开但目标区域未就绪
- **WHEN** 抖音单店大屏已打开，但目标指标区域尚未渲染或未能取值
- **THEN** 系统进入等待态或未就绪态，并返回抖音专属 reason code 与提示文案

### Requirement: 抖音只读返回结构统一
系统 SHALL 让抖音只读结果与天猫、京东、唯品会遵循统一的结构化返回规范。

#### Scenario: 返回字段完整
- **WHEN** 调用抖音页面只读接口
- **THEN** 返回结构必须包含 `ready`、`status`、`reason_code`、`message`、`pay_amt`、`captured_at`、`update_time`、`interval_seconds`、`source_url`、`metric_label`、`platform_key`、`value_source`

#### Scenario: 平台字段统一
- **WHEN** 抖音只读成功或失败
- **THEN** `platform_key` 必须稳定返回 `抖音`
- **THEN** `value_source` 必须稳定返回 `screen_readonly`

### Requirement: 抖音正式只读轮询频率
系统 SHALL 将抖音 `screen_readonly` 正式采集轮询频率固定为 `1 秒`，并与全局前端降级轮询区分开。

#### Scenario: 抖音正式任务进入只读调度
- **WHEN** 抖音任务被保存为 `screen_readonly` 且处于启用状态
- **THEN** 调度器下一次正式只读采样间隔必须按 `1 秒` 计算

#### Scenario: 不误改前端全局降级轮询
- **WHEN** 实现抖音 1 秒业务轮询
- **THEN** 不应把前端 WebSocket 失败后的全局 HTTP 兜底轮询节奏误改为抖音专属逻辑

## MODIFIED Requirements
### Requirement: 多平台大屏只读正式链路
系统 SHALL 以统一规范支持天猫、京东、唯品会、抖音四个平台的大屏只读正式采集；每个平台可以有独立目标页和独立指标，但平台支持判断、返回结构、状态语义和正式值写入口径必须统一。

#### Scenario: 多平台规则并存
- **WHEN** 系统同时处理天猫、京东、唯品会、抖音的大屏只读任务
- **THEN** 各平台应按各自页面规则读取目标值
- **THEN** 共享统一的正式运行态写入结构和状态展示口径

#### Scenario: 平台扩展可维护
- **WHEN** 后续继续新增其它平台大屏只读规则
- **THEN** 新平台应复用统一框架接入，而不是在不同模块重复维护不一致的平台支持名单
