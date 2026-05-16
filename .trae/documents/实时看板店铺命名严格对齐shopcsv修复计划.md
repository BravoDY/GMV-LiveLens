# 实时看板店铺命名严格对齐 shop.csv 修复计划

## 概要
- 修复“前端实时看板中的平台名、店铺名没有严格按照 `shop.csv` 的 `platform` / `shop_name` 呈现”的问题。
- 目标是让实时看板仅展示并使用 `shop.csv` 中定义的命名，不再出现历史遗留的“其他平台 / 未命名店铺”之类脱离 `shop.csv` 的名称。
- 用户已明确接受：可以删除历史错误数据，只保留最新、按 `shop.csv` 对齐的数据。

## 当前状态分析

### 1. 前端实时看板当前直接使用任务字段渲染名称
- `frontend/dashboard.js` 中店铺卡片直接渲染 `store.shopName`，平台汇总卡片直接渲染 `p.platform`。
- `frontend/core.js` 中 `liveTasks()` 只筛选 `task.enabled && shopConfigForTask(task)` 的任务，但并不会把任务名称强制改写成 `shop.csv` 的名称。
- `shopConfigForTask(task)` 当前是：
  - 先用 `(platform, shop_name)` 精确匹配
  - 匹配不到再用 `edge_session_id` 回退匹配
- 这意味着：即使匹配到了 `shop.csv` 对应配置，前端最终显示的仍可能是任务表里旧的 `platform / shop_name`，而不是配置表中的权威命名。

### 2. 当前数据库里已经存在被改坏的任务命名
- 只读检查结果显示，`capture_tasks` 中存在任务：
  - `id=62, platform='其他平台', shop_name='未命名店铺', target=4200000`
- 这条记录显然不符合当前 `shop.csv` 中“天猫 / 官方旗舰店”的语义，却仍被实时看板展示出来。
- 结合之前已定位的“前端保存任务时可能带默认名称”的链路，说明历史上任务数据已经被错误写入数据库。

### 3. `shop.csv` 本身在只读查看时存在乱码风险
- 通过直接读取 `data/shops.csv`，可见文件内容显示为乱码。
- `backend/services/shop_config.py` 的 `_read_csv_text_with_fallbacks()` 虽尝试按 `utf-8-sig / gb18030 / utf-8 / gbk` 解析，但当前仓库中的 CSV 可读性异常，说明：
  - 要么文件编码本身有问题；
  - 要么某些工具读取方式与运行时解析方式存在差异。
- 这会进一步放大 `(platform, shop_name)` 精确匹配失败的概率。

## 推荐实现方案

### 1. 后端：把 `shop.csv` 作为任务命名的权威来源
- **文件**：`backend/services/store.py`
- **修改内容**：
  - 在 `sync_tasks_with_shop_configs()` 中，继续以 `shop.csv` 配置为准同步 `platform / shop_name / edge_session_id / target / sort_order`。
  - 补充“清理历史脏命名”的逻辑：
    - 对于能通过 `edge_session_id` 对应到 `shop.csv` 的任务，强制将任务表中的 `platform / shop_name` 回写为 `shop.csv` 中的值；
    - 对于无法在 `shop.csv` 中找到对应项、且明显属于历史错误命名/脏数据的任务，直接删除，仅保留最新、可对齐到 `shop.csv` 的任务。
- **原因**：
  - 当前数据库里已经存在错误命名，仅靠前端显示层兜底不够，必须把源数据修正，否则任务管理、工作台、接口输出都会持续污染。

### 2. 前端：实时看板显示名称改为优先使用 `shop.csv` 配置名
- **文件**：`frontend/core.js`
- **修改内容**：
  - 在 `liveTasks()` 或其上游新增“任务展示名归一化”步骤：
    - 若 `shopConfigForTask(task)` 能匹配到配置，则返回一个“展示用任务对象”，其 `platform / shop_name / sort_order` 以 `shop.csv` 配置为准；
    - 若匹配不到，则不进入实时看板展示。
- **原因**：
  - 即使数据库还残留旧名称，只要能匹配到配置，就应由 `shop.csv` 决定最终呈现；
  - 这样可以保证看板展示层严格遵守你要求的命名口径。

### 3. 前端：排序与平台聚合也以归一化后的名称为准
- **文件**：`frontend/core.js`, `frontend/dashboard.js`
- **修改内容**：
  - `aggregatePlatforms()`、`platformOrder()`、`sortByConfiguredOrder()` 继续使用归一化后的 `platform / shop_name / sort_order`。
  - 确保“平台汇总卡”和“店铺卡片”都不会再依据旧任务名产生错误分组。
- **原因**：
  - 当前问题不仅影响单张店铺卡片，也影响平台维度聚合。

### 4. 后端：检查 CSV 解析稳定性，避免命名源头失真
- **文件**：`backend/services/shop_config.py`
- **修改内容**：
  - 核查 `shops.csv` 的编码解析逻辑，必要时补充更稳妥的编码处理或明确报错；
  - 保证运行时 `load_shop_configs()` 解析出的 `platform / shop_name` 与你实际维护的 CSV 一致。
- **原因**：
  - 如果配置源本身被乱码污染，即使前后端都按配置走，也会继续显示错误名称。

## 假设与决策
- `shop.csv` 是平台名、店铺名的唯一权威来源。
- 实时看板中“不在 `shop.csv` 中的任务”不应继续显示，也不应再以默认名展示。
- 本次修复不仅要修正“未来展示”，还要清理数据库中已存在的历史错误命名任务。
- 用户已明确同意删除历史错误数据，因此对于无法映射到 `shop.csv` 的旧任务，不做保留兼容。
- 不引入新的命名配置入口，继续沿用当前 `shop.csv -> 后端同步 -> 前端展示` 主链路。

## 风险评估
- **兼容性风险**：如果当前数据库中有用户手工创建但未在 `shop.csv` 登记的任务，本次修复会直接删除这些旧任务；这是已获用户接受的决策。
- **数据风险**：如果 `shops.csv` 编码确实异常，盲目同步可能把乱码再次写回数据库，因此实现前要先验证解析结果。
- **前端聚合风险**：若只改店铺卡片而不改平台聚合，仍可能出现平台汇总名称和店铺名称不一致。

## 验证步骤
1. 读取运行时 `shop.csv` 解析结果，确认 `platform / shop_name` 与用户实际维护内容一致。
2. 检查 `capture_tasks` 中历史异常记录（如 `id=62`）是否已被同步修正为 `shop.csv` 对应名称。
3. 检查无法映射到 `shop.csv` 的历史脏任务是否已被删除，不再残留“其他平台 / 未命名店铺”类记录。
4. 调用 `/api/tasks`，确认返回的任务名称已与 `shop.csv` 严格一致。
5. 刷新前端实时看板，验证：
   - 店铺卡片名称严格等于 `shop.csv` 的 `shop_name`
   - 平台汇总名称严格等于 `shop.csv` 的 `platform`
   - 不再出现“其他平台 / 未命名店铺”等脱离 `shop.csv` 的命名
6. 验证任务排序仍与 `shop.csv` 行顺序一致。
