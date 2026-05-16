# YOY 逻辑：本期 GMV 复用计划

## 深度分析：本期 GMV 如何呈现

### 周期模式 `_build_period_payload()` (L465-544)

```
① MySQL 查全部 dates → date_index
② 按 period 聚合 → periods[chinese_key] = {csn → 累计GMV}  ← 全部 period dates, 无 yesterday 截止
③ current_map = periods[chinese_key]
④ shop.gmv = current_map[csn] + today_gmv_map[csn]          ← +今日实时值
⑤ total/platform 汇总 = sum(shop.gmv)
```

### 实时模式 `_build_realtime_payload()` (L367-424)

```
shop.gmv = last_trusted_value                                  ← 今日采集值
total/platform 汇总 = sum(shop.gmv)
```

---

## 根因

当前 `_compute_platform_yoy_map()` 对 本期 用 `date_index[min→yesterday] + today_gmv` **重新计算** cur，但实际看板上显示的 GMV (`current_map[csn] + today_gmv`) 用的是 `periods[chinese_key]`，**日期范围不同**（periods 无 yesterday 截止）。

## 方案：复用已计算的 GMV，同期完全镜像本期逻辑

| | 本期 (cur) | 同期 (ly) |
|--|-----------|----------|
| 实时 | `shop.gmv` (已计算) | `to_index[to_date]` (单日) |
| 周期 | `shop.gmv` (已计算 = `periods[csn] + today`) | `ly_periods[chinese_key][csn]` (镜像 periods 但用 to_dates) |

## 具体改动

### 1. `_query_all_periods_mysql()` 新增 `ly_periods`

镜像 `periods` 构建逻辑，但用 `to_dates` + `to_index`：

```python
ly_periods[ds_id] = {csn → sum(to_index[to_date] for to_date in ds.to_dates)}
```

### 2. `_build_period_payload()`

```
ly_map = cache.ly_periods[chinese_key]
for each shop:
    yoy[csn] = (shop.gmv / ly_map[csn] - 1) × 100%
```

删除对 `_compute_platform_yoy_map` / `_compute_period_platform_yoy` 的调用。

### 3. `_build_realtime_payload()`

保持现有实时 YOY 逻辑（`_compute_realtime_platform_yoy`），本期就是 `last_trusted_value`，同期查 to_index 单日。

### 4. 清理

删除 `_compute_platform_yoy_map` / `_compute_period_platform_yoy` 中对 cur 的重复计算逻辑。

---

## 涉及文件

| 文件 | 变更 |
|------|------|
| `dashboard_query.py` `_query_all_periods_mysql()` | 新增 `ly_periods` 字段 |
| `dashboard_query.py` `_build_period_payload()` | yoy 改为 `shop.gmv / ly_map[csn]` |
| `dashboard_query.py` | 简化/删除 `_compute_platform_yoy_map` |

前端零改动。

## 风险

- **L2**：本期 GMV 不再重复计算，直接复用。同期用完全同构的 `ly_periods`。
