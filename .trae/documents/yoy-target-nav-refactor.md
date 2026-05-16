# YOY / Target / 导航 全链条重构计划

## 用户需求总结

### 需求 1：导航栏由 to_date.csv 驱动
- `to_date.csv` 中有 N 个 `chinese_product`，前端就生成 N+1 个导航（含"实时"）
- 目前"实时"被硬编码，后续产品靠 CSV 自动生成

### 需求 2：实时 — Target 和 YOY 逻辑

| 维度 | 逻辑 |
|------|------|
| GMV | `last_trusted_value`（采集实时值） ✅ 不变 |
| Target | `target.csv` 中 `date = 今天` 的 `companyshop_name` 对应值 |
| YOY | `to_date.csv` 中 "实时" 组 `date = 今天` 的行 → 用该行的 `to_date` 查 MySQL 去年同期 GMV → 对比 |

**当前问题**：实时 YOY 取缓存第一个值（永远是"集团全周期"的 yoy），不正确。

### 需求 3：周期(非实时) — Target 和 YOY 逻辑

| 维度 | 逻辑 |
|------|------|
| GMV | 历史 MySQL + 今日实时（=累计至今） ✅ 上一轮已修复 |
| Target | `target.csv` 中 `date` 在周期范围内且 ≤ 今天 → 累计 |
| YOY | **本期**：周期内 dates ≤ 今天的所有 companion GMV 累计；**去年同期**：对应 to_dates 累计 → 对比 |

**当前问题**：Target 有 `today_date` 上限过滤（✅ 已修复），但 YOY 计算未按上限过滤——目前 `_query_all_periods_mysql()` 是对**全部周期 dates** 计算 yoy，未限制到今天。

---

## 涉及模块与变更

### 1. 后端：`backend/services/dashboard_query.py`

#### 1.1 `_build_realtime_payload()` — Target + YOY

**Target**：改为从 `target.csv` 当天匹配（上一轮已修复 ✅，确认仍正确即可）

**YOY**：从 `to_date.csv` "实时" 组找 `date = 今天` 的行，取 `to_date`，查 MySQL 去年同期 GMV

```python
# 伪代码
today_tgb = _today_slash()  # "2026/5/16"
to_date_rows = load_to_date_rows()
yoy_to_date = None
for r in to_date_rows:
    if r.chinese_product == "实时" and r.date == today_tgb:
        yoy_to_date = r.to_date
        break

if yoy_to_date:
    last_year_gmv = _query_mysql_single_date(yoy_to_date)  # 去年今日GMV
    yoy = f"{int(round((total / last_year_gmv - 1) * 100))}%" if last_year_gmv else "--"
else:
    yoy = "--"
```

#### 1.2 `_build_period_payload()` — YOY 上限过滤

当前 `_query_all_periods_mysql()` 对全部 dates/to_dates 计算，需改为截至今天。

**方案 A**（轻量）：在 `_build_period_payload()` 中自己算 yoy，不依赖缓存的 `yoy` 字段

**方案 B**（彻底）：修改 `_query_all_periods_mysql()` 的 yoy 计算加上 today 上限

推荐**方案 A**：缓存只存原始 MySQL 数据，yoy 实时计算。这样跨天自动对齐。

#### 1.3 导航数据集生成 — `build_dashboard_datasets()`

当前硬编码 `"realtime"` 为特殊数据集。需改为：
- "实时" 不再从 `to_date.csv` 读取其全量 dates，而是仅 `dates = [今天]`
- 其他 `chinese_product` 按现有逻辑不变（dates 为全部 CSV 行）
- 导航按 `datasets` 数组顺序生成

### 2. 前端：无需改动

导航由 `build_dashboard_datasets()` → `/api/dashboard-datasets-test` → `renderDatasetNav()` 自动渲染，JS 无需改动。

---

## 修改清单

| 文件 | 函数/位置 | 变更 |
|------|----------|------|
| `backend/services/dashboard_queue.py` | `_build_realtime_payload()` | YOY 改为从 to_date.csv "实时" today 行的 to_date 计算 |
| `backend/services/dashboard_queue.py` | `_build_period_payload()` | YOY 不从缓存取，改为实时计算（本期≤today vs 同期≤to_date） |
| `backend/services/dashboard_queue.py` | `_query_all_periods_mysql()` | 可保留或清理不再需要的 yoy 预计算 |
| `backend/services/dashboard_dataset.py` | `build_dashboard_datasets()` | "实时" 产品特殊处理：dates=[今天] |

---

## 风险评估

- **L2（标准任务）**
- 影响范围：后端 3 个函数的 yoy/target 计算逻辑
- 不涉及前端 JS、HTML、CSS
- 不涉及采集链路、任务表
- 需要 MySQL 可访问（已有 `_query_mysql_range` / `_query_mysql_single_date`）
