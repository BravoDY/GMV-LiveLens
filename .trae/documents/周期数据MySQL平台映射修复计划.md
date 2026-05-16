# 周期数据 MySQL 平台映射修复计划（v3 — 最终版）

## 一、完整数据关系图谱

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                        GMV-LiveLens 数据源全景关系图                       ║
╚═══════════════════════════════════════════════════════════════════════════╝

  ┌───────────────────────────────────────────────────────────────┐
  │                  shops_name.csv  ★ 唯一权威来源 ★              │
  │                                                                │
  │  列: companyshop_name, chinese_name                           │
  │                                                                │
  │  companyshop_name (店铺映射的唯一主键):                         │
  │  ┌─────────────────────────────┬───────────────────┐          │
  │  │ DST天猫                      │ DESCENTE迪桑特天猫   │          │
  │  │ DST京东                      │ DESCENTE迪桑特京东   │          │
  │  │ DST抖店                      │ DESCENTE迪桑特抖音   │          │
  │  │ 唯品会                       │ DESECENTE 迪桑特唯品 │          │
  │  │ DST得物                      │ DESCENTE迪桑特得物   │          │
  │  │ DST天猫高尔夫旗舰店           │ 迪桑特高尔夫天猫      │          │
  │  │ DESCENTE迪桑特童装旗舰店      │ 迪桑特KIDS天猫       │          │
  │  │ DSTBLANC天猫店               │ 迪桑特BLANC天猫      │          │
  │  │ DSTGOLF抖店                  │ 迪桑特高尔夫抖音      │          │
  │  │ DST小程序官方旗舰店            │ 迪桑特小程序         │          │
  │  └─────────────────────────────┴───────────────────┘          │
  └──────────┬──────────────────────────────────────┬─────────────┘
             │                                      │
             │ companyshop_name                     │ companyshop_name
             │ (关联键)                              │ (关联键)
             ▼                                      ▼
  ┌──────────────────────────┐       ┌──────────────────────────────┐
  │       shops.csv           │       │        target.csv             │
  │                           │       │                               │
  │ 列: platform, companyshop_│       │ 列: date, companyshop_name,  │
  │     name, brand, shop_name│       │     target                    │
  │     enabled, Target, ...  │       │                               │
  │                           │       │ 作用: 每日各店铺目标(GMV)      │
  │ 作用: 提供 platform(平台名)│      │                               │
  │      和shop_name(店铺名)  │       │ 示例:                         │
  │      之间的映射关系        │       │ 2026/5/13, DST天猫, 55000000  │
  │                           │       │ 2026/5/13, DST京东, 8000000   │
  │ 示例:                      │       └──────────────────────────────┘
  │ 天猫, DST天猫, DESCENTE... │
  │ 抖音, DST抖店, DESCENTE... │
  │ 抖音, DSTGOLF抖店, ...    │
  └──────────┬───────────────┘
             │
             │ platform → SQLite tasks 表
             ▼
  ┌──────────────────────────────────────┐
  │           SQLite tasks 表             │
  │                                       │
  │ 列: platform, shop_name, target,     │
  │     last_trusted_value, status, ...  │
  │                                       │
  │ 作用: 实时采集任务，存 OCR 采集值       │
  │ platform = shops.csv.platform         │
  │ shop_name = shops.csv.shop_name      │
  └──────────────────────────────────────┘

             ┌─── 周期数据查询链路 ───────────────────────────────┐
             │                                                    │
             │  to_date.csv                                       │
             │  ┌──────────────────────────────┐                  │
             │  │ 列: product, chinese_product, │                 │
             │  │    date, to_date              │                 │
             │  │                               │                 │
             │  │ ⚠ 无 platorm 字段             │                 │
             │  │ ⚠ 仅有日期范围                 │                │
             │  └──────────────┬───────────────┘                  │
             │                 │                                   │
             │                 │ date range (start → end)          │
             │                 ▼                                   │
             │  ┌──────────────────────────────────────┐          │
             │  │          MySQL (od_ecbi)              │          │
             │  │  descente_al店铺整体取数源              │         │
             │  │                                       │          │
             │  │  列: 平台, 统计日期, 支付金额           │         │
             │  │                                       │          │
             │  │  MySQL.平台 ≈ shops_name.companyshop_ │         │
             │  │              name (应一一对应)          │         │
             │  │                                       │          │
             │  │  作用: 按平台+日期查询历史GMV           │         │
             │  └──────────────┬───────────────────────┘          │
             │                 │                                   │
             │                 │ GMV by 平台                       │
             │                 ▼                                   │
             │  ┌──────────────────────────────────────┐          │
             │  │       看板 GMV 匹配                   │          │
             │  │                                       │          │
             │  │  MySQL.平台 → shops.csv.platform      │          │
             │  │  再按 task.platform 匹配 GMV 到店铺    │         │
             │  │                                       │          │
             │  │  当前问题: PLS_NORMALIZE 硬编码         │         │
             │  │  不灵活，必须改为动态读取 shops.csv     │         │
             │  └──────────────────────────────────────┘          │
             └────────────────────────────────────────────────────┘


  ╔══════════ 关联路径总结 ═════════════════════════════════════════╗
  ║                                                                 ║
  ║  shops_name.companyshop_name ←→ shops.csv.companyshop_name     ║
  ║  shops_name.companyshop_name ←→ MySQL.平台                     ║
  ║  shops_name.companyshop_name ←→ target.csv.companyshop_name    ║
  ║                                                                 ║
  ║  shops.csv.platform → SQLite tasks.platform → 看板显示          ║
  ║  shops.csv.shop_name → SQLite tasks.shop_name → 看板显示        ║
  ║                                                                 ║
  ║  周期看板 GMV 匹配链路:                                          ║
  ║  MySQL.平台 → shops.csv.companyshop_name → shops.csv.platform   ║
  ║  然后: shops.csv.platform → task.platform → 匹配 GMV 到店铺      ║
  ║                                                                 ║
  ╚═════════════════════════════════════════════════════════════════╝
