# 移动端看板：导航栏居中 + 刷新按钮文字垂直居中

## 任务分级
L1 轻量任务（纯 CSS 样式调整，无业务逻辑变更）

---

## 需求理解
1. **移动端导航栏**（`实时看板 | 采集配置 | 任务管理`）目前左对齐，用户希望页面居中显示
2. **右上角"刷新数据"按钮**内的文字在按钮方块中没有垂直居中，用户希望文字在按钮内上下居中

---

## 影响范围分析
- **仅涉及** `frontend/styles.css` 中的移动端响应式 CSS
- 不涉及 JS 逻辑、HTML 结构、后端代码
- 影响页面：主看板 (`index.html`) 和测试看板 (`test-dashboard/index.html`) 的移动端视图

---

## 问题根因

### 问题 1：导航栏移动端左对齐
- **位置**：`frontend/styles.css` 第 3341-3357 行，`@media (max-width: 768px)` 内
- **现状**：`.header-nav` 设置了 `justify-content: flex-start`（左对齐）+ `overflow-x: auto`（横向滚动）
- **原因**：当初可能为防导航项过多而设计成可滚动，但当前只有 3 个导航按钮，在绝大多数移动屏幕宽度下都能容纳，不需要滚动

### 问题 2：刷新按钮文字未垂直居中
- **位置**：`frontend/styles.css` 第 301-314 行（基础样式）、第 3324-3328 行（768px 断点）、第 3764-3769 行（420px 断点）
- **现状**：
  - 显示时使用 `display: inline-flex`，但未设置 `align-items: center`
  - 移动端 `height: 34px`（768px）/ `height: 32px`（420px）+ `padding: 0 12px`（上下 padding 为 0）
  - 文字 `font-size: 13px`（768px）/ `font-size: 12px`（420px），默认行高约 15~16px，在 32-34px 高度容器内会偏上
- **修复方案**：为刷新按钮添加 `display: inline-flex; align-items: center; justify-content: center;` 统一在基础样式中

---

## 执行计划

### 步骤 1：修改导航栏移动端居中
**文件**：`frontend/styles.css`（约第 3350 行）
**操作**：将 `@media (max-width: 768px)` 中 `.header-nav`（及同级选择器组）的 `justify-content: flex-start` 改为 `justify-content: center`
**注意**：保留 `overflow-x: auto` 作为安全兜底（当内容超出时仍可滚动），保留 `flex-wrap: nowrap`

### 步骤 2：修改刷新按钮文字垂直居中
**文件**：`frontend/styles.css`（约第 316-319 行）
**操作**：在 `body.public-dashboard-mode .header-actions .test-dataset-refresh-btn` 和 `body.test-dashboard-mode .header-actions .test-dataset-refresh-btn` 的显示规则中，添加 `align-items: center; justify-content: center;`，确保在任何断点下文字都垂直水平居中

### 步骤 3：验证
- 使用浏览器 DevTools 模拟移动端视口（375px-768px 范围）
- 确认导航栏三个按钮在页面水平居中
- 确认"刷新数据"按钮文字在按钮方块内垂直居中

---

## 风险评估
- **风险等级**：极低
- **可能影响**：如果未来导航项增加到 5 个以上，在 320px 窄屏上 `justify-content: center` + `overflow-x: auto` 依然可以正常滚动（居中内容超出时，flexbox 会自动退化为可滚动状态）
- **兼容性**：`justify-content: center` 和 `align-items: center` 均为 CSS Flexbox 标准属性，所有现代浏览器及移动端 WebView 均支持
