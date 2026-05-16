# Tasks
- [x] Task 1: 锁定第一批可清理对象的边界
  - [x] SubTask 1.1: 复核上一轮审计结论，确认本次只处理高置信对象。
  - [x] SubTask 1.2: 再次确认每个候选项不存在静态引用、入口引用或文档声明用途。
  - [x] SubTask 1.3: 列出本次明确不处理的范围，如 `backend/tools`、需人工确认的前端样式残片和休眠功能。

- [x] Task 2: 删除高置信无引用文件
  - [x] SubTask 2.1: 删除 `tmp_verify_target_consistency.py`。
  - [x] SubTask 2.2: 删除 `frontend/store-card-top-flash-demo.html`。
  - [x] SubTask 2.3: 删除 `frontend/favicon.svg`。

- [x] Task 3: 删除后端高置信死代码
  - [x] SubTask 3.1: 删除 `backend/main.py` 中零调用函数 `_select_auto_rebind_candidate()`。
  - [x] SubTask 3.2: 删除 `backend/main.py` 中位于 `return edge_binding...` 之后的不可达旧实现代码块。
  - [x] SubTask 3.3: 删除 `backend/collectors/window_control.py` 中零调用的进程清理辅助函数。

- [x] Task 4: 做最小风险回归验证
  - [x] SubTask 4.1: 对变更文件执行诊断检查。
  - [x] SubTask 4.2: 执行与后端主入口、Edge 绑定主链相关的最小测试或脚本验证。
  - [x] SubTask 4.3: 复查前端正式入口仍只依赖保留的资源，不受删除孤立文件影响。

- [x] Task 5: 汇总本次首批清理结果
  - [x] SubTask 5.1: 记录已删除对象与删除原因。
  - [x] SubTask 5.2: 记录验证结果、剩余风险和未处理范围。
  - [x] SubTask 5.3: 明确下一批清理应继续从哪些“需人工确认”对象开始。

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 4
