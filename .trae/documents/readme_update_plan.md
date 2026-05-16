# README.md 更新计划

## 1. 目标与背景
用户指出我们之前仅更新了 `GMV-LiveLens项目全量说明书.md`，而遗漏了根目录下的 `README.md`。`README.md` 虽然定位为快速启动与总览，但也需要保持与核心架构和事实逻辑的同步，特别是最近关于全局采集频率、`ddddocr` 引擎引入、自动样本收集、严格单页策略以及 Playwright 超时降级等关键改动。

## 2. 当前遗漏的内容分析
1. **全局采集频率**：`README.md` 中的“配置文件说明”仍提示 `interval_seconds` 是针对单个任务的，并且“采集工作流”中也是基于任务独立的 `interval_seconds`。实际上现在已改为全局设置。
2. **数据库结构**：未体现新增的 `app_settings` 表。
3. **OCR 引擎**：未体现 `ddddocr` 已经完全可用并作为高优兜底引擎，也未提及 `data/ocr_datasets/` 自动样本收集机制。
4. **Edge 机制优化**：未提及受控 Edge 的“严格单页策略”和 Playwright 截图的“5秒超时降级机制”。

## 3. 拟执行的变更 (Proposed Changes)
目标文件：`C:\Users\yjd22\Desktop\python项目\GMV-LiveLens\README.md`

### 步骤 1：更新配置文件说明
- 在 `data/shops.csv` 的字段说明表格下方，添加关于 `interval_seconds` 的说明：“*注：任务独立的 `interval_seconds` 现已弃用，系统统一使用前端配置的全局采集频率。*”

### 步骤 2：更新数据库结构
- 在“数据库结构”部分增加 `app_settings` 表的简要说明：
```markdown
### `app_settings` 表
全局设置表，存储 `ocr_engine`（全局 OCR 引擎选择）、`interval_seconds`（全局采集频率）等配置。
```

### 步骤 3：更新 OCR 引擎与数据集
- 在“OCR 引擎”表格中，将 `ddddocr` 的优先级提升，并标记为“✅ 可用（抗干扰/艺术字兜底）”。
- 在表格下方补充自动样本收集机制：“*系统支持自动将纯数字的截图裁剪保存至 `data/ocr_datasets/` 目录下，作为后续 AI 微调的高质量训练集。*”

### 步骤 4：更新采集工作流与 Edge 机制
- 在“采集工作流”的调度器流程中，将 `每 task.interval_seconds 秒触发一次` 修改为 `每 interval_seconds(全局设置) 秒触发一次`。
- 在“Edge 会话模式”或“已知限制”部分，补充说明：
  - **严格单页策略**：受控 Edge 会自动关闭额外标签页，仅保留一个主业务页或登录页。
  - **5秒超时降级**：内置 Playwright 截图 5 秒超时自动取消动画禁用重试的机制，解决字体加载死锁问题。

## 4. 验证方式
- 审查修改后的 `README.md`，确认改动准确且排版（Markdown 表格、列表）没有损坏。
- 确认内容保持了“总览”的简洁性，没有过度引入本该在“全量说明书”中的细节代码级解释。