# Align Total & Platform Progress Bars Spec

## Why
全渠道卡和平台卡的进度条底部不在同一水平线上。虽然两卡都用了 `margin-top: auto` 推底部容器，但容器内部内容高度不同导致进度条垂直位置不一致，视觉上不整齐。

## What Changes
- `.total-card-bottom` 改为 `display: flex; flex-direction: column`
- `.platform-card-bottom` 改为 `display: flex; flex-direction: column`
- `.total-progress-track` 的 `margin-top: 10px` 改为 `margin-top: auto`
- `.platform-progress-track` 增加 `margin-top: auto`
- `.platform-progress-track` 增加 `overflow: hidden`（与 total 一致）
- `.total-card` 和 `.platform-summary-card` 保持各自的 padding-bottom 不变（已通过 auto 自动对齐）

## Impact
- Affected specs: none (UI-only)
- Affected code: [styles.css](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/styles.css) 3 个规则
- 前端 JS 零改动

## MODIFIED Requirements
### Requirement: Progress Bar Bottom Alignment
The progress tracks in `.total-card` and `.platform-summary-card` SHALL align at their bottom edges.

#### Scenario: Same-height cards
- **WHEN** dashboard renders with one total card and multiple platform cards
- **THEN** all `.platform-progress-track` and `.total-progress-track` bottom edges align on the same horizontal line

#### Scenario: Content push-down
- **WHEN** `.card-bottom` containers grow taller via inner content
- **THEN** progress tracks within them remain at the very bottom via `margin-top: auto`