```

***

## 二、当前问题

### 2.1 硬编码问题

[dashboard\_query.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/dashboard_query.py#L43-L59) 中硬编码了 `PLS_NORMALIZE` 字典：

```python
PLS_NORMALIZE = {
    "DST小程序": "小程序",
    "DST京东": "京东",
    "DST天猫": "天猫",
    "唯品会": "唯品",
    "DST得物": "得物",
    "DST天猫高尔夫旗舰店": "天猫",
    "DST抖店": "抖音",
    "DESCENTE迪桑特童装旗舰店": "童装",
    "DSTBLANC天猫店": "天猫",
    "DSTGOLF抖店": "抖音",
}
```

**问题：**

1. 新增店铺时必须改代码，无法仅通过 CSV 生效
2. 映射值与 shops.csv 中的 platform 字段可能不一致（如 shops.csv 中天猫就是"天猫"，但 PLS\_NORMALIZE 把某些也映射为"天猫"）
3. 违反"shops\_name.csv 是唯一权威来源"的设计原则

### 2.2 与 shops.csv 的关系

`shops.csv` 已经定义了完整的 `companyshop_name → platform` 映射关系：

| shops.csv 行 | platform         | companyshop\_name |
| ----------- | ---------------- | ----------------- |
| 天猫          | DST天猫            | <br />            |
| 天猫          | DESCENTE迪桑特童装旗舰店 | <br />            |
| 天猫          | DSTBLANC天猫店      | <br />            |
| 天猫          | DST天猫高尔夫旗舰店      | <br />            |
| 京东          | DST京东            | <br />            |
| 唯品          | 唯品会              | <br />            |
| 抖音          | DST抖店            | <br />            |
| 抖音          | DSTGOLF抖店        | <br />            |
| 得物          | DST得物            | <br />            |

**这个映射就是 PLS\_NORMALIZE 应该做的事情，完全不需要单独维护。**

***

## 三、修复方案

### 3.1 核心原则

1. **shops\_name.csv 的** **`companyshop_name`** **是店铺映射唯一来源**
2. `MySQL.平台 → shops.csv.companyshop_name → shops.csv.platform` 映射完全动态，从 CSV 中读取
3. 不保留任何硬编码的平台名映射
4. 如果 MySQL 出现 shops.csv 中不存在的平台名，保留原始名称作为兜底

### 3.2 实现方式

在 [dashboard\_query.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/dashboard_query.py) 中：

```python
from backend.services.dashboard_dataset import DATA_DIR
# 复用 dashboard_dataset.py 已有的 DATA_DIR

def _build_mysql_to_platform_map() -> dict[str, str]:
    """
    从 shops.csv 动态构建 MySQL 平台名 → 看板平台名 的映射。

    shops.csv 的 companyshop_name 列对应 MySQL 的平台字段，
    shops.csv 的 platform 列就是看板使用的平台名。

    不需要 shops_name.csv 中间层——因为 shops.csv 的
    companyshop_name 字段本身就是与 MySQL 平台名对应的。
    """
    import csv, io

    shops_path = DATA_DIR / "shops.csv"
    if not shops_path.exists():
        return {}

    # 复用 shop_config.py 的编码兼容读取方式
    raw_bytes = shops_path.read_bytes()
    text = ""
    for encoding in ("utf-8-sig", "gb18030", "utf-8", "gbk"):
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        return {}

    mapping: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(text, newline="")):
        companyshop_name = str(row.get("companyshop_name") or "").strip()
        platform = str(row.get("platform") or "").strip()
        if companyshop_name and platform:
            mapping[companyshop_name] = platform
    return mapping


