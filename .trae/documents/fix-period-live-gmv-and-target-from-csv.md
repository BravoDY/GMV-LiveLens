# 周期看板实时跳动 + 实时看板 Target 从 target.csv 读取 — 修复计划

## 问题 1：周期看板（非实时导航页）数据不跳动

### 症状
测试看板切换到周期导航（如"全周期""一裙周期"）后，GMV 数据显示的是 MySQL 缓存中的历史数据，数字不随实时采集更新。

### 根因
`_build_period_payload()` 第 383 行：
```python
current_value = float(current_map.get(csn, 0))
```
`current_map` 只来自 MySQL 缓存（历史周期累计 GMV），**完全没有加上今日实时采集的 GMV**。

### 修复
在构建 `shop_rows` 时，每个店铺的 GMV 应改为：
```
period_gmv = 历史周期GMV + 今日实时GMV(last_trusted_value)
```

具体改动：`_build_period_payload()` 中，为每个 shop 从 tasks 中查找对应 `companyshop_name` 的 `last_trusted_value`，加上：

```python
# 构建今日实时GMV索引
today_gmv_map: dict[str, int] = {}
for task in tasks:
    if not task.get("enabled"):
        continue
    csn = str(task.get("companyshop_name") or "").strip()
    if csn:
        today_gmv_map[csn] = int(task.get("last_trusted_value") or 0)

# 在构建 shop_rows 时：
current_value = float(current_map.get(csn, 0)) + today_gmv_map.get(csn, 0)
```

### 验证
切换到周期导航后，GMV 数字应随实时采集更新（约每秒跳动）。

---

## 问题 2：实时看板 Target 应从 target.csv 读取

### 症状
实时看板的 Target 值来自 tasks 表中 shops.csv 的 `target` 字段（固定值），而不是 target.csv 中对应 `companyshop_name` 当天日期的目标值。

### 数据事实
- `target.csv` 格式：`companyshop_name, date, target`，其中 date 格式为 `2026/5/15`
- 例如：`DST天猫 | 2026/5/15 | 19500000` 表示 DST天猫今天目标 1950 万
- `_today()` 返回格式：`2026-05-15`（`%Y-%m-%d`）

### 根因
`_build_realtime_payload()` 第 259 行：
```python
"target": int(task.get("target") or 0),
```
直接使用 tasks 中 shops.csv 的固定 target 字段，没有关联 target.csv。

### 修复
在 `_build_realtime_payload()` 中，加载 target.csv 并建立 `companyshop_name → today_target` 的映射：

```python
target_rows = load_target_rows()
today_str = _today()
today_target_map: dict[str, int] = {}
for row in target_rows:
    # 标准化 target.csv 的日期格式：2026/5/15 → 2026-05-15
    try:
        normalized = datetime.strptime(row.date, "%Y/%m/%d").strftime("%Y-%m-%d")
    except ValueError:
        continue
    if normalized == today_str:
        today_target_map[row.companyshop_name] = row.target

# 然后在构建 shop_item 时：
"target": today_target_map.get(str(task.get("companyshop_name") or "").strip(), 0),
```

### 验证
刷新实时看板，Target 值应与 `data/target.csv` 中当天 shop 对应的 target 一致。

---

## 涉及文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `backend/services/dashboard_query.py` | 修改 `_build_realtime_payload()` | Target 从 target.csv 当天读取 |
| `backend/services/dashboard_query.py` | 修改 `_build_period_payload()` | GMV 加上今日实时采集值 |

---

## 风险评估

- **风险等级：L2（标准任务）**
- 仅修改两个后端函数的 GMV/Target 数据来源
- 不影响采集链路、数据库写入、前端渲染
- 修改逻辑清晰：历史+实时、target.csv 当天匹配

## 验证方式

1. 重启 Uvicorn
2. 打开 `/dashboard-test`，切换到周期导航 → 确认 GMV 数字随采集跳动
3. 检查实时看板 Target → 确认与 `data/target.csv` 当天行的 target 值一致
4. 确认 `POST /api/dashboard-cache/refresh` 后周期数据包含今日实时增量
