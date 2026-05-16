# 实时看板双品牌分区重构 Spec

## Why
当前实时看板下半区仍采用单一店铺网格，无法按业务要求区分“大货独立店”和“子品牌独立店”。用户已在 `data/shops.csv` 中通过 `platform`、`shop_name`、`brand` 维护分组关系，因此需要以该配置为唯一数据来源，对看板进行像素级双区域重构。

## What Changes
- 将实时看板下半区从单一 `store-grid` 重构为左右两个品牌区域面板。
- 左侧区域固定承载 `brand=大货独立店` 的店铺，右侧区域固定承载 `brand=子品牌独立店` 的店铺。
- `brand` 的唯一来源为 `data/shops.csv`；前端不再按店铺名称推断主/子身份。
- 当 `brand` 缺失或为非预期值时，店铺默认归入左侧“大货独立店”。
- 顶部 Summary 继续保留“全渠道实时GMV + 各平台实时GMV汇总”，不新增主/子品牌概览卡。
- 店铺卡继续保留平台色、平台角标、GMV、目标、达成进度、进度条、更新时间，以及现有的实时刷新/状态反馈机制。
- 不渲染任何“预留位 / 新增店铺”占位卡。
- 说明书中“主品牌（独立店）/子品牌（店中店）”的标题与兜底逻辑不直接照搬，改为以 `shops.csv` 中实际 `brand` 中文值驱动展示。

## Impact
- Affected specs: 实时看板布局、店铺配置元数据透传、店铺卡片分组渲染
- Affected code:
  - `backend/services/shop_config.py`
  - `backend/main.py`
  - `frontend/core.js`
  - `frontend/dashboard.js`
  - `frontend/index.html`
  - `frontend/styles.css`

## ADDED Requirements
### Requirement: 品牌分区必须由 shops.csv 的 brand 字段驱动
系统 SHALL 从 `data/shops.csv` 读取 `platform`、`shop_name`、`brand`，并将 `brand` 作为实时看板店铺分区的唯一来源。

#### Scenario: brand 字段命中左侧区域
- **WHEN** 某店铺配置的 `brand` 为 `大货独立店`
- **THEN** 该店铺显示在左侧品牌区域
- **AND** 不因店铺名称包含特定关键字而改变分区

#### Scenario: brand 字段命中右侧区域
- **WHEN** 某店铺配置的 `brand` 为 `子品牌独立店`
- **THEN** 该店铺显示在右侧品牌区域
- **AND** 该店铺继续保留原有平台角标与平台色

#### Scenario: brand 缺失或不合法时兜底
- **WHEN** 某店铺配置缺少 `brand`，或其值不是 `大货独立店` / `子品牌独立店`
- **THEN** 该店铺默认归入左侧“大货独立店”
- **AND** 系统不得因该异常值导致该店铺从看板消失

### Requirement: 实时看板下半区必须渲染为双品牌面板
系统 SHALL 将实时看板下半区渲染为左右两个品牌面板，左侧标题为“大货独立店”，右侧标题为“子品牌独立店”。

#### Scenario: 大屏宽度下左右布局
- **WHEN** 页面宽度满足桌面大屏布局阈值
- **THEN** 左右两个品牌面板并排显示
- **AND** 每个品牌面板内部采用两列店铺卡布局

#### Scenario: 窄屏宽度下纵向堆叠
- **WHEN** 页面宽度低于品牌面板双列阈值
- **THEN** 两个品牌面板改为上下排列
- **AND** 每个品牌面板内部店铺卡仍遵守设定的响应式列数

### Requirement: 看板下半区不得渲染占位卡
系统 SHALL 仅渲染真实店铺卡，不渲染“预留位 / 新增店铺”之类的占位卡。

#### Scenario: 渲染品牌区域
- **WHEN** 左右品牌区域完成店铺卡渲染
- **THEN** 页面只展示真实店铺卡
- **AND** 左右两侧都不追加预留位卡片

## MODIFIED Requirements
### Requirement: 实时看板店铺区域展示方式
系统 SHALL 保留顶部 Summary 区域的总 GMV 卡与平台汇总卡，但原先单一的 `store-grid` 店铺网格必须改为基于 `brand` 分组的双品牌面板布局。

#### Scenario: 渲染实时看板
- **WHEN** 前端收到实时任务快照与店铺配置
- **THEN** 顶部继续渲染全渠道总卡和平台汇总卡
- **AND** 下半区不再渲染“统一卡片网格”
- **AND** 下半区改为“大货独立店”与“子品牌独立店”两个区域
- **AND** 不渲染任何占位卡

### Requirement: 品牌标题来源
系统 SHALL 直接使用 `shops.csv` 中实际配置的 `brand` 原文作为区域标题，而不是说明书中的“主品牌/子品牌”文案，也不是由店铺名称推断出的标题。

#### Scenario: 渲染品牌标题
- **WHEN** 看板渲染两个品牌区域标题
- **THEN** 左侧显示 `大货独立店`
- **AND** 右侧显示 `子品牌独立店`
- **AND** 标题直接使用 `brand` 原文，不追加括号副标题

## REMOVED Requirements
### Requirement: 基于店铺名称推断主/子身份
**Reason**: 用户已在 `shops.csv` 中提供稳定的 `brand` 字段，名称猜测会与真实业务分组冲突，尤其不适用于“大货独立店 / 子品牌独立店”的新命名方式。
**Migration**: 前端与后端改为透传并消费 `brand`；缺失或非法值统一兜底到左侧“大货独立店”。

### Requirement: 下半区统一店铺网格标题与布局
**Reason**: 旧版“店铺实时GMV（统一卡片网格）”与目标设计图不一致，无法表达双业务区域。
**Migration**: 使用品牌面板容器替换旧标题和单一 `store-grid` 容器，Summary 区域保持不变。
