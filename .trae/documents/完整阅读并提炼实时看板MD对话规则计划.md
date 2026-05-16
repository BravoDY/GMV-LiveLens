# 完整阅读并提炼实时看板MD对话规则计划

## Summary

- 目标：完整阅读并消化 `C:\Users\yjd22\Downloads\cursor_real_time_data_dashboard_framewo.md`，把这份超长对话导出的真实需求、口径修正、实现边界和已推进进度，整理成后续开发可直接使用的“需求与规则清单”。
- 交付形式：以“需求与规则清单”为主，不做时间线长篇复述；仅在必要处标注关键纠偏点，帮助后续避免再次走偏。
- 本次执行阶段不修改业务代码、不运行写操作；核心工作是基于已读文档和当前仓库现状做结构化提炼与对照说明。

## Current State Analysis

### 已完成的只读探索

- 已分块阅读全文 `C:\Users\yjd22\Downloads\cursor_real_time_data_dashboard_framewo.md`，确认该文件不是单一方案文档，而是一次完整的多轮需求澄清与实现推进记录。
- 已通过标题索引与分段阅读确认文档主线包含 3 个阶段：
  - 早期：围绕“不要新 UI、要基于现有正式看板做 demo”的来回纠偏。
  - 中期：围绕 `shops_name.csv`、`target.csv`、`to_date.csv` 与 MySQL 取数口径的深度业务澄清。
  - 后期：围绕数据集层、后端接口、测试副本看板、正式环境隔离策略的落地推进。

### 已确认的仓库真实文件

- 前端正式看板文件存在：
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\index.html`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\app.js`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\dashboard.js`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\styles.css`
- 前端测试副本目录已存在：
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\test-dashboard\`
- 后端与文档中提到的数据集/查询相关文件已存在：
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\services\dashboard_dataset.py`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\services\dashboard_query.py`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\services\dashboard_service.py`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\routers\dashboard.py`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\routers\dashboard_test.py`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\routers\system.py`
- 数据基线文件已存在：
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\data\shops.csv`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\data\shops_default.json`
  - `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\data\shops_page_data.json`

### 从文档中锁定的核心主题

- 这不是“重做新看板”，而是在现有正式看板模板上增加“固定实时 + 动态周期数据集”的顶部子导航。
- 真正的业务核心不是 UI，而是 4 条数据关系：
  - `shops_name.csv`：店铺主连接表。
  - `target.csv`：按 `companyshop_name + date` 唯一的目标表。
  - `to_date.csv`：导航 + 本期周期 + 同比周期控制表。
  - MySQL `descente_al店铺整体取数源`：真实历史单日 GMV 来源。
- 文档后期已明确转向“正式看板先不乱改，优先在测试副本看板验证”的策略。

## Proposed Changes

### 交付内容

- 产出一份面向开发执行的“需求与规则清单”，而不是泛化摘要。
- 清单将分为以下几部分：
  - 业务目标与页面边界。
  - 真实数据源与字段映射关系。
  - 子导航生成规则。
  - 实时页与周期页的差异规则。
  - 本期/同期/同比/目标的精确计算口径。
  - 已确认的实现落点与未完全闭环的风险点。
  - 后续进入实现时必须遵守的隔离规则。

### 具体执行方式

- 以 `cursor_real_time_data_dashboard_framewo.md` 为唯一权威来源，提炼最终被用户确认的规则，不把中途被推翻的理解当成结论。
- 对于对话中多次修正的点，按“最终口径优先”处理，并在结果中明确标识这些地方曾发生纠偏，防止后续再次误解。
- 对文档中提到的仓库文件，仅做“是否存在、承担什么职责”的对照说明，不对其代码做解释扩写，避免越界推断。
- 不输出数据库明文凭据，不复述敏感信息；只保留对实现有用的字段映射关系。

### 输出结果结构

- 结果将优先覆盖以下文件/模块的上下文关系：
  - `frontend/index.html`
  - `frontend/dashboard.js`
  - `frontend/styles.css`
  - `frontend/test-dashboard/index.html`
  - `backend/services/dashboard_dataset.py`
  - `backend/services/dashboard_query.py`
  - `backend/routers/dashboard.py`
  - `backend/routers/dashboard_test.py`
  - `backend/routers/system.py`
- 每个模块只说明与文档主线直接相关的职责，例如：
  - 哪些是正式看板入口。
  - 哪些是测试副本入口。
  - 哪些承接数据集解析、周期查询、接口分流。

## Assumptions & Decisions

- 已确认本次后续交付形式采用“需求与规则清单”，不是完整时间线复盘。
- 以用户在文档后半段明确确认过的业务规则为最终口径；前半段所有被纠正的理解，只作为“曾经误解过”的辅助背景。
- 默认不对文档中宣称“已经做完”的代码变更真伪逐项审计；本轮任务目标是先完整理解文档，不是审查文档与代码是否百分百一致。
- 若后续用户要求基于该文档继续开发，再进入第二阶段：对照当前仓库逐项核验哪些规则已落地、哪些仍未落地。

## Verification Steps

- 核对结果中是否完整覆盖以下 7 类信息：
  - 导航生成规则。
  - 三张 CSV 的职责与主键/唯一性约束。
  - MySQL 字段映射。
  - 实时页与周期页口径差异。
  - 同比与目标计算规则。
  - 测试看板副本策略。
  - 当前仓库已存在的关键实现文件。
- 检查结果是否只保留“最终确认口径”，不混入已被否定的中间说法。
- 检查结果是否去除了敏感凭据和无关冗余表述。
- 检查结果是否能让后续执行者在不重读 190KB 原文档的情况下，直接理解并继续推进该需求。
