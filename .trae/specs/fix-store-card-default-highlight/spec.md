# 店铺卡片默认高光修复 Spec

## Why
当前店铺卡片顶边在未发生 GMV 变化时也呈现明显高光，造成“常亮像在闪烁”的误判。需要恢复“默认克制、变化时明显”的视觉语义。

## What Changes
- 下调店铺卡片顶边默认样式亮度，去除默认态的强白色高光中心与强发光。
- 保留 GMV 变化触发逻辑，仅在 `is-flashing` 状态下展示明显渐变扫光。
- 保持平台汇总卡与总卡动效不变，避免本次修复扩大影响范围。

## Impact
- Affected specs: 实时看板店铺卡片高亮反馈
- Affected code: `frontend/styles.css`, `frontend/dashboard.js`

## ADDED Requirements
### Requirement: 默认态不误报高亮
系统 SHALL 在店铺 GMV 未变化时保持顶边为低干扰常态样式，不应出现明显扫光效果。

#### Scenario: 未变化状态
- **WHEN** 实时看板首次加载且某店铺 GMV 与上次值一致
- **THEN** 店铺卡片顶边仅显示基础平台色，不出现高亮扫光主视觉

### Requirement: 变化态高亮可感知
系统 SHALL 在店铺 GMV 发生变化时触发一次可感知的顶边渐变扫光。

#### Scenario: 变化触发
- **WHEN** 某店铺当前 GMV 值与上一帧不同
- **THEN** 该店铺卡片添加 `is-flashing` 并播放明显顶边扫光动画
- **AND** 其他未变化店铺不触发扫光

## MODIFIED Requirements
### Requirement: 店铺卡片顶边视觉层级
店铺卡片顶边视觉层级调整为“默认态弱、变化态强”，其中默认态仅承担品牌识别，动态态承担变更提醒。

## REMOVED Requirements
### Requirement: 默认态高亮中心常驻
**Reason**: 会导致用户把静态样式误认为动态告警。  
**Migration**: 将高亮中心与强发光仅保留在 `is-flashing` 动画关键帧中。
