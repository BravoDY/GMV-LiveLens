# 店铺/平台级 YOY 重构计划

## 用户需求

每个店铺卡片的同比要基于 **to_date.csv 的 date→to_date 映射**，按 **MySQL 中平台对应的 GMV** 分别计算：

| 维度 | 本期查询 | 同期查询 |
|------|---------|---------|
| date 来源 | `to_date.csv` 的 `date` 列 | `to_date.csv` 的 `to_date` 列 |
| MySQL 聚合键 | `platform`（与 task.platform 对应）| `platform` |
| 截止条件 | date ≤ 今天 | to_date ≤ 对应日 |

**示例**：
- 店铺「天猫官旗店」platform=`天猫`
- 本期：to_date.csv 中 "实时" date=`2026/5/16` → 查 MySQL `统计日期=2026/5/16, 平台=天猫` → GMV
- 同期：to_date=`2025/5/19` → 查 MySQL `统计日期=2025/5/19, 平台=天猫` → GMV
- YOY = (本期 / 同期 - 1) × 100%

---

## 当前问题

| 函数 | 问题 |
|------|------|
| `_compute_realtime_yoy()` | 1) 只返回总 YOY，不区分 platform；2) 参数 `today_total` 是采集实时值，应与 MySQL 本期 GMV 对比而非采集值 |
| `_compute_period_yoy()` | 只返回总 YOY，不区分 platform |
| `_build_realtime_payload()` | yoy 只放 summary，未传入 shop/plat |
| `_build_period_payload()` | yoy 只放 summary，未传入 shop/plat |
| 前端 `renderStoreCard`/`renderPlatformCard` | 拿 `model.total.yoy` 透传，所有卡同一值 |

---

## 修复方案

### 核心思想

将 YOY 计算从"全量汇总"改为"按 platform 分区"，返回 `{platform → yoy}` map。

### 1. 新函数 `_compute_platform_yoy_map(ds_key, dates, to_dates)`

```python
def _compute_platform_yoy_map(dates: list[str], to_dates: list[str]) -> dict[str, str]:
    """
    dates:     本期日期列表 (YYYY/MM/DD)
    to_dates:  同期日期列表 (YYYY/MM/DD)
    返回: { "天猫": "-40%", "京东": "15%", ... }
    """
    # 1. 过滤 today 上限 + 解析为 YYYY-MM-DD
    # 2. 查 MySQL 两段 → {date → {platform → GMV}}
    # 3. 对每个 platform: yoy = (本期合计 / 同期合计 - 1) × 100%
```

### 2. 实时模式

- `to_date.csv` "实时" 组 `date = 今天` 的行 → `date` / `to_date`
- 调用 `_compute_platform_yoy_map([date], [to_date])`
- 将结果按 `platform` 注入 `shop_rows` 和 `platform_map`

### 3. 周期模式

- 从 `to_date.csv` 取当前 `chinese_key` 的全部行
- 过滤 date ≤ 今天
- 收集 `dates` / `to_dates` 两个 list
- 调用 `_compute_platform_yoy_map(dates, to_dates)`
- 注入 `shop_rows` 和 `platform_map`

### 4. 前端适配

- `renderPlatformCard()` 接收 `yoy` 参数，显示在前端平台卡
- `renderStoreCard()` 已有 `yoyText` 参数 ✅ 无需改
- `renderTotalCard()` summary YOY → 改为对各 platform YOY 做加权平均或直接取第一个

---

## 涉及文件

| 文件 | 变更 |
|------|------|
| `backend/services/dashboard_query.py` | 新增 `_compute_platform_yoy_map()`；重写实时/周期 yoy 逻辑；shop/platform 注入 yoy |
| `frontend/dashboard-shared.js` | `renderPlatformCard()` 接收 yoy 参数；`renderSummaryGrid()` 传入 |
| `frontend/test-dashboard/dashboard.js` | `renderDashboard()` 传 yoy |
| `frontend/dashboard.js` | `renderDashboard()` 传 yoy |

## 风险评估

- **L2（标准任务）**
- 后端改动集中在一个新函数 + 两个现有函数的 yoy 注入
- 前端改动量很小（已有 yoy 参数通道）
- MySQL 查询增加 2 次（本期 + 同期），每次范围查询，不影响采集链路
