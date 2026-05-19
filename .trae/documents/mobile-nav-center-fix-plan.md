# 移动端导航栏居中问题诊断与修复 — 实施计划

## 问题诊断

### 根因：CSS Grid 区域冲突导致 `.header-nav` 与 `.test-dataset-nav-row` 重叠

移动端 `@media (max-width: 768px)` 中，以下 CSS 规则使用**分组选择器**将两个不同的 DOM 元素同时放入同一个 `grid-area: nav`：

```css
.header-nav,
body.dashboard-page.public-dashboard-mode .app-header .test-dataset-nav-row,
body.dashboard-page.test-dashboard-mode .app-header .test-dataset-nav-row {
    grid-area: nav;
    ...
}
```

这导致在看板模式（`public-dashboard-mode` / `test-dashboard-mode`）下：
1. `.header-nav` 占据 `nav` 区域
2. `.test-dataset-nav-row` 也占据 `nav` 区域
3. 两个元素在 CSS Grid 中**重叠**，互相挤压/遮挡

`.test-dataset-nav-row` 内的子元素 `.test-dataset-bar` 设置了 `justify-content: flex-start`（左对齐），当它与导航栏重叠时会破坏视觉居中效果。

### 证据链
| 文件 | 行号 | 内容 |
|---|---|---|
| [styles.css#L3348-L3364](file:///d:/User_Project/GMV-LiveLens/frontend/styles.css#L3348-L3364) | 分组选择器 | `.header-nav, .test-dataset-nav-row` 共享 `grid-area: nav` |
| [styles.css#L3405-L3413](file:///d:/User_Project/GMV-LiveLens/frontend/styles.css#L3405-L3413) | `.test-dataset-bar` | `justify-content: flex-start` |
| [styles.css#L229-L232](file:///d:/User_Project/GMV-LiveLens/frontend/styles.css#L229-L232) | 看板模式显示 | `body.public-dashboard-mode .test-dataset-nav-row { display: flex }` |

---

## 执行方案

### 步骤 1 — 拆分 CSS 规则组，解除 grid-area 冲突
**文件**: `frontend/styles.css`

**操作**: 将分组选择器拆分为两个独立规则块：
1. `.header-nav` 保留 `grid-area: nav`（导航栏独立占据 nav 行）
2. `.test-dataset-nav-row` 移除 `grid-area`，让它在 Grid 中自然排列到 `nav` 行之后

### 修改前
```css
.header-nav,
body.dashboard-page.public-dashboard-mode .app-header .test-dataset-nav-row,
body.dashboard-page.test-dashboard-mode .app-header .test-dataset-nav-row {
    grid-area: nav;
    position: static;
    transform: none;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    justify-content: center;
    gap: 10px;
    overflow-x: auto;
    overflow-y: hidden;
    flex-wrap: nowrap;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
}
```

### 修改后
```css
/* 导航栏：独立占据 nav 区域 */
.header-nav {
    grid-area: nav;
    position: static;
    transform: none;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    justify-content: center;
    gap: 10px;
    overflow-x: auto;
    overflow-y: hidden;
    flex-wrap: nowrap;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
}

/* 测试数据集子导航：不占 grid-area，自然排列在下方 */
body.dashboard-page.public-dashboard-mode .app-header .test-dataset-nav-row,
body.dashboard-page.test-dashboard-mode .app-header .test-dataset-nav-row {
    position: static;
    transform: none;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    justify-content: flex-start;
    gap: 10px;
    overflow-x: auto;
    overflow-y: hidden;
    flex-wrap: nowrap;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
}
```

关键差异：
- `.test-dataset-nav-row` **去掉** `grid-area: nav`
- `.test-dataset-nav-row` 的 `justify-content` 改为 `flex-start`（数据集标签适合左对齐）

---

## 验证清单
- [ ] 移动端看板模式导航栏视觉居中显示
- [ ] 测试数据集标签栏出现在导航栏下方（独立一行，不重叠）
- [ ] PC 端无变化
- [ ] 切换 "实时看板/采集配置/任务管理" 无异常
