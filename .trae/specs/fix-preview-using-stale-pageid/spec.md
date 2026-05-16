# 修复采集配置状态不同步与店铺切换缺项 Spec

## Why
采集配置工作台当前存在两个互相关联的状态错位问题：

- 页签绑定错位：进入任务时，候选页预加载和自动恢复绑定可能已经拿到了新的 `page_id`，但前端本地任务快照没有同步更新，导致界面显示“当前页签已选中/可生成预览”，点击“生成预览”时仍发送旧 `page_id`，随后立刻被后端判定为 `remote_page_not_found` 并回退到“重新选择页面”。
- 店铺切换错位：`切换店铺` 下拉栏当前按“已有任务快照”渲染，而不是按最新店铺配置渲染。只要某个店铺配置暂时没有对应任务记录、任务快照未同步或数据库出现轻微漂移，下拉栏就会少一项，出现“明明有 4 家店，但只能切 3 家”的现象。

## What Changes
- 修正前端采集配置上下文同步逻辑：`/api/tasks/{id}/page-candidates` 返回了最新绑定后，必须同步更新当前任务在前端内存中的 `page_id/page_url/page_title/edge_session_id/status/last_reason`。
- 修正“生成预览”触发源：预览接口必须优先使用当前最新绑定上下文，而不是过期的任务快照字段。
- 增加一致性保护：当 `bindCandidates.current_binding`、`bindCandidates.task`、当前任务快照三者不一致时，工作台应以前两者中的最新绑定结果为准。
- 修正“切换店铺”下拉栏的数据来源：下拉栏必须以最新 `state.shopConfigs` 为主，而不是仅以 `configuredSetupTasks()` 的任务快照结果为主。
- 增加店铺配置缺失任务时的受控修复策略，确保配置中的店铺不会因为任务记录暂缺而从下拉栏消失。
- 增加日志与提示文案，明确区分“已恢复绑定但本地状态未同步”与“绑定页签真实失效”两类情况。
- 增加针对“自动恢复后立即生成预览”和“4 家店配置完整展示”的回归验证。

## Impact
- Affected specs: 采集配置工作台、页签绑定恢复、真实 Edge 预览生成、店铺切换下拉栏
- Affected code:
  - `frontend/config.js`
  - `frontend/edge.js`
  - `frontend/core.js`
  - `backend/main.py`

## Current Structure Analysis
- `frontend/config.js`
  - `syncTaskContext()` 会在进入当前任务时触发候选页预加载，是“进入工作台时校验绑定是否仍有效”的主入口。
  - `renderSetupWorkbench()` 决定步骤提示、按钮显隐、当前店铺摘要和 `切换店铺` 下拉栏渲染。
  - `renderSetupShopJumper()` 当前直接读取 `configuredSetupTasks()`，因此它天然受“任务快照是否完整”影响。
- `frontend/edge.js`
  - `previewRemotePage()` 是“生成预览”按钮的最终动作入口，当前优先读 `currentSetupTask().page_id`，这正是旧 `page_id` 被继续使用的风险点。
- `frontend/core.js`
  - `currentSetupTask()`、`findTaskById()`、`configuredSetupTasks()` 都建立在 `state.snapshot.tasks` 之上。
  - 只要 `state.snapshot.tasks` 未同步或少了一条任务，工作台切店、摘要、下一家排序就会与 `state.shopConfigs` 脱节。
- `frontend/app.js`
  - `renderSnapshot()` 才会整体替换 `state.snapshot`。这意味着如果某次局部接口已拿到更新后的绑定信息，但没有同步回当前快照，局部 UI 和全局任务快照就会出现分叉。
- `backend/main.py`
  - `/api/tasks/{task_id}/page-candidates` 已经具备“扫描当前页签 + 轻量 reconcile + 自动恢复绑定”的能力，是当前绑定状态的后端真相来源。
  - `/api/shops/init` 基于 `store.sync_tasks_with_shop_configs()` 做幂等补齐与修复，可作为“店铺配置存在但任务记录缺失”时的受控恢复手段。

## Recommended Implementation Strategy
- 保守改造，不重写整个采集配置状态机。
- 新增一个前端内部的“最新绑定上下文同步层”，只负责把 `page-candidates`、手动绑定结果、预览结果统一折叠回当前任务上下文。
- `previewRemotePage()` 改为从统一上下文取值，避免到处散落读取 `task.page_id`。
- `切换店铺` 下拉栏改为“以 `state.shopConfigs` 为主、用任务快照补充状态”的模式，避免继续被缺失任务拖掉店铺项。
- 对“店铺配置存在但任务记录缺失”的情况使用受控修复，不做激进的自动全量重建，避免把已有运行态和用户改动带偏。

