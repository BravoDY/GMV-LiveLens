# Hello.md 聊天记录上下文索引 — 计划

## 目标

将 `C:\Users\yjd22\Downloads\Hello.md`（约 6600+ 行聊天记录）完整理解，并作为后续对话的核心上下文索引。

---

## Hello.md 内容全景总结

这份聊天记录是 **GMV-LiveLens 项目开发过程中多轮对话的完整实录**，覆盖了从数据架构讨论、功能开发、Bug 修复、到全项目审计的完整生命周期。

### 聊天记录中涉及的十大主题

#### 1. 数据架构与关联键设计
- `shops_name.csv` 的 `companyshop_name` 是全项目店铺主键
- `shops.csv`、`target.csv`、MySQL 都通过 `companyshop_name` 关联
- `to_date.csv` 控制周期切换（product/date/to_date）
- 最终统一口径：所有表以 `companyshop_name` 为核心关联键

#### 2. Dashboard-Test 导航切换开发
- 测试看板的导航栏从无到有：实时↔周期数据集切换
- 修复了轮询冲掉切换状态的问题
- 修复了 MySQL 查询失败导致切换回退到 realtime 的问题
- 增加了 localStorage 记忆、失败回退、空数据状态横幅

#### 3. MySQL 历史数据接入
- 从 SQLite 误导性代码 → 真正接入 `10.128.64.96` MySQL
- 库名从 `user_od_ecbi` 修正为 `od_ecbi`
- 平台名映射：MySQL 存 `DST天猫`/`DST京东`/`DST抖店`，需映射到 `天猫`/`京东`/`抖音`
- 动态映射从 `shops.csv` 的 `companyshop_name` → `platform` 关系读取，不硬编码

#### 4. 周期数据缓存机制
- 核心需求：to_date.csv 不变 + 未跨天 → 直接走缓存，避免每次切换都查 MySQL
- 缓存文件：`data/.cache/period_gmv.json`
- 失效规则：跨天（>10:00 AM）自动刷新、CSV SHA256 变更自动刷新
- 手动刷新按钮 + `POST /api/dashboard-cache/refresh` API

#### 5. 品牌分组与任务卡片修复
- 周期看板 brand 字段缺失 → 全部店铺归入「大货独立店」
- 修复：`_build_period_payload()` 补充 `brand` 字段
- 任务管理卡片完全缺失 → 重写 `renderManagerGrid()`
- 每个任务卡片恢复 Edge 操作按钮（启动/显示/隐藏/关闭）
- 卡片排序按 shops.csv 中 `platform + shop_name` 的填报顺序

#### 6. 前端导航栏与事件绑定 Bug
- 三个导航栏无法切换：`switchView()` 从未被绑定到按钮点击事件
- 事件委托修复在 `app.js` 中
- Edge 按钮点击误跳转：`closest("[data-editable]")` 冒泡捕获
- 采集全部按钮不工作：HTML `display:none` + `toggleScheduler()` 未绑定
- `#schedulerToggle` 按钮缺少事件绑定

#### 7. 数字格式化
- GMV/Target 不保留小数位 + 千分符：`Math.round().toLocaleString("zh-CN")`

#### 8. 全项目技术审计
- 项目类型：Windows 本地 Python + FastAPI + SQLite + 纯原生 JS 前端
- 依赖：11 个 Python 库，无 npm/Node.js
- API 端点：29 个，8 个路由模块
- 前端：8 JS 文件 4114 行，3 CSS 文件 3112 行
- 安全：无硬编码密钥、SQL 参数化查询、`escapeHtml()` XSS 防护
- 待处理风险：requirements.txt 缺 pymysql/python-dotenv、target.csv 去重、同比日期偏差

#### 9. 采集配置链路深度审查
- 完整数据流：任务配置 → Edge 会话绑定 → 截图 → OCR → 调度确认 → SQLite → 看板
- 大屏只读模式：直接读取 Angular scope 或 DOM 中的 `payAmt`/`todayOrdAmt`
- 调度器 `_judge()`：跳变检测 5 倍阈值、连续确认、跨天重置

#### 10. 三页面代码统一
- 正式版 `dashboard.js` 和测试版 `test-dashboard/dashboard.js` 存在大量重复
- 最终方案：统一关键函数，减少维护成本

---

## 关键文件变更记录（按时间线）

| 阶段 | 涉及文件 | 主要变更 |
|------|----------|----------|
| 导航切换 | `test-dashboard/app.js`, `dashboard_query.py` | 状态机收口、MySQL 降级 |
| MySQL 接入 | `dashboard_query.py`, `.env.example`, `main.py` | pymysql 直连、动态平台映射 |
| 缓存机制 | `dashboard_query.py`, `dashboard_test.py`, `main.py` | SHA256 检测、缓存调度器 |
| 品牌分组 | `dashboard_query.py`, `frontend/dashboard.js` | brand 字段补充、任务卡片渲染 |
| 导航 Bug | `frontend/app.js`, `frontend/core.js` | 事件委托绑定、toggleScheduler |
| 三页统一 | `frontend/dashboard.js`, `test-dashboard/dashboard.js` | 函数统一、差异化增量 |

---

## 作为上下文索引的使用方式

后续对话中，当用户提到以下任何关键词或问题时，应直接引用 Hello.md 中的对应内容：

| 关键词/问题 | Hello.md 对应章节/行号 |
|-------------|------------------------|
| companyshop_name 关联 | 第 7-84 行 |
| dashboard-test 导航 | 第 89-249 行 |
| MySQL 历史数据 | 第 381-537 行 |
| 周期缓存 | 第 993-1323 行 |
| 品牌分组 | 第 1396-1821 行 |
| 导航栏无法切换 | 第 1325-1395 行 |
| 任务管理卡片 | 第 1902-2585 行 |
| Edge 按钮跳转 Bug | 第 2676-2770 行 |
| 项目审计报告 | 第 2677-3952 行 |
| 采集配置链路 | 第 4115-5589 行 |
| 三页面代码统一 | 第 5752-6279 行 |
| 启动采集按钮 | 第 4063-4113 行 |

---

## 执行计划

1. ✅ 已完整读取 Hello.md 各章节内容
2. ✅ 已归纳十大主题和关键文件变更记录
3. ✅ 已建立关键词→内容映射索引
4. 将以上知识作为后续所有对话的上下文基础

---

## 状态

计划已完成。Hello.md 的全部聊天内容已作为后续交互的核心上下文索引。
