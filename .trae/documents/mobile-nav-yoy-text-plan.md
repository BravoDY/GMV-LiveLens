# 移动端导航栏下加入同比文案 — 实施计划

## 需求
在移动端 (≤768px) 导航栏下方，新增同比日期文案显示 (如 `[ 2026/5/18 ]   同比   [ 2025/5/21 ]`)，内容与 PC 端看板内的 `summary-time-row` 保持同步。

---

## 影响范围分析
| 文件 | 改动类型 |
|---|---|
| `frontend/index.html` | 新增 1 个 DOM 元素 |
| `frontend/styles.css` | 新增 PC 端隐藏 + 移动端显示样式；调整 header 布局 |
| `frontend/dashboard-shared.js` | 在 `renderSummaryTimeRow()` 中新增同步逻辑 (3-4 行) |

不涉及后端、HTML 结构变更、JS 逻辑重构。

---

## 现状回顾

### 数据流
```
后端 yoy_date.cur / yoy_date.ly
  → WebSocket 推送 snapshot
    → renderDashboard() 构建 dateRange
      → renderSummaryGrid() → renderSummaryTimeRow(dateRange)
        → formatDateRangeDisplay(dateRange)
          → 输出: "[ 2026/5/18 ]   同比   [ 2025/5/21 ]"
```

### 关键文件/位置
- **同比文案生成**: [frontend/dashboard-shared.js#L194-L215](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard-shared.js#L194-L215)
- **PC端同比行样式**: [frontend/styles.css#L2262-L2333](file:///d:/User_Project/GMV-LiveLens/frontend/styles.css#L2262-L2333)（`.summary-time-row`）
- **移动端当前隐藏**: [frontend/styles.css#L3429-L3431](file:///d:/User_Project/GMV-LiveLens/frontend/styles.css#L3429-L3431)（`.summary-time-row { display: none; }`）
- **移动端 header 布局**: [frontend/styles.css#L3285-L3288](file:///d:/User_Project/GMV-LiveLens/frontend/styles.css#L3285-L3288)
- **导航 HTML**: [frontend/index.html#L17-L21](file:///d:/User_Project/GMV-LiveLens/frontend/index.html#L17-L21)

---

## 执行步骤

### 步骤 1 — HTML: 在 app-header 中新增移动端同比文案容器
**文件**: `frontend/index.html`
**位置**: `.app-header` 内部，`<nav class="header-nav">` 之后、`<div class="header-actions">` 之前

**新增 DOM**:
```html
<div class="mobile-yoy-row" id="mobileYoyRow"></div>
```

说明：
- 此元素在 PC 端通过 CSS 隐藏 (`display: none`)
- 在移动端 (`≤768px`) 显示在导航栏下方


### 步骤 2 — CSS: PC 端隐藏 + 移动端显示并布局
**文件**: `frontend/styles.css`

#### 2a. 在 `@media (min-width: 769px)` 区域（或基础样式区）添加隐藏规则
```css
.mobile-yoy-row {
  display: none;
}
```

#### 2b. 在 `@media (max-width: 768px)` 中：

**① 修改 `.app-header` 的 `grid-template-areas`**，在 `"nav nav"` 下方新增 `"yoy yoy"` 行：
```css
grid-template-areas:
  "brand actions"
  "nav   nav"
  "yoy   yoy";
```

**② 添加 `.mobile-yoy-row` 移动端样式**：
```css
.mobile-yoy-row {
  grid-area: yoy;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  padding: 2px 0 6px;
  white-space: nowrap;
  gap: 6px;
}
```

**③ 如果 `.mobile-yoy-row` 内容为空则不占高度**（通过 `:empty` 或 JS 控制）

**可选**: `.mobile-yoy-row:empty { display: none; }` 确保空内容时折叠


### 步骤 3 — JS: 在 renderSummaryTimeRow() 中同步内容
**文件**: `frontend/dashboard-shared.js`
**位置**: `renderSummaryTimeRow()` 函数末尾

在 `return html;` 之前，新增同步逻辑：
```javascript
// 同步移动端 nav 下方同比文案
const mobileYoyRow = document.getElementById("mobileYoyRow");
if (mobileYoyRow) {
  mobileYoyRow.textContent = formatDateRangeDisplay(dateRange);
}
```

说明：
- 复用已有的 `formatDateRangeDisplay(dateRange)` 函数，确保内容完全一致（含 "北京时间" 仅 PC 端显示的区别）
- 移动端只显示纯同比日期文案，不显示 "北京时间" 部分


### 步骤 4 — 选项卡切换时的行为确认
- `.mobile-yoy-row` 位于 `.app-header` 内，不受 `.view` 元素的 `display` 切换影响
- 因此无论切换到哪个 tab，同比文案都始终可见（合理，因为它是全局数据摘要，不属于某个特定 view）
- PC 端行为不变（`.mobile-yoy-row` 被 `display: none` 隐藏，`.summary-time-row` 仅在 dashboard view 内显示）

---

## 验证清单
- [ ] PC 端 (≥769px) 视图无任何变化
- [ ] 移动端 (375px-768px) 导航栏下方出现同比文案
- [ ] 文案格式与 PC 端 `.total-card-date-range` 一致 (如 `[ 2026/5/18 ]   同比   [ 2025/5/21 ]`)
- [ ] 数据刷新后文案同步更新
- [ ] 切换 "实时看板/采集配置/任务管理" 选项卡时，文案始终存在
- [ ] 无 JS 报错（`mobileYoyRow` 为 null 时安全兜底）
