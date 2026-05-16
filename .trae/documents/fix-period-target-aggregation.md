# 周期看板 Target 聚合逻辑修复 — 计划

## 先行判断结论 ✅ 问题确认存在

### 数据事实
- `to_date.csv` "全周期" 的 dates 范围：`2026/5/10` ~ `2026/6/9`（47 天，含未来）
- `target.csv` 有每天的目标值
- 今天：`2026/5/15`

### 根因
`_build_period_payload()` 第 381-384 行：
```python
date_set = set(dates)       # 包含全部 47 天（含未来 5/16 ~ 6/9）
for row in target_rows:
    if row.date in date_set:
        target_map[row.companyshop_name] += row.target
```
**target_map 汇总了全部 47 天的目标（含未来 25 天）**，而 GMV 只是历史至今+今日。两者逻辑不对等：

| 指标 | 聚合范围 | 逻辑 |
|------|---------|------|
| GMV | 5/10 ~ 昨日(Mysql) + 今日(实时) | 历史至今 |
| Target | 5/10 ~ 6/9(全部含未来) | 全周期 **含未来** ❌ |

### 正确逻辑
Target 应和 GMV 一样：**累计至 today-1（历史target）+ 今日 target**

---

## 修复方案

仅修改 `_build_period_payload()` 中 target_map 的构建逻辑：增加日期上限过滤。

### 修改位置
`backend/services/dashboard_query.py` 第 379-384 行

### 修改前
```python
target_rows = load_target_rows()
target_map: dict[str, int] = defaultdict(int)
date_set = set(dates)
for row in target_rows:
    if row.date in date_set:
        target_map[row.companyshop_name] += row.target
```

### 修改后
```python
target_rows = load_target_rows()
target_map: dict[str, int] = defaultdict(int)
date_set = set(dates)
today_date = datetime.now().date()
for row in target_rows:
    if row.date not in date_set:
        continue
    parsed = _parse_date(row.date)
    if parsed is None:
        continue
    if parsed <= today_date:
        target_map[row.companyshop_name] += row.target
```

---

## 涉及文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `backend/services/dashboard_query.py` | 修改 `_build_period_payload()` | target_map 增加日期上限过滤，只累计至今天 |

---

## 风险评估

- **风险等级：L2（标准任务）**
- 仅修改 target_map 的聚合范围，不影响任何其他逻辑
- 不改 GMV 计算、缓存机制、采集链路
- datetime.now() 每次请求取当前时刻，符合实时性要求

## 验证方式

1. 重启 Uvicorn
2. 调 `/api/dashboard-test?dataset_id=product:集团全周期` 
3. 确认 total_target 不再包含未来日期目标
4. 确认 GMV 和 Target 的时间口径一致（都截至今天）
