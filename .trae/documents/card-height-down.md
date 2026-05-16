# 全渠道 / 平台卡片 — 向下增高

## 约束

- `.summary-grid` 上方有 `padding-top: 36px`，再上是"北京时间"行
- Grid 使用 `align-items: stretch`，各卡片高度自动对齐
- 增高只能向下（增加 bottom padding），不能动 top

## 改动

| 规则 | 当前 `padding` | 改为 |
|------|--------------|------|
| `.total-card` | `18px 24px 20px` | `18px 24px 28px` |
| `.platform-summary-card` | `14px 16px 12px` | `14px 16px 20px` |

仅改 bottom padding，内容自然下沉，顶部位置不变。

## 文件

| 文件 | 变更 |
|------|------|
| `frontend/styles.css` | 两处 padding-bottom 值 |

前端 JS / 后端 零改动。

## 风险

- L1：纯 UI padding 微调
