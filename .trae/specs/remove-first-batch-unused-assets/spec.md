# 最小风险清理第一批 Spec

## Why
上一轮无用代码与无用文件审计已经识别出一批高置信、低副作用的清理对象，包括孤立文件、零调用函数和不可达旧实现。为了避免一次性删除过多历史残留造成回归风险，本次只处理第一批已确认“未被任何引用”的对象，不触碰仍需人工确认的样式残片、休眠功能和人工工具脚本。

## What Changes
- 删除根目录一次性临时校验脚本 `tmp_verify_target_consistency.py`。
- 删除前端孤立演示页 `frontend/store-card-top-flash-demo.html`。
- 删除未被引用的前端图标资源 `frontend/favicon.svg`。
- 删除 `backend/main.py` 中零调用函数 `_select_auto_rebind_candidate()`。
- 删除 `backend/main.py` 中已经被 `edge_binding.py` 取代、且位于 `return` 之后的不可达旧实现代码块。
- 删除 `backend/collectors/window_control.py` 中零调用的进程清理辅助函数。
- 补做最小风险验证：确认服务入口、前端主页面、Edge 绑定主链和窗口控制主链不受影响。

## Impact
- Affected specs: 无用代码清理、前端静态资产治理、Edge 绑定逻辑收敛、窗口控制代码瘦身
- Affected code:
  - `tmp_verify_target_consistency.py`
  - `frontend/store-card-top-flash-demo.html`
  - `frontend/favicon.svg`
  - `backend/main.py`
  - `backend/collectors/window_control.py`

## ADDED Requirements
### Requirement: 仅清理高置信无引用对象
系统 SHALL 只清理上一轮审计中已确认“未被任何引用”的首批对象，不得顺带删除需要人工确认的文件、样式或功能。

#### Scenario: 清理首批对象
- **WHEN** 执行本次清理
- **THEN** 只允许删除高置信对象和不可达代码
- **AND** 不得扩大到 `backend/tools`、中低置信前端样式残片或休眠功能

### Requirement: 保持主链路不变
系统 SHALL 在清理后继续保持 FastAPI 主入口、前端主入口、Edge 绑定主链和窗口控制主链可用。

#### Scenario: 清理后验证主入口
- **WHEN** 完成清理并执行静态检查或最小回归
- **THEN** `backend.main:app` 仍可通过诊断检查
- **AND** `frontend/index.html` 仍引用现有正式脚本和 favicon 资源
- **AND** Edge 绑定相关 API 不因删除不可达旧逻辑而报错

### Requirement: 代码删除必须可解释
系统 SHALL 为每一项被删除的文件或代码块保留“为何确认未被引用”的证据说明，便于后续追溯。

#### Scenario: 删除零调用函数
- **WHEN** 删除 `backend/main.py` 或 `window_control.py` 中的函数
- **THEN** 需要确认全仓搜索不存在调用链
- **AND** 真实主链已有替代实现或不存在入口依赖

## MODIFIED Requirements
### Requirement: 无用代码清理策略
无用代码清理从“先做只读审计”推进到“执行第一批最小风险落地”，范围限定为高置信对象，且必须伴随静态验证和最小回归。

## REMOVED Requirements
### Requirement: 首批清理阶段保留所有高置信孤立对象不动
**Reason**: 审计已经完成，且已识别出一批风险较低的可清理对象，继续全部保留会增加维护噪音。  
**Migration**: 先删除第一批高置信对象，再根据结果决定是否进入第二批清理。