def _normalize_mysql_platform(raw: str, shop_map: dict[str, str]) -> str:
    """
    MySQL 原始平台名 → 看板平台名。
    先查动态映射表，找不到则保留原始名称。
    """
    name = raw.strip()
    return shop_map.get(name, name)
```

### 3.3 集成方式

在 `_build_period_payload()` 函数开头构建一次映射，替换旧逻辑：

```python
# 旧代码（删除）:
# normalized = _normalize_platform(row["platform"])

# 新代码:
shop_map = _build_mysql_to_platform_map()

for row in current_rows:
    normalized = _normalize_mysql_platform(row["platform"], shop_map)
    current_map[normalized] += float(row["pay_amount"] or 0)
```

### 3.4 删除内容

删除以下硬编码：

* 第 43 行: `PLS = {"DST": "", "DSTBLANC": "", "DSTGOLF": ""}`

* 第 44-55 行: `PLS_NORMALIZE = {...}` 整个字典

* 第 58-59 行: `_normalize_platform()` 函数

***

## 四、映射链路验证

以 MySQL 中 `DST抖店` 为例，完整链路：

```
MySQL.平台 = "DST抖店"
    ↓ _normalize_mysql_platform()
shop_map["DST抖店"] → shops.csv.companyshop_name="DST抖店" 的行
    → 取 platform="抖音"
    ↓
current_map["抖音"] += pay_amount
    ↓
task.platform = "抖音" (来自SQLite tasks表，与shops.csv一致)
    ↓
current_value = current_map.get("抖音", 0) ✅ 匹配成功
```

***

## 五、文件变更清单

| 文件                                    | 变更内容                                                                                                                                                                                    | 原因           |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `backend/services/dashboard_query.py` | ① 新增 `_build_mysql_to_platform_map()` 动态映射函数；② 新增 `_normalize_mysql_platform()` 函数；③ 删除 `PLS` / `PLS_NORMALIZE` 硬编码字典及 `_normalize_platform()` 函数；④ 修改 `_build_period_payload()` 使用动态映射 | 消除硬编码，实现动态映射 |

**仅改 1 个文件，不动前端、不动其他后端模块。**

***

## 六、验证方案

| 步骤 | 操作                                                  | 预期结果                                  |
| -- | --------------------------------------------------- | ------------------------------------- |
| 1  | Python 语法检查                                         | 无语法错误                                 |
| 2  | 重启 Uvicorn                                          | 启动成功，无 import 错误                      |
| 3  | `GET /api/dashboard-test?dataset_id=product:迪桑特全周期` | `data_status: "ok"`，`shops[].gmv > 0` |
| 4  | 浏览器 `/dashboard-test` 切换到周期页                        | 金额正常显示，无"查询失败"横幅                      |
| 5  | 验证不同平台的 GMV 值合理                                     | 天猫 > 京东 > 抖音 > 唯品会 > 得物 (按实际业务)       |
| 6  | shops.csv 新增一行店铺后重启                                 | 无需改代码即可正确映射                           |

***

## 七、风险评估

| 风险                         | 等级 | 说明                                                       |
| -------------------------- | -- | -------------------------------------------------------- |
| MySQL 出现 shops.csv 不存在的平台名 | 低  | `_normalize_mysql_platform()` 会保留原始名称，不会崩溃               |
| shops.csv 编码异常             | 低  | 复用 shop\_config.py 的编码容错逻辑 (utf-8-sig/gb18030/utf-8/gbk) |
| 影响实时看板                     | 无  | 仅改周期查询链路，`_build_realtime_payload()` 不动                  |
| shops.csv 不存在              | 低  | `_build_mysql_to_platform_map()` 返回空字典，原始名称保留，不会崩溃       |

***

## 八、实施步骤

1. 在 `dashboard_query.py` 中新增 `_build_mysql_to_platform_map()` 和 `_normalize_mysql_platform()` 函数
2. 删除 `PLS` / `PLS_NORMALIZE` / `_normalize_platform()` 硬编码代码块
3. 在 `_build_period_payload()` 中集成动态映射
4. 重启 Uvicorn
5. 浏览器验证周期页 GMV 显示正常

