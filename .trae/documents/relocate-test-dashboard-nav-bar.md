# 测试看板 — 导航栏和刷新按钮移至页面上方居中

## 目标

将测试看板（`/dashboard-test`）中数据集导航栏和"刷新数据"按钮从左上角移到看板顶部居中位置，UI 与整个页面设计风格统一。

## 当前布局

```
┌─ dashboard-top-frame ──────────────────────────────┐
│ [导航1] [导航2] [导航3] ...          [刷新数据]     │  ← 左上角
│ ┌─────────────────────────────────────────────────┐ │
│ │ 总GMV卡片 │ 达成率 │ 同比 │ ...                  │ │
│ └─────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

## 目标布局

```
┌─ dashboard-top-frame ──────────────────────────────┐
│                                                    │
│      [实时] [全周期] [第一波] ...    [刷新数据]      │  ← 居中
│                                                    │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 总GMV卡片 │ 达成率 │ 同比 │ ...                  │ │
│ └─────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

## 实现方案

### 修改 1：HTML 结构调整

将 `#testDatasetNav` 和 `#refreshCacheBtn` 包裹在一个新的容器 div 中，放在 `.dashboard-top-frame` 内、`#summaryGrid` 之前。

**文件**: `frontend/test-dashboard/index.html`

**修改前** (L56-L58):
```html
<div id="testDatasetNav" class="test-dataset-bar"></div>
<button id="refreshCacheBtn" class="test-dataset-refresh-btn" type="button">刷新数据</button>
<div id="summaryGrid" class="summary-grid"></div>
```

**修改后**:
```html
<div class="test-dataset-nav-row">
  <div id="testDatasetNav" class="test-dataset-bar"></div>
  <button id="refreshCacheBtn" class="test-dataset-refresh-btn" type="button">刷新数据</button>
</div>
<div id="summaryGrid" class="summary-grid"></div>
```

### 修改 2：CSS 样式更新

新增 `.test-dataset-nav-row` 容器样式，使其居中并保持与页面设计一致。

**文件**: `frontend/test-dashboard/styles.css`

**新增/修改样式**:

```css
.test-dataset-nav-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 6px 0 22px;
  min-height: 44px;
}

.test-dataset-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: center;
  overflow-x: auto;
  min-height: 42px;
}

.test-dataset-chip {
  flex: 0 0 auto;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.05);
  color: var(--muted);
  border-radius: 999px;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}

.test-dataset-chip:hover {
  background: rgba(24, 217, 210, 0.08);
  border-color: rgba(24, 217, 210, 0.32);
  color: #e0eaf5;
}

.test-dataset-chip.is-active {
  background: rgba(24, 217, 210, 0.16);
  border-color: rgba(24, 217, 210, 0.56);
  color: #ffffff;
  box-shadow: 0 0 0 1px rgba(24, 217, 210, 0.14) inset;
}

.test-dataset-refresh-btn {
  flex: 0 0 auto;
  border: 1px solid var(--line);
  background: rgba(24, 217, 210, 0.06);
  color: var(--muted);
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}

.test-dataset-refresh-btn:hover {
  background: rgba(24, 217, 210, 0.16);
  border-color: rgba(24, 217, 210, 0.5);
  color: #ffffff;
}

.test-dataset-refresh-btn.is-refreshing,
.test-dataset-refresh-btn:disabled {
  cursor: wait;
  opacity: 0.6;
}
```

### 修改 3：版本号更新

更新 `test-dashboard/styles.css` 和 `test-dashboard/index.html` 的版本号。

---

## 涉及文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `frontend/test-dashboard/index.html` | 结构优化 | 新增 `.test-dataset-nav-row` 容器包裹 nav+refresh |
| `frontend/test-dashboard/styles.css` | 重写 | 导航栏样式重构，使用 `var(--*)` 统一设计语言 |

## 风险评估

- **风险等级：L1（轻量任务）**
- 仅调整 HTML 结构和 CSS 样式
- 不涉及 JS 逻辑、后端、数据流
- 不影响其他页面

## 验证方式

1. 刷新 `/dashboard-test` 页面
2. 确认导航栏和"刷新数据"按钮在总面积卡上方居中显示
3. 确认芯片 hover/active 效果与页面整体风格一致（使用 `--accent` 青色）
4. 确认响应式下可正常换行不溢出
