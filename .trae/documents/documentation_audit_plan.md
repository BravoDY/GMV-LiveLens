# 深度检查与文档更新计划

## 1. 目标与背景
基于前面对最新代码库（特别是 `backend/main.py`、`backend/services/store.py` 和 `backend/services/scheduler.py`）的深层审查，发现 `GMV-LiveLens项目全量说明书.md` 依然遗漏了最近关于“全局设置”和“最新预览图拉取”的改动。为了确保文档作为 AI 代理和接手人员的绝对事实来源，我们需要将这些缺失的细节补充进去。

## 2. 当前遗漏的内容分析
1. **数据库表缺失**：`store.py` 中已经新增了 `app_settings` 表，用于持久化全局采集频率（`interval_seconds`）和 OCR 引擎选择（`ocr_engine`）。说明书中尚未体现该表。
2. **API 遗漏**：
   - `GET /api/settings` 和 `POST /api/settings` 未记录。
   - `GET /api/task-previews/{filename}` 未记录（用于前端获取最近一次截图的预览）。
3. **配置逻辑变更说明不足**：虽然 H 章节提到了前端加入了全局设置，但在 F 章节（配置系统）中，尚未明确说明 `shops.csv` 中的 `interval_seconds` 已经被全局 `app_settings` 的设置覆盖（通过 `scheduler.py` 中的 `global_interval` 逻辑）。

## 3. 拟执行的变更 (Proposed Changes)
目标文件：`C:\Users\yjd22\Desktop\python项目\GMV-LiveLens\.trae\documents\GMV-LiveLens项目全量说明书.md`

### 步骤 1：补充数据库表说明
在 **E. 数据模型与数据库** 的 “三张表” 标题下，改为 “四张表”，并补充 `app_settings` 表结构：
```markdown
#### `app_settings` — 全局设置表

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | TEXT PK | 配置键名（如 `ocr_engine`, `interval_seconds`） |
| `value` | TEXT | 配置的字符串值 |
```

### 步骤 2：更新配置逻辑的说明
在 **F. 配置系统** 中关于 `shops_default.json / shops.csv 字段说明` 的表格下方，增加关于全局设置覆盖的说明：
> **注意：全局采集频率覆盖**
> 虽然 `shops.csv` 中仍保留 `interval_seconds` 字段，但目前系统调度器已升级为采用全局采集频率（存储在 `app_settings` 中，默认 0.5 秒）。该全局设置会覆盖单个任务配置的时间间隔，以便于大促期间统一调整。

### 步骤 3：补充缺失的 API 端点
在 **L. API 全量清单** 中进行补充：
- 将“系统与健康检查”改为“系统与全局设置类”，并补充：
```markdown
GET  /api/settings                  获取全局设置（OCR引擎、采集频率等）
POST /api/settings                  更新全局设置
```
- 在“OCR 与预览类”中补充：
```markdown
GET  /api/task-previews/{filename}  获取指定截图文件的预览图
```

## 4. 验证方式
- 阅读修改后的 `GMV-LiveLens项目全量说明书.md`，检查 Markdown 格式是否正确，内容是否清晰且符合当前代码事实。
- 确认没有其他遗漏的核心 API。
