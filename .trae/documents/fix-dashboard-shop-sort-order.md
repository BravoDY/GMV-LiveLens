# 修复 /dashboard 和 /dashboard-test 店铺排序规则不跟随主页的问题

## 症状

`http://127.0.0.1:8100/dashboard` 和 `http://127.0.0.1:8100/dashboard-test` 两个页面的店铺卡片排列顺序与主页 `http://127.0.0.1:8100/` 不一致。主页按 shops.csv 填报顺序排列，而另外两个页面按 GMV 从大到小排列。

## 根因分析

项目有三条数据输出路径，各自的排序逻辑如下：

### 主页 `/`（正确基准）
- 后端：`build_snapshot()` → [common.py:L186](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/routers/common.py#L186)
  - `tasks.sort(key=lambda t: (t.get("sort_order") or 0, ...))` — 按 shops.csv 行号排序
- 前端：`sortByConfiguredOrder()` → [core.js:L403-L414](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/core.js#L403-L414)
  - 按平台出现顺序 → 店铺出现顺序 → 拼音排序
- **结果：完全按 shops.csv 填报顺序排列 ✅**

### `/dashboard` 公共看板（错误排序）
- 后端：`build_public_dashboard()` → [dashboard_service.py:L89](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/dashboard_service.py#L89)
  - `shops.sort(key=lambda item: item["gmv"], reverse=True)` — **按 GMV 降序排列**
  - 平台也按 `total_gmv` 降序 → [dashboard_service.py:L85](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/dashboard_service.py#L85)
- **问题：同店 GMV=0 时顺序随机，有值时也打乱了 shops.csv 填报顺序**

### `/dashboard-test` 测试看板（部分错误排序）
- 实时模式 `_build_realtime_payload()` → [dashboard_query.py:L286](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/dashboard_query.py#L286)
  - `shop_rows.sort(key=lambda item: item["gmv"], reverse=True)` — **按 GMV 降序排列**
  - 平台也按 `total_gmv` 降序 → [dashboard_query.py:L287](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/dashboard_query.py#L287)
- 周期模式 `_build_period_payload()` — **排序正确**
  - 遍历 tasks 的顺序来自 `build_snapshot()`（已按 sort_order），不做二次排序
  - 平台按字母排序 → [dashboard_query.py:L399](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/dashboard_query.py#L399)

### 排序规则对比

| 页面/模式 | shops 排序 | platforms 排序 | 是否正确 |
|-----------|-----------|----------------|:--:|
| `/` 主页 | sort_order (shops.csv 行号) | 平台出现顺序 | ✅ |
| `/dashboard` 公共看板 | **GMV 降序** | **GMV 降序** | ❌ |
| `/dashboard-test` 实时 | **GMV 降序** | **GMV 降序** | ❌ |
| `/dashboard-test` 周期 | sort_order (继承 snapshot) | 字母序 | ✅ |

## 修复方案

### 修改 1：`dashboard_service.py` — `build_public_dashboard()`

删除 GMV 排序，改为按 shops.csv 填报顺序（继承 `build_snapshot()` 的 sort_order）：

```python
# 删除第 89 行
# shops.sort(key=lambda item: item["gmv"], reverse=True)

# 删除第 85 行，替换为：
platforms = sorted(platforms_map.values(), key=lambda item: platform_order.get(item["platform"], 99))
# 并需要根据 shops.csv 建立 platform_order 映射
```

**更简洁的方案**：直接保持 `build_snapshot()` 的顺序不变，不二次排序：

```python
# L85: 改为按 shops.csv 中平台出现顺序
platform_order = []
for t in enabled_tasks:
    p = str(t.get("platform") or "其他平台").strip()
    if p not in platform_order:
        platform_order.append(p)
platforms = sorted(platforms_map.values(), key=lambda item: platform_order.index(item["platform"]) if item["platform"] in platform_order else 999)

# L89: 删除整行，shops 保持 snapshot 原始顺序
```

### 修改 2：`dashboard_query.py` — `_build_realtime_payload()`

删除 GMV 排序，改为按 shops.csv 填报顺序：

```python
# L286: 删除
# shop_rows.sort(key=lambda item: item["gmv"], reverse=True)

# L287-L289: 删除 GMV 排序，platforms 保持遍历顺序
```

**更简洁方案**：

```python
# L286: shop_rows 不做二次排序（tasks 已被 build_snapshot() 按 sort_order 排好）
# 删除 shop_rows.sort(...) 这一行

# L287: platforms 改为按 shops.csv 中平台出现顺序
platform_order = []
for t in enabled_tasks:
    p = str(t.get("platform") or "").strip()
    if p and p not in platform_order:
        platform_order.append(p)
platforms = sorted(platform_map.values(), key=lambda item: platform_order.index(item["platform"]) if item["platform"] in platform_order else 999)

# L288-L289: 删除内部 shops 的 GMV 排序
# for platform in platforms:
#     platform["shops"].sort(key=lambda item: item["gmv"], reverse=True)
```

### 修改 3：`dashboard_query.py` — `_build_period_payload()`

周期模式排序基本正确（继承 snapshot 的 sort_order），只需将平台的字母排序改为按 shops.csv 平台出现顺序：

```python
# L399: 改为按 shops.csv 平台出现顺序
platform_order = []
for t in tasks:
    if not t.get("enabled"):
        continue
    p = str(t.get("platform") or "").strip()
    if p and p not in platform_order:
        platform_order.append(p)
for p in platform_order:
    if p in platform_map:
        platforms.append(platform_map[p])
```

## 涉及文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/services/dashboard_service.py` | 修改 | 删除 GMV 排序（L85、L89），改为按 platform 出现顺序 |
| `backend/services/dashboard_query.py` | 修改 | 删除 `_build_realtime_payload()` 中的 GMV 排序（L286-L289）；修改 `_build_period_payload()` 平台排序（L399） |

## 风险评估

- **风险等级：L2（标准任务）**
- 仅修改后端返回数据的排序方式，不改变任何字段值
- 不影响采集链路、数据库、前端渲染逻辑
- 三个页面的 shops 排序将统一为 shops.csv 填报顺序

## 验证方式

1. 重启 Uvicorn 后刷新 `/`、`/dashboard`、`/dashboard-test` 三个页面
2. 确认三个页面的店铺卡片排列顺序一致（按 shops.csv 填报顺序）
3. 确认平台分组顺序一致
