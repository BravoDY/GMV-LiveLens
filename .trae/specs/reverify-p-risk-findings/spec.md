# P级问题复核 Spec

## Why
需要对上一轮 P0/P1/P2 审查结论逐条复查，确保结论基于事实证据且分级准确。

## What Changes
- 输出一份“证据链复核报告”，逐条对应 P 级问题
- 明确每条问题的复核方法、证据来源与是否成立
- 对不成立或需要降级的项给出理由

## Impact
- Affected specs: 审查报告输出、风险分级口径
- Affected code: 无代码改动

## ADDED Requirements
### Requirement: 复核报告
系统 SHALL 提供逐条 P 级问题的复核结论与证据链。

#### Scenario: Success case
- **WHEN** 触发复核流程
- **THEN** 每个 P 级问题都有“是否成立 + 证据 + 结论”的说明

## MODIFIED Requirements
### Requirement: 审查结论准确性
审查结论必须基于可复现的证据链，且区分“已确认事实”与“需要业务确认的推断”。

## REMOVED Requirements
### Requirement: 仅凭经验下结论
**Reason**: 容易导致误判  
**Migration**: 统一采用“证据链 + 可复现步骤”作为结论依据
