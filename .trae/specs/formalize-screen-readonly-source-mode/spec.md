# 天猫专享页面只读正式采集模式 Spec

## Why
当前已验证天猫生意参谋大屏 `screen.htm` 中 `overview.json` 的 `payAmt.value` 读取结果正确，但现阶段仍只是测试版面板，未真正进入正式采集链路。该能力在当时只覆盖天猫平台，用户希望把它做成与 OCR 平行可选的正式能力，在采集配置中可直接选择“页面只读”或“OCR识别”，并让页面只读结果真正进入实时看板店铺卡片。

## What Changes
- 在采集配置中新增正式的采集方式选择：`页面只读` 与 `OCR识别` 并行可选。
- 当任务选择 `页面只读` 时，正式采集链路改为在真实页面上下文中持续读取天猫大屏 `payAmt.value`，而不是走 OCR。
- 页面只读模式需要具备“等待大屏就绪后自动开始稳定读取”的能力，用户只需打开网页，无需手动反复操作。
- 页面只读采集结果要写入任务正式运行态，并体现在实时看板的店铺卡片中。
- 保持现有 OCR 链路可继续工作，避免把只读模式硬编码成唯一方案。

## Impact
- Affected specs: 采集配置工作台、采集模式选择、调度器正式采集链路、实时看板店铺卡片、真实 Edge 页面读取
- Affected code:
  - `frontend/index.html`
  - `frontend/config.js`
  - `frontend/edge.js`
  - `frontend/app.js`
  - `frontend/dashboard.js`
  - `frontend/core.js`
  - `backend/main.py`
  - `backend/services/store.py`
  - `backend/services/scheduler.py`
  - `backend/collectors/remote_edge.py`

## ADDED Requirements
### Requirement: 正式采集方式必须支持天猫专享页面只读与 OCR 并行可选
系统 SHALL 在正式采集配置中提供 `页面只读` 与 `OCR识别` 两种可选采集方式，并将选择结果保存到任务配置；其中该 spec 对应的历史页面只读能力仅覆盖天猫规则。

#### Scenario: 用户切换采集方式
- **WHEN** 用户在采集配置中为某个店铺任务选择 `页面只读`
- **THEN** 该任务后续正式采集应走页面只读链路
- **AND** 不再以 OCR 结果作为该任务的正式主值
- **AND** 当用户切回 `OCR识别` 时，系统继续使用原有 OCR 链路

### Requirement: 天猫专享页面只读模式必须在大屏未就绪时自动等待
系统 SHALL 让页面只读任务在真实页面尚未进入天猫大屏时持续等待并重试，而不是直接失败终止。

#### Scenario: 用户已打开业务页但尚未进入大屏
- **WHEN** 任务采集方式为 `页面只读`，且当前真实页面还没有切到 `screen.htm`
- **THEN** 系统显示明确的等待/未就绪状态
- **AND** 继续按受控频率重试读取
- **AND** 一旦页面进入大屏并可读到 `payAmt.value`，系统自动切换为正常采集

### Requirement: 天猫专享页面只读模式必须把 payAmt.value 写入正式任务结果
系统 SHALL 将页面只读模式读取到的天猫 `payAmt.value` 作为任务正式采集值写入运行态，并参与后续看板展示。

#### Scenario: 页面只读读取成功
- **WHEN** 大屏 `overview.json` 返回有效 `payAmt.value`
- **THEN** 系统更新该任务的正式最新值、采样时间、原因说明和状态
- **AND** 实时看板店铺卡片展示的数值与该正式值保持一致

### Requirement: 实时看板必须能区分当前任务的数据来源
系统 SHALL 在任务或看板维度保留当前采集值的数据来源，便于用户确认该店铺当前走的是页面只读还是 OCR。

#### Scenario: 页面只读任务进入正常采集
- **WHEN** 某店铺任务当前采用 `页面只读`
- **THEN** 系统在合适位置显示该值来源于页面只读
- **AND** 不得让用户误以为该值仍然来自 OCR

### Requirement: 页面只读模式必须遵守低风险边界
系统 SHALL 仅在真实已登录页面上下文内读取 `screen.htm` 数据，不做浏览器外接口重放。

#### Scenario: 正式读取大屏值
- **WHEN** 页面只读模式运行
- **THEN** 所有读取动作都发生在真实 Edge 页面的上下文内
- **AND** 不复制 Cookie/Token 到浏览器外独立重放

## MODIFIED Requirements
### Requirement: 正式采集链路
系统从“正式采集结果主要由 OCR 链路产出”调整为“正式采集结果可由页面只读或 OCR 任一配置链路产出”。任务以自身配置的采集方式为准，调度器、任务状态和看板展示都必须遵守该选择。

### Requirement: 采集配置工作台的数据源测试能力
系统从“仅提供大屏只读测试面板”调整为“在保留测试可视化的基础上，支持把页面只读配置为正式采集方式”，但仍需保留必要的提示和状态说明，避免用户误把未就绪状态当成采集故障。

## REMOVED Requirements
### Requirement: 大屏只读仅限测试展示
**Reason**: 用户已确认只读值正确，希望将其升级为正式可选的数据源。  
**Migration**: 将测试版只读能力升级为正式采集方式；页面展示记录可保留用于调试，但正式值应进入任务运行态和实时看板。
