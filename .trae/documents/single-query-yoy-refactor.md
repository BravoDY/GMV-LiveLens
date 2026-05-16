# 单次 MySQL OR 查询 + 内存聚合 YOY — 重构计划

## 数据范围（已验证）

```
date 全局:     2026/5/10 ~ 2026/6/9 (47 unique)
to_date 全局:  2025/5/10 ~ 2025/6/9 (47 unique)
```

## SQL（一次查询，两段 OR）

```sql
SELECT `平台`, `统计日期`, `支付金额`
FROM descente_al店铺整体取数源
WHERE ( `统计日期` >= '2026-05-10' AND `统计日期` <= '2026-06-09' )
   OR ( `统计日期` >= '2025-05-10' AND `统计日期` <= '2025-06-09' )
```

≈94 天 × 5 平台 ≈ 470 行，一次 SQL 完成。

## 内存拆分

结果集按 date 是否匹配 `to_date.csv` 的 `date` / `to_date` 字段拆入两个 index：

```
date_index:  { "2026-05-10": {"天猫": 1.2M, ...}, ... }
to_index:    { "2025-05-10": {"天猫": 0.8M, ...}, ... }
```

## YOY 计算（天对天）

对每个 `chinese_product`，取 to_date.csv 中该产品的全部行：

```
2026/5/10 → to_date=2025/5/10
2026/5/11 → to_date=2025/5/11
...
2026/5/16 → to_date=2025/5/16  ← 截止今天
```

从 `date_index[2026-05-10]` 取本期 per-platform GMV  
从 `to_index[2025-05-10]` 取同期 per-platform GMV  
按 platform 累加后 `yoy = (本期合计/同期合计-1)×100%`

## 缓存结构

```json
{
  "cached_at": "...",
  "to_date_hash": "...",
  "query_ok": true,
  "date_index": { "2026-05-10": {...}, ... },
  "to_index":    { "2025-05-10": {...}, ... },
  "periods":     { "集团全周期": {"DST天猫": 148M, ...}, ... }
}
```

## 各模式

| 模式 | 本期 | 同期 |
|------|------|------|
| 实时 | `last_trusted_value` (采集) | `to_index[to_date]` |
| 周期 | `date_index` (全部 ≤ 今天) | `to_index` (对应) |

## 重构步骤

1. 重写 `_query_all_periods_mysql()`：SQL 改 OR 两段，返回 `date_index` + `to_index`
2. `_compute_platform_yoy_map()` 从 `date_index` / `to_index` 内存取，不再查 MySQL
3. `_compute_realtime_platform_yoy()` 本期用采集值，同期从 `to_index` 取单日
4. 清理旧两次查询逻辑

## 涉及文件

| 文件 | 变更 |
|------|------|
| `backend/services/dashboard_query.py` | 4 个函数重写 |

前端 **零改动**。

## 风险

- **L2**：缓存结构增量字段 `to_index`，旧缓存自动重建
- SQL 从 2~3 次 → **1 次**
- 94 天 ≈ 500 行，内存极轻
