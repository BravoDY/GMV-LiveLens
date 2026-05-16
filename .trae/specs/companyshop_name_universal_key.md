# SPEC: companyshop_name 作为全系统通用关联键

## 一、问题诊断

### 1.1 数据关系图谱（已确认）

```
MySQL: descente_al店铺整体取数源.平台  ──1:1──▶  shops.csv.companyshop_name
                                                        │
                                                        │ (同一 CSV 行)
                                                        ▼
                                              shops.csv.shop_name (非唯一！)
                                                        │
                                                        │ (via (platform, shop_name) join)
                                                        ▼
                                              SQLite capture_tasks (task dict)
                                                        │
                                                        │ (丢失了 companyshop_name)
                                                        ▼
                                              dashboard_query._build_period_payload()

shops_name.csv.companyshop_name  ──  仅用于中文名展示，不参与 GMV 匹配链
target.csv.companyshop_name     ──1:1──▶  shops.csv.companyshop_name
to_date.csv                     ──  无 platform / companyshop_name，仅通过 product 匹配
```

### 1.2 核心根因

**task 字典中缺失 `companyshop_name` 字段**，导致周期查询时的匹配链条断裂：

| 数据源 | 键字段 | 能否关联到 task |
|--------|--------|:---:|
| MySQL.平台 | `DST天猫` | ❌ task 中无此字段 |
| target.csv.companyshop_name | `DST天猫` | ❌ task 中无此字段 |
| shops.csv.companyshop_name | `DST天猫` | ❌ task 中无此字段 |
| task.shop_name | `天猫官旗店` | ⚠️ 非唯一 (GOLF官旗店 出现 2 次) |
| task.platform | `天猫` | ⚠️ 太粗，4 个子店铺都会塌缩到同一个平台 |

### 1.3 当前代码的具体 Bug

1. **_build_mysql_to_shop_map()**: MySQL.平台 → shops.shop_name，但 shop_name 不唯一（GOLF官旗店 同时对应 DST天猫高尔夫旗舰店 和 DSTGOLF抖店），导致 GMV 塌缩。
2. **target_map 匹配**: 用 shop_map 翻译 target.companyshop_name → shop_name，但 target 按 companyshop_name 分组，shop_name 不唯一导致 Target 丢失。
3. **task 迭代匹配**: `current_map.get(company, 0)` 用 task.shop_name 匹配已塌缩的 current_map，导致同 shop_name 的不同店铺显示相同 GMV。

## 二、修复方案

### 2.1 核心思路

**将 `companyshop_name` 注入到 task 字典中**，使其成为周期查询的统一关联键：

- MySQL.平台 == shops.csv.companyshop_name == task.companyshop_name == target.csv.companyshop_name

### 2.2 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `shop_config.py` | `ShopConfig` 新增 `companyshop_name` 字段；`load_shop_configs()` 从 CSV 读取 |
| `store.py` | `task_to_dict()` 返回 `companyshop_name`（从 config 获取） |
| `dashboard_query.py` | 删除 `_build_mysql_to_shop_map` / `_normalize_mysql_to_shop`；新增 `_build_companyshop_index`；`_build_period_payload` 用 `companyshop_name` 直接匹配 MySQL current_map 和 target_map |
| `dashboard_query.py` | `_build_realtime_payload` 的 shop_item 也改用 `companyshop_name` |

### 2.3 数据流

```
shops.csv ──▶ load_shop_configs() ──▶ ShopConfig(companyshop_name="DST天猫", ...)
                                              │
                                              ▼
                        config_by_shop()[(platform, shop_name)] → ShopConfig
                                              │
                                              ▼
                        task_to_dict() → {"companyshop_name": "DST天猫", ...}
                                              │
                                              ▼
                        _build_period_payload():
                          current_map["DST天猫"] += MySQL.支付金额
                          target_map["DST天猫"]  += target.target
                          遍历 task: gmv = current_map[task.companyshop_name]
```

### 2.4 匹配策略

- **1:1 直连店铺**（如 DST京东、唯品会、DST得物）：MySQL.平台 == shops.companyshop_name == task.companyshop_name，直接匹配。
- **1:N 平台下多子店铺**（如 天猫 下有 4 个子店铺 DST天猫/DESCENTE迪桑特童装旗舰店/DSTBLANC天猫店/DST天猫高尔夫旗舰店）：MySQL 中每个子店铺是独立的 平台 值，各自匹配到对应的 task.companyshop_name，GMV 不会塌缩。

## 三、风险评估

| 风险 | 级别 | 说明 |
|------|------|------|
| task dict 结构变更 | 低 | `companyshop_name` 是新增字段，不影响现有消费者 |
| shop_config 结构变更 | 低 | `companyshop_name` 是新增字段，有默认值 ''，兼容旧配置 |
| GOLF官旗店 冲突解决 | — | 不再依赖 shop_name 匹配，冲突自然消失 |
| MySQL NULL 平台 | 已处理 | 第一行查询结果显示有 NULL 值，代码中已丢弃 |

## 四、验证方法

1. 调用 `/api/dashboard?dataset_id=product:xxx` 检查周期数据
2. 确认同平台多店铺（如天猫 4 店）GMV 各不相同
3. 确认 Target 非零
4. 确认 抖店(DST抖店 vs DSTGOLF抖店) GMV 各自独立
