# 实时看板Target字段与CSV行顺序同步计划

## 1. 当前状态分析
- **CSV 解析与入库**：已经在之前的步骤中修改了 `shop_config.py` 和 `store.py`，支持从 `data/shops.csv` 中读取 `Target` 字段并将行号作为 `sort_order` 保存到 `capture_tasks` 表中。
- **前端页面渲染**：已经在 `frontend/dashboard.js` 和 `frontend/core.js` 中接入了 `target` 和 `sort_order` 的处理，并且店铺网格 (`storeGrid`) 改为直接遍历 `tasks` 数组渲染，从而继承后端的严格排序。
- **存在的问题**：由于 `backend/services/store.py` 中的 `task_to_dict` 方法尚未包含新增加的 `target` 和 `sort_order` 字段，导致 `/api/tasks` 接口返回的数据中缺失这两个字段。前端因此拿不到数据，也抛出了 `KeyError: 'target'` 错误。

## 2. 提议的更改

### 2.1 修复后端接口数据返回
**文件**: `backend/services/store.py`
- **改动**: 在 `task_to_dict(task: CaptureTask)` 方法返回的字典中，增加 `"target": task.target` 和 `"sort_order": task.sort_order`。
- **原因**: 这样可以确保前端能够通过 API 拿到这两个字段，从而正确渲染进度条和目标金额，并正确排序。

### 2.2 前端二次确认 (如有必要)
**文件**: `frontend/dashboard.js` & `frontend/core.js`
- 前端逻辑目前已经准备好，但在修改后端并启动服务器后，需要执行走查验证：
  - 确认 `tasks` 的数组顺序与 `data/shops.csv` 的行顺序一致。
  - 确认平台进度、全局进度以及单店进度的计算正确，目标金额能够正确呈现。

## 3. 验证步骤
1. 修改 `backend/services/store.py` 后，重启后端 FastAPI 服务。
2. 浏览器打开本地看板（Preview URL）。
3. 检查“全局总览”、“各平台明细”和“单店卡片网格”的展现：
   - 店铺卡片的排列顺序应与 CSV 行顺序严格一致。
   - `Target` 金额应正确显示，达成进度应按公式 `(last_trusted_value / target) * 100` 正确计算并展示进度条。
4. 确认没有遗留的 JavaScript 错误和后端的 `KeyError`。