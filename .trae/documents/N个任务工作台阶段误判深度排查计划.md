# N个任务工作台阶段误判深度排查计划

## 1. 需求理解
- 目标不是只解释“儿童旗舰店为什么这样”，而是把这个问题上升为系统性问题来排查：既然一个任务会出现“任务管理状态”和“采集配置工作台状态”不一致，那么同类的 N 个 `remote_edge` 任务都可能出现同样问题。
- 成功标准：
  - 明确根因是否为通用逻辑缺陷，而不是个别店铺数据异常。
  - 给出一套能覆盖全部 `remote_edge` 任务的修复方案。
  - 修复后，任务管理卡片、采集配置工作台、店铺切换下拉、待处理统计、下一步提示保持同一套状态语义。

## 2. 当前项目结构判断
- `frontend/core.js`
  - 定义工作台阶段判断 `setupStageMeta()`
  - 定义待处理统计 `buildSetupSummary()`
  - 当前这里是“工作台状态口径”的根源
- `frontend/config.js`
  - 渲染采集配置工作台
  - 使用 `setupStageMeta()` 决定顶部状态、下一步文案、按钮显示、切店标签、摘要统计
- `backend/main.py`
  - 已经提供真实 Edge 页签状态语义
  - 当前能区分：
    - `remote_page_not_found`
    - `edge_login_page_bound`
    - `edge_page_bound`
    - `edge_target_page_ready`
- `frontend/app.js`
  - 每次快照刷新时会调用 `buildSetupSummary()`，所以一旦 `setupStageMeta()` 逻辑有偏差，整套工作台都会被带偏

## 3. 当前状态分析

### 3.1 已确认的根因
- 采集配置工作台当前并不是按任务真实状态来判断阶段，而是按下面这套简化逻辑：
  - 没有 `page_id` -> `待绑定`
  - 有 `page_id` 且仍是默认框选 -> `待标定`
  - 否则 -> `已完成`
- 对应代码在 `frontend/core.js` 的 `setupStageMeta()`：
  - `if (!task.page_id) -> pending_bind`
  - `if (isTaskUsingDefaultCalibration(task)) -> pending_calibrate`
  - `else -> completed`
- 这意味着工作台完全忽略了后端已经返回的真实状态：
  - `edge_login_page_bound`
  - `edge_page_bound`
  - `edge_target_page_ready`

### 3.2 为什么儿童旗舰店会显示“待标定”
- 儿童旗舰店当前真实状态是：
  - `status = edge_login_page_bound`
  - `page_url = sycm ... login.htm`
- 但它的框选参数仍然是默认值，因此工作台按旧逻辑把它判成了 `待标定`。
- 这不是因为它真的已经到了“可标定目标业务页”阶段，而是因为“登录页 + 默认框”在旧逻辑下被误归类了。

### 3.3 为什么官方旗舰店会显示“已完成”
- 官方旗舰店当前真实状态同样是：
  - `status = edge_login_page_bound`
  - `page_url = sycm ... login.htm`
- 但它历史上已经保存过非默认框选参数，所以旧逻辑直接把它判成了 `已完成`。
- 本质上，这个“已完成”也是误判，因为它当前绑定的是登录页，不是目标业务页。

### 3.4 为什么这是 N 个任务的系统性风险
- 只要某个 `remote_edge` 任务满足以下任一条件，就会出现类似错判：
  - 已自动恢复到登录页，但仍保留 `page_id`
  - 已绑定到非目标业务页/中间页，但仍保留 `page_id`
  - 历史上保存过非默认框选参数
  - 历史上还停留默认框选参数
- 因此这个问题不是“儿童旗舰店特例”，而是所有使用真实 Edge 会话绑定页签的任务都会受到同一套错误阶段模型影响。

## 4. 最佳实现方案

### 4.1 总体策略
- 不再让工作台自己推断业务阶段，而是优先消费后端已生成的真实状态语义。
- 用“任务真实状态 + 是否仍为默认框选”组成两层判断：
  - 第一层：任务现在绑定的是什么页
  - 第二层：如果已经是目标业务页，再判断是否完成标定

### 4.2 建议的新阶段模型
- `pending_bind`
  - 没有 `page_id`
  - 含义：还没有任何可用绑定页
- `pending_login`
  - `task.status === edge_login_page_bound`
  - 含义：Edge 会话已恢复，但当前绑定的是登录页
- `pending_target_page`
  - `task.status === edge_page_bound`
  - 含义：当前绑定的是其它页，不是目标业务页
- `pending_calibrate`
  - `task.status === edge_target_page_ready` 且仍为默认框选
  - 含义：目标业务页已就绪，但还没完成 OCR 区域标定
- `completed`
  - `task.status === edge_target_page_ready` 且已完成非默认框选
  - 含义：目标业务页已就绪，框选也已完成

### 4.3 具体修改文件与职责

#### 文件一：`frontend/core.js`
- 修改内容：
  - 重构 `setupStageMeta()`
  - 重构 `buildSetupSummary()`
  - 让 `setupQueue` 的入队逻辑按新阶段模型运行
- 设计原因：
  - 这是工作台所有状态判断的源头，必须在这里统一口径
- 不推荐的简单方案：
  - 只在 `config.js` 改文案
  - 原因：这样表面提示变了，但摘要统计、切店标签、待处理队列仍然错

#### 文件二：`frontend/config.js`
- 修改内容：
  - 让 `setupFlowState()` 和 `renderSetupWorkbench()` 支持新阶段
  - 根据 `pending_login / pending_target_page / pending_calibrate / completed` 输出不同的：
    - 当前状态
    - 下一步提示
    - 工作台按钮显示
    - 摘要统计文案
    - 切店下拉标签
- 设计原因：
  - 工作台是用户直接操作入口，必须把“登录页”和“业务页”差异说清楚

#### 文件三：必要时补充 `frontend/app.js`
- 修改内容：
  - 检查是否有依赖旧 `setupSummary` 结构或旧状态标签的提示文案
  - 同步修正与工作台状态相关的提示
- 设计原因：
  - 避免任务管理和采集配置再次出现文案不一致

### 4.4 状态统计口径
- 为避免 UI 改动过大，可以先保持统计字段数量不变，但改含义：
  - `待绑定`
    - 包含 `pending_bind + pending_login + pending_target_page`
  - `待标定`
    - 只统计真正已到目标业务页但还没框选完成的任务
  - `已完成`
    - 只统计真正已到目标业务页并已完成框选的任务
- 更优但改动略大的方案：
  - 新增一类统计“待登录/待业务页”
- 本轮建议先用兼容口径，先把错判修掉，再考虑 UI 扩展

## 5. 风险评估
- 主要风险：
  - 修改 `setupStageMeta()` 会影响工作台所有入口，包括：
    - 待处理统计
    - 自动聚焦下一家
    - 切店标签
    - 步骤卡片高亮
    - 按钮显隐
- 兼容风险：
  - 历史任务可能没有新的 `task.status`
  - 需要保留旧兜底逻辑，避免老任务直接失去阶段判断
- 功能风险：
  - 如果只修状态标签，不同步修 `setupFlowState()`，仍会出现“状态是待登录，但下一步却提示生成预览”的冲突

## 6. 执行计划
1. 以 `task.status` 为主，重构 `frontend/core.js` 中的阶段判定函数。
2. 调整 `buildSetupSummary()` 和 `setupQueue`，保证摘要和待处理顺序符合新阶段模型。
3. 重构 `frontend/config.js` 的工作台步骤提示、按钮显隐和切店标签，避免“登录页却提示生成预览”。
4. 为缺失新状态的历史任务保留回退逻辑，避免一次性破坏旧数据。
5. 用以下场景逐项验证：
   - 无 `page_id`
   - 登录页绑定
   - 非目标页绑定
   - 目标业务页 + 默认框
   - 目标业务页 + 非默认框
6. 复查任务管理与采集配置两处文案是否一致，避免再次产生认知冲突。

## 7. 验证步骤
- 代码验证：
  - `setupStageMeta()` 必须优先读取 `task.status`
  - `buildSetupSummary()` 不能再把 `edge_login_page_bound` 算成 `待标定/已完成`
- 场景验证：
  1. `官方旗舰店`
     - 当前 `edge_login_page_bound`
     - 工作台应显示“待登录”或等价直白文案，不能再显示“已完成”
  2. `儿童旗舰店`
     - 当前 `edge_login_page_bound`
     - 工作台应显示“待登录”，不能再显示“待标定”
  3. 目标业务页 + 默认框
     - 应显示“待标定”
  4. 目标业务页 + 非默认框
     - 应显示“已完成”
  5. 非目标页绑定
     - 应显示“待切业务页”或等价文案
- 最终验收标准：
  - 任意一个 `remote_edge` 任务，只要任务管理卡片显示“已恢复到登录页/其它页/业务页”，采集配置工作台、切店下拉、摘要统计、下一步提示都必须与其一致。

