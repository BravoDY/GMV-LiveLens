# Plan: 平台卡目标加粗 + 时间行日期范围 + 店铺卡字号统一

## 需求 1：平台卡片目标数值字体加粗

* 目标：`.platform-target-value` 的 `font-weight` 改为 `700`

* 文件：`frontend/styles.css`

* 风险：L1

## 需求 2：总卡时间行最右端显示当前导航的日期范围

### 后端修改 (`backend/services/dashboard_query.py`)

#### 2a. `_build_realtime_payload()` — 新增 `yoy_date` 字段

在返回值中新增：

```python
"yoy_date": {"cur": f"{today.year}/{today.month}/{today.day}", "ly": ly_date}
```

* `cur`: 今日日期（如 `"2026/5/16"`）

* `ly`: to\_date.csv 中 "实时" 组当天行对应的 `to_date`（如 `"2025/5/19"`）

* 如果 to\_date.csv 中没有匹配行，则 `ly` 为 `""`

#### 2b. `_build_period_payload()` — 新增 `to_date_range` 字段

在返回值中新增：

```python
"to_date_range": {"start": dataset.get("start_to_date", ""), "end": dataset.get("end_to_date", "")}
```

* 数据来源：`dataset`（周期数据集）已有 `start_to_date` / `end_to_date`（格式 `"YYYY-MM-DD"`）

### 前端修改

#### 2c. `renderTotalCard(total, dateRange)` — 新增 dateRange 参数

当前签名：`renderTotalCard(total)`
修改为：`renderTotalCard(total, dateRange)`

在 `.total-card-time-row` 内新增右侧日期范围元素：

```html
<span class="total-card-date-range">2026/5/16 同比 2025/5/19</span>
```

日期格式化为短格式（`"M/D"` 或 `"YYYY/M/D"`），逻辑：

* **实时模式**：`"YYYY/M/D 同比 YYYY/M/D"`

* **周期模式**：`"M/D 累计至 M/D 同比 M/D 累计至 M/D"`（同年省略年份）

* 数据不可用时返回空字符串

#### 2d. `renderSummaryGrid()` — 新增 dateRange 参数并透传

```javascript
function renderSummaryGrid(model, platformYoy, dateRange) {
  // ...
  $("summaryGrid").innerHTML = renderTotalCard(model.total, dateRange) + cardsHtml;
}
```

#### 2e. test-dashboard `renderDashboard()` — 从 snapshot 提取 dateRange

```javascript
const pd = state.snapshot?.public_dashboard;
const dateRange = pd ? {
  mode: pd.mode,
  cur: pd.mode === "realtime" 
    ? (pd.yoy_date?.cur || "")
    : (pd.date_range?.start || ""),
  end: pd.mode === "period" ? (pd.date_range?.end || "") : "",
  ly: pd.mode === "realtime"
    ? (pd.yoy_date?.ly || "")
    : (pd.to_date_range?.start || ""),
  lyEnd: pd.mode === "period" ? (pd.to_date_range?.end || "") : "",
} : null;
```

并传递给 `renderSummaryGrid(model, snapshotPlatformYoy, dateRange)`

#### 2f. 主页面 `dashboard.js` `renderDashboard()` — 同上逻辑

#### 2g. CSS 新增 `.total-card-date-range` 样式

```css
.total-card-date-range {
  margin-left: auto;
  font-size: 14px;
  font-weight: 600;
  color: #8899b4;
  white-space: nowrap;
}
```

利用 `margin-left: auto` 靠右，与左侧"北京时间"自然形成两端对齐。

## 需求 3：店铺卡达成进度和同比数值字号与平台卡统一

* 当前：`.store-metric-value` = `16px`

* 平台：`.platform-progress-value` = `20px` / `.platform-yoy-value` = `20px`

* 目标：`.store-metric-value` font-size `16px` → `20px`

* 仅改 CSS 1 行，无 JS 改动

### 文件变更清单

| 文件                                                  | 变更                                                                                                     |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `backend/services/dashboard_query.py`               | `_build_realtime_payload()` +11 行；`_build_period_payload()` +1 行                                       |
| `frontend/styles.css`                               | `.platform-target-value` font-weight；新增 `.total-card-date-range`；`.store-metric-value` font-size 16→20 |
| `frontend/dashboard-shared.js`                      | `renderTotalCard()` 签名+渲染；`renderSummaryGrid()` 签名+透传                                                  |
| `frontend/test-dashboard/dashboard.js`              | `renderDashboard()` 提取 dateRange 并传递                                                                   |
| `frontend/dashboard.js`                             | `renderDashboard()` 同上                                                                                 |
| `frontend/index.html` + `test-dashboard/index.html` | CSS/JS 版本号更新                                                                                           |

### 影响范围

* 不改变任何现有数据字段，仅追加

* L2 风险 — 涉及前后端联调，需重启验证

