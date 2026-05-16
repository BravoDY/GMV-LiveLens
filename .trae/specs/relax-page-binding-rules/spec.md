# Relax Page Binding Rules Spec

## Why
目前系统在“采集配置”中绑定页面时，会严格校验页面的 URL 是否匹配目标业务页，或是否停留在登录页。如果不符合预期（例如电商平台更新了后台 URL，导致被判定为非目标页或“旧版本”），系统会阻塞用户进行“生成预览”和“测试 OCR”等后续操作。用户希望获得充分的自由度：只要是当前受控浏览器中的页面，不判断新旧，只要用户选择绑定，就可以直接进行截图和 OCR 采集。

## What Changes
- 修改前端 `config.js`，在工作台流程中移除 `login_required` 和 `target_page_required` 的强制拦截，只要已绑定页面，直接允许生成预览。
- 修改后端 `main.py`，在 `_task_runtime_for_bound_page` 中，只要页面已绑定，统一返回 `edge_target_page_ready` 状态，不再细分登录页或非目标业务页。
- 修改后端 `main.py` 的候选页评估逻辑 `_build_task_page_candidates`，只要 `bound_exists`，统一标记为 `page_selected`，移除对 `is_login_page` 等状态的特殊阻塞提示。
- 优化后端关于“旧页签”的提示文案，避免给用户造成困扰。

## Impact
- Affected specs: 采集工作台配置流程、Edge 页面绑定和状态评估逻辑。
- Affected code: 
  - `frontend/config.js`
  - `backend/main.py`

## MODIFIED Requirements
### Requirement: 页面绑定与预览流程
系统不再强制校验绑定的 Edge 页面是否匹配特定的业务 URL 规则。
- **WHEN** 用户在采集配置页选中任意一个当前打开的 Edge 页签并点击“使用此页面”进行绑定时
- **THEN** 系统应立即接受绑定，并在前端工作台中直接显示“步骤 2：生成预览”和后续 OCR 框选流程，不可拦截。
- **THEN** 后端运行状态应统一标记为 `edge_target_page_ready`，允许定时调度器对该页面执行自动截图采集。
