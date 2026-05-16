# Tasks

- [x] Task 1: 周期看板 shop_rows 新增 brand 字段
  - [x] 修改 `backend/services/dashboard_query.py` 的 `_build_period_payload()`，在 `shop_rows` 每个 item 中新增 `"brand": str(task.get("brand") or "").strip()`

- [x] Task 2: 新增任务管理卡片渲染
  - [x] 在 `frontend/dashboard.js` 中新增 `renderManagerGrid(tasks)` 函数：按 platform 分组渲染任务卡片 HTML
  - [x] 卡片展示：shop_name、platform、brand、status badge、last_trusted_value、target、达成进度、最后采集时间
  - [x] 使用已有 CSS class `.manager-card`、`.manager-grid`
  - [x] 点击卡片触发 `loadTaskIntoConfig(task)` 跳转到采集配置编辑
  - [x] 在 `renderDashboard()` 末尾调用 `renderManagerGrid()`

- [x] Task 3: 数字格式化去掉小数位
  - [x] 修改 `frontend/dashboard.js` 的 `formatCurrency()`：`Math.round(Number(value || 0)).toLocaleString("zh-CN")`
  - [x] 同步修改 `frontend/test-dashboard/dashboard.js` 的 `formatCurrency()`

- [x] Task 4: 集成验证
  - [x] 周期 API brand 字段存在，子品牌独立店正确识别（DESCENTE童装、DSTBLANC、高尔夫旗舰、GOLF抖店）
  - [x] 实时 API tasks 包含全部所需字段
  - [x] formatCurrency 取整逻辑正确
