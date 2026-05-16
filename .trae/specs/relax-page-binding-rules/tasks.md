# Tasks

- [x] Task 1: 修改后端页面运行状态评估逻辑
  - [x] 编辑 `backend/main.py` 中的 `_task_runtime_for_bound_page` 函数。
  - [x] 移除对 `flags.get("is_target_page")` 和 `is_login_page` 的条件分支。
  - [x] 无论页面类型如何，只要进入该函数（即已绑定），直接返回 `status: edge_target_page_ready`。
- [x] Task 2: 修改后端候选页签流程逻辑与文案
  - [x] 编辑 `backend/main.py` 中的 `_build_task_page_candidates` 函数。
  - [x] 移除对 `current_bound_page.get("is_login_page")` 和非目标页的 `elif` 拦截分支，只要 `task.page_id and bound_exists` 为真，统一设置为 `flow_state = "page_selected"`。
  - [x] 将代码中出现的“旧页签”相关提示文案（如 `next_action = "当前任务记录的是旧页签..."`）修改为更清晰的表述（如“原绑定页签已失效”）。
- [x] Task 3: 修改前端采集配置工作台流程
  - [x] 编辑 `frontend/config.js` 中的 `setupFlowState` 函数。
  - [x] 删除针对 `pending_login` / `login_page_bound` 以及 `pending_target_page` / `page_bound_non_target` 的 `if` 拦截判断块。
  - [x] 确保代码可以顺畅地走到 `key: "preview"` 或后续步骤。
- [x] Task 4: 综合冒烟测试与系统验证
  - [x] 测试场景 1：在浏览器中打开非业务页（如百度或 about:blank），并在 UI 界面尝试绑定，验证系统是否允许绑定并直接进入“生成预览”状态。
  - [x] 测试场景 2：验证后端 `rebind_page` 和 `shops_bind` 接口的执行结果，确认是否能正常返回 `edge_target_page_ready`，无拦截阻断。
  - [x] 测试场景 3：验证关闭页签或重启浏览器后，系统对失效页签的提示文案是否符合预期，不再包含引起歧义的“旧页签/旧版本”表述。
  - [x] 测试场景 4：开启调度器，验证对非目标业务页的自动定时截图和 OCR 功能是否不受阻碍、正常执行。
  - [x] 依据测试结果排查隐藏的边界 Bug，并执行必要的性能或日志优化。
