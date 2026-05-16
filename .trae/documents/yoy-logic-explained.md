# 当前同比（YOY）逻辑说明

## 1. YOY 数据源头：MySQL 缓存计算

所有同比数据来自 [`_query_all_periods_mysql()`](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/dashboard_query.py#L98-L186)，核心逻辑：

### 步骤 1：读取 to_date.csv
- 每个周期数据集有两组日期：`dates`（本期）和 `to_dates`（去年同期）
- 例如"全周期"：`dates = 5/10~6/9`，`to_dates = 5/10~6/9 但年份-1 → 2025`

### 步骤 2：MySQL 查两次
1. **本期** → `periods`：`{csn → 汇总GMV}` 按 dates 范围查询，按 `companyshop_name` 累加
2. **去年同期** → `to_index`：`{date → {platform → GMV}}` 按 to_dates 范围查询

### 步骤 3：同比计算（L170-L178）
```python
for ds_id in 所有周期数据集:
    last_year_total = sum( 去年同期所有店铺的 GMV )
    current_total   = sum( 本期所有店铺的 GMV )
    
    if last_year_total and current_total:
        yoy[ds_id] = f"{int(round((current_total / last_year_total - 1) * 100))}%"
    else:
        yoy[ds_id] = "--"
```

### 步骤 4：持久化到缓存
```json
{
  "periods": { "集团全周期": {"DST天猫": 148M, ...}, ... },
  "yoy":     { "集团全周期": "-63%", "第一波抢先购": "-30%", ... },
  "query_ok": true,
  "cached_at": "2026-05-16T10:00:00"
}
```

**缓存刷新策略**：每天 10:00 自动刷新一次 + 手动点"刷新数据"按钮立即刷新。

---

## 2. 实时模式 → `_build_realtime_payload()` (L307-L312)

```python
cache = _load_cache()              # 读取周期缓存文件
yoy = "--"                          # 默认兜底
if cache and cache.get("query_ok"):
    yoy_map = cache.get("yoy", {})  # {"集团全周期": "-63%", "第一波": "-30%", ...}
    if yoy_map:
        yoy = list(yoy_map.values())[0]  # 取第一个（集团全周期 → "-63%"）
```

**取数逻辑**：
- 从缓存中**取第一个**周期数据集的 yoy 值
- 因为后端所有周期数据集用的是同一份 MySQL 同期对比（同一组 `to_dates`），所以 yoy 口 径相同
- 如果缓存未生成或 MySQL 不可用 → `"--"`

**局限性**：
- 实时模式不区分当前选中的数据集，永远返回缓存里第一个数据集的 yoy
- 缓存过期后 yoy 仍是旧值，直到 10:00 或手动刷新

---

## 3. 周期模式 → `_build_period_payload()` (L370-L375)

```python
cache_periods = cache.get("periods", {})    # 本期 GMV
yoy = str(cache.get("yoy", {}).get(chinese_key, "--"))  # 按数据集ID取 yoy
```

**取数逻辑**：
- `chinese_key` = `dataset_id` 去掉 `product:` 前缀（如 `"集团全周期"`）
- 按 key 从缓存 `yoy` map 中精确匹配当前数据集的 yoy
- 与实时模式不同：每个周期数据集有**独立的 yoy**（因为它们 `dates` 范围不同）

---

## 4. 前端消费

| 卡片 | yoy 来源 | 说明 |
|------|---------|------|
| 总卡 (total) | `model.total.yoy` ← `summary.yoy` | 实时/周期共享，来自后端 `summary.yoy` |
| 平台卡 | `model.total.yoy` 透传 | 与总卡共享同一 yoy 值 |
| 店铺卡 | `model.total.yoy` 透传 | 与总卡共享同一 yoy 值 |

前端显示规则：
- 负值（以 `-` 开头）→ 红色 `var(--bad) #ff4d68`
- 正值 → 青色 `var(--accent) #18d9d2`
- `"--"` → 灰色静默

### 对比表格

| 维度 | 实时模式 | 周期模式 |
|------|---------|---------|
| yoy 数据源 | 周期缓存 `yoy` map 第1项 | 周期缓存 `yoy` map 按数据集ID |
| 计算时机 | 读取缓存（最多1天旧） | 读取缓存（最多1天旧） |
| 可区分不同周期？ | ❌ 无法区分 | ✅ 每个数据集独立 yoy |
| 缓存过期 | 仍返回旧值 `--` | 仍返回旧值 `--` |
| 每天自动刷新 | 10:00 | 10:00 |

---

## 5. 已知局限性

1. **实时模式不区分周期**：无论选实时/全周期/第一波，总显示缓存第一个 yoy
2. **同比仅全渠道层面**：后端 `yoy` 是全集 GMV 对比，没有按平台/店铺拆分
   - 所以目前全卡、平台卡、店铺卡都显示同一个 yoy 值
3. **缓存依赖**：MySQL 不可用时 yoy 为 `"--"`
