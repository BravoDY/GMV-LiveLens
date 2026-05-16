# YOY 范围聚合 + 昨日截止修正

## 用户纠正

| 维度 | 之前理解 | 正确理解 |
|------|---------|---------|
| 本期 MySQL | 从最早 date 累计到**今天** | 从最早 date 累计到**昨天** |
| 本期合计 | MySQL 全部 | MySQL(最早→昨天) + **今日实时采集值** |
| 同期 MySQL | 到今天对应的 to_date | 到**昨天**对应的 to_date |

### 示例："集团全周期"，今天=2026/5/16

```
to_date.csv:
  date      to_date
  2026/5/10 2025/5/10  ← min
  ...
  2026/5/15 2025/5/18  ← 昨天
  2026/5/16 2025/5/19  ← 今天（不纳入MySQL）

本期   = MySQL[2026-05-10 ~ 2026-05-15] + 今日实时采集值
同期   = MySQL[2025-05-10 ~ 2025-05-18]
YOY    = (本期/同期 - 1) × 100%
```

---

## 改动方案

### `_compute_platform_yoy_map()` 签名变更

```python
def _compute_platform_yoy_map(
    chinese_key: str,
    date_index: dict,
    to_index: dict,
    today_gmv: dict[str, int]  # NEW: {csn → today实时采集值}
) -> dict[str, str]:
```

**逻辑**：
1. 从 to_date.csv 取该 product 全部行
2. 找 min_date / min_to_date
3. 找**昨天** (`today - 1d`) 对应行 → yesterday_date / yesterday_to_date
4. cur: 遍历 date_index[日期在 min_date~yesterday_date] 的 per-CSN GMV
5. ly: 遍历 to_index[日期在 min_to_date~yesterday_to_date] 的 per-CSN GMV
6. **加上** today_gmv 到 cur
7. yoy = (cur/ly − 1) × 100%

### `_compute_period_platform_yoy()` 适配

传入 today_gmv_map（从 tasks 的 last_trusted_value 提取）

### `_compute_realtime_platform_yoy()` 

**不变** — 实时模式本期就是当日采集值，不需要 MySQL 累加，同期从 to_index 取当天对应的单日。

### Target 验证

✅ 已验证：`today_target_map.get(companyshop_name)` — 每个任务卡用自己的 companion_shop_name 匹配 target.csv。

---

## 文件

| 文件 | 变更 |
|------|------|
| `dashboard_query.py` | `_compute_platform_yoy_map` 改截止昨天 + 接收 today_gmv |

## 风险

- L2：范围聚合 + 昨日截止，输入输出清楚