## Risk Guardrails
- 不改 OCR 识别算法、不改截图能力、不改保存任务接口结构。
- 不重构 `setupFlowState()` 整体流程，只修正它读取的数据来源与一致性判定。
- 不让 `/api/shops/init` 变成页面加载时的无脑强制调用；如需补齐，必须有明确的触发条件与幂等保护。
- 修复后必须重点回归：
  - 页签扫描
  - 手动绑定
  - 生成预览
  - 测试 OCR
  - 保存并进入下一家
  - 切换店铺

## ADDED Requirements
### Requirement: 绑定恢复结果必须同步到前端当前任务
系统 SHALL 在候选页预加载或自动恢复绑定成功后，把最新绑定结果同步到前端当前任务上下文，确保后续预览、OCR 测试、保存使用同一份绑定数据。

#### Scenario: page-candidates 自动恢复成功
- **WHEN** `GET /api/tasks/{task_id}/page-candidates` 已为当前任务自动恢复了新的 `page_id`
- **THEN** 前端当前任务上下文必须立即更新为该新的 `page_id/page_url/page_title/edge_session_id`
- **AND** 工作台步骤、已选页签展示、预览按钮所使用的绑定来源必须一致

### Requirement: 生成预览必须使用最新绑定来源
系统 SHALL 在用户点击“生成预览”时，优先使用当前最新绑定来源，而不是仅依赖初始载入时的任务快照。

#### Scenario: 已显示已选中页签
- **WHEN** 工作台已显示某个页签为“已选中”且步骤为“生成预览”
- **THEN** 预览请求必须对应该已选中的最新 `page_id`
- **AND** 不得因为仍发送旧 `page_id` 而立即回退到“重新选择页面”

#### Scenario: 绑定真实失效
- **WHEN** 当前最新绑定来源也无法在会话中找到
- **THEN** 系统才进入“重新选择页面”
- **AND** 提示应明确说明这是当前最新绑定真实失效，而非前端本地状态落后

### Requirement: 切换店铺下拉栏必须覆盖最新店铺配置
系统 SHALL 让采集配置页的 `切换店铺` 下拉栏完整覆盖最新店铺配置中的所有店铺，而不是只展示当前已有任务快照中的子集。

#### Scenario: 配置有 4 家店但任务快照少 1 家
- **WHEN** 最新店铺配置中存在 4 家店，但当前任务快照只返回其中 3 家
- **THEN** 下拉栏仍应能完整展示这 4 家店
- **AND** 系统应提供受控修复或补齐路径，使缺失店铺可被正常进入和配置

#### Scenario: 店铺配置与任务记录完全一致
- **WHEN** 每个店铺配置都已有对应任务记录
- **THEN** 下拉栏展示顺序与数量应与 `state.shopConfigs` 保持一致
- **AND** 当前选中项、下一家队列、待处理统计口径必须一致

## MODIFIED Requirements
### Requirement: 采集配置工作台状态一致性
系统从“候选页状态与任务快照可暂时不一致”调整为“候选页状态、当前任务上下文、预览动作必须保持同一绑定来源”。只要界面显示“可生成预览”，预览请求就必须使用与界面展示一致的最新绑定信息。

### Requirement: 采集配置店铺切换入口
系统从“切换店铺依赖已有任务快照”调整为“切换店铺以最新店铺配置为主，并与任务快照进行受控对齐”。只要店铺配置里存在，该店铺就不应在下拉栏中无故消失。

## REMOVED Requirements
### Requirement: 预览动作可直接依赖旧任务快照 page_id
**Reason**: 任务快照可能落后于 `page-candidates` 的自动恢复结果，继续直接使用会造成界面显示已选中但点击后立刻失效的假成功。
**Migration**: 改为在前端维护“最新绑定上下文”，由候选页预加载、手动绑定、自动恢复三类入口统一更新，预览与保存都读取该上下文。

### Requirement: 切换店铺下拉栏只依赖已有任务快照
**Reason**: 任务快照可能少于最新店铺配置，继续直接依赖会造成店铺配置存在但下拉栏缺项。
**Migration**: 改为以最新店铺配置为主生成切换项，再把任务记录、任务修复和当前焦点状态映射到这些切换项上。

## Verification Plan
- 场景 A：`page-candidates` 自动恢复了新的 `page_id` 后，工作台立即显示正确步骤，点击“生成预览”成功。
- 场景 B：当前页签真实失效时，工作台直接进入“重新选择页面”，不再先出现假选中。
- 场景 C：`state.shopConfigs` 有 4 家天猫店而 `state.snapshot.tasks` 只缺 1 家时，切换下拉栏仍能展示 4 家。
- 场景 D：对缺失任务的店铺执行受控补齐后，该店铺可正常进入配置，并且不影响已有 3 家店的当前状态。
- 场景 E：保存并进入下一家后，下一家排序和切换下拉栏仍与最新店铺配置一致。
