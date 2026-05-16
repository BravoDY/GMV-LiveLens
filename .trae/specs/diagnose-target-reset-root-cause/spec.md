# 目标值被重置为0根因诊断 Spec

## Why
用户反馈“目标仍显示 `--`”，与此前“已修复”结论冲突，说明链路中仍存在把目标值置空或置 0 的路径。需要明确根因并给出可验证证据，避免反复回归。

## What Changes
- 建立“目标值来源与落库链路”的诊断规范（`shops.csv` -> `load_shop_configs` -> `sync_tasks_with_shop_configs` -> `upsert_task` -> `/api/tasks` -> 前端渲染）。
- 增加“目标被回写为 0”的高风险路径识别：前端保存任务时 `target` 取值回退到 `0` 的场景。
- 输出复现条件、证据点和判定标准，区分“同步未执行”和“同步后被覆盖”两类原因。

## Impact
- Affected specs: 任务配置保存、一致性同步、实时看板目标展示
- Affected code: `frontend/config.js`, `backend/services/store.py`, `backend/services/shop_config.py`, `backend/main.py`

## ADDED Requirements
### Requirement: 目标值异常诊断闭环
系统 SHALL 提供一条可复核的诊断链路，用于解释“为何 UI 显示 `--` 而非目标值”。

#### Scenario: 目标显示为 `--`
- **WHEN** 用户在看板看到某任务目标为 `--`
- **THEN** 诊断应先验证该任务在数据库中的 `target` 是否为 `0`
- **AND** 继续验证 `/api/tasks` 的该任务 `target` 是否同样为 `0`
- **AND** 明确该值来自“未同步”还是“后续保存覆盖”

#### Scenario: 同步与覆盖冲突
- **WHEN** `shops.csv` 内目标非零，但任务记录目标为 `0`
- **THEN** 诊断应检查是否存在任务保存请求将 `target` 以 `0` 回写
- **AND** 给出对应代码路径和字段取值依据

## MODIFIED Requirements
### Requirement: 目标值修复验收口径
目标值修复不再仅以“CSV 和接口读取正常”判定通过，必须额外满足“任务保存链路不会把既有目标回写为 `0`”。

## REMOVED Requirements
### Requirement: 仅靠一次同步即可长期正确
**Reason**: 运行期仍可能有保存动作覆盖同步结果，单次同步无法保证后续一致性。  
**Migration**: 将验收改为“同步 + 保存链路双校验”，并记录覆盖路径证据。
