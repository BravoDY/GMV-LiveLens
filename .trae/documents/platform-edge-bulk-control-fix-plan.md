# 平台总控 Edge 异常修复计划

## Summary

- 目标：修复任务管理页平台级四个总控按钮的两类问题：
  - 平台级 `关闭Edge` 误报“仍有 Edge 进程未关闭”。
  - 平台级总控处理数量与页面显示任务数不一致，出现“天猫显示 4 个任务，但只调度了 3 个 Edge”的情况。
- 成功标准：
  - 平台级 `启动Edge / 显示Edge / 隐藏Edge / 关闭Edge` 不再弹出当前这类误报。
  - 平台级总控的作用对象与任务管理页当前展示的可控 Edge 任务严格一致。
  - 若平台下存在非 `remote_edge` 任务或未绑定 `edge_session_id` 的任务，UI 要明确区分“总任务数”和“可控 Edge 数”，避免用户误解。

## Current State Analysis

### 1. 平台总控与任务页数据源不一致

- 任务管理页的分组与计数来自 `build_snapshot()` 返回的 `capture_tasks`：
  - [main.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L129-L143)
  - [store.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/services/store.py#L304-L311)
- 前端平台头部显示的 `X 个任务` 使用的是页面分组后的 `groupTasks.length`：
  - [app.js](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/app.js#L475-L496)
- 但平台总控后端实际执行对象来自 `shop_config.load_shop_configs()`，并过滤 `capture_mode == "remote_edge"`：
  - [main.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/main.py#L175-L179)
- 这意味着平台总控当前基于“配置文件中的店铺配置”执行，而页面显示基于“数据库当前任务”展示，两者天然可能错位：
  - 用户新增/改绑/保留的任务可能存在于 `capture_tasks`，但不在 `shops.csv` 中。
  - 平台下若有非 `remote_edge` 任务，页面会计入总任务数，但平台总控不会执行。

### 2. 平台级关闭误报的根因

- 进程终止逻辑在 `kill_edge_process_tree()` 中会对匹配到的多个 PID 逐个执行 `taskkill /PID ... /T /F`：
  - [window_control.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/window_control.py#L281-L318)
- 当前问题有两个：
  - 当父 PID 已经被关闭并连带杀死子进程后，后续对子 PID 的 `taskkill` 会返回“没有找到进程”，代码未把该中文返回视为成功。
  - `find_edge_process_ids()` 在没有再匹配到真实进程时，会因为 `pid` 兜底逻辑把原始 `target_pid` 重新塞回结果，导致后续“残留进程检查”出现假阳性：
    - [window_control.py](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/collectors/window_control.py#L253-L278)
- 这正好与用户弹窗里的现象一致：
  - 子进程已不存在，但被当成错误累计。
  - 最终“remaining”里仍然出现已被杀掉的根 PID。

### 3. 现有单任务链路基本正常

- 前端单任务四按钮已单独接到会话级接口：
  - [app.js](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/app.js#L824-L879)
- 用户反馈“单个任务四个按键是能够正常执行的”，说明本次重点不是单任务会话级 API，而是平台级聚合来源和批量关闭聚合逻辑。

## Proposed Changes

### 1. 统一平台总控的作用对象来源

#### 文件

- `backend/main.py`
- `backend/services/store.py`（如需补辅助函数）
- `frontend/app.js`

#### 改动内容

- 将平台总控后端执行对象从 `shop_config.load_shop_configs()` 切换为 `store.list_tasks(include_disabled=True)` 派生出来的“当前任务管理页实际任务”。
- 筛选规则改为：
  - `task.platform == platform`
  - `task.capture_mode == "remote_edge"`
  - `task.edge_session_id` 非空
- 再按 `edge_session_id` 去重，避免同一会话被重复执行。

#### 原因

- 这样平台总控与任务管理页使用同一任务源，能消除“页面显示 4 个任务，但平台总控只处理 3 个配置”的结构性偏差。
- 也能兼容后续用户手工新增任务、历史任务、改绑任务，而不是被 `shops.csv` 限死。

#### 实现方式

- 在 `backend/main.py` 中新增或替换平台控制目标构建函数，例如：
  - 从 `store.list_tasks(include_disabled=True)` 读取平台任务；
  - 过滤可控 Edge 任务；
  - 按 `edge_session_id` 去重后，再映射成 `remote_edge_manager.get_client(...)` 需要的数据。
- 如果 `store` 当前缺少直接将 `task.edge_session_id` 映射为 session 信息的便捷方法，则复用现有 `store.get_edge_session()` 即可，无需改表。

### 2. 修复批量关闭的进程误报

#### 文件

- `backend/collectors/window_control.py`
- `backend/collectors/remote_edge.py`

#### 改动内容

- 修正 `find_edge_process_ids()` 的 PID 兜底逻辑：
  - 仅在“首次寻找候选目标”时可用 `pid` 兜底。
  - 在“关闭后的残留校验”阶段，不允许因为传入 `pid` 就把一个已经不存在的 PID 重新判定为残留。
- 扩大 `taskkill` 成功容忍语义：
  - 将“没有找到进程”“找不到进程”“该进程不存在”等中文返回也视为“目标已不在”，不再记作关闭失败。
- 优化批量杀进程策略：
  - 若已找到根 PID，优先只对根 PID 执行一次 `/T /F`，让系统递归结束子进程。
  - 仅在没有根 PID 或根 PID 关闭失败时，再考虑补杀其余匹配 PID。

#### 原因

- 当前误报并不是“真没关闭”，而是“关闭完成后又把已消失的 PID 认成残留”，属于结果判定错误。
- 修复后平台级 `关闭Edge` 的失败反馈才能只反映真实未关闭进程，而不是误报。

### 3. 平台头部明确展示“总任务数”和“可控 Edge 数”

#### 文件

- `frontend/app.js`
- `frontend/styles.css`

#### 改动内容

- 平台头部保留当前 `X 个任务`，但当 `startableTasks.length !== groupTasks.length` 时，增加附加说明，例如：
  - `4 个任务 · 3 个Edge`
  - 或 `4 个任务（可控 Edge 3 个）`
- 平台级成功/失败提示文案也使用“可控 Edge 会话数”，避免用户把“总任务数”和“Edge 可控数”混为一谈。

#### 原因

- 就算后端统一改成基于任务源，也仍可能存在平台下部分任务不是 `remote_edge` 的情况。
- UI 明示可以减少误解，也方便快速判断为什么某个平台的总控不是对所有任务都生效。

### 4. 平台级聚合结果与错误信息优化

#### 文件

- `frontend/app.js`
- `backend/main.py`

#### 改动内容

- 平台级接口返回项中增加更明确字段：
  - `requested`
  - `succeeded`
  - `results`
  - 可选 `controlled_edge_tasks`
- 前端弹窗/提示对平台级错误做摘要化处理：
  - 优先显示失败数量和对应店铺名。
  - 对长错误串做适当折叠或拼接，避免一次性弹出大量 PID 错误干扰判断。

#### 原因

- 当前错误弹窗直接把所有 PID 层面的原始文本拼出来，可读性差，且掩盖了真正的根因。
- 适度摘要化后，用户可以先看“哪个店铺失败”，再在后台日志或 detail 中看具体原因。

## Assumptions & Decisions

- 决策：平台总控应以“当前任务管理页中的可控 Edge 任务”为准，而不是以 `shops.csv` 为准。
- 决策：平台级执行对象按 `edge_session_id` 去重，避免同一会话被重复操作。
- 决策：平台头部需要同时表达“总任务数”和“可控 Edge 数”，以解决认知偏差。
- 决策：`关闭Edge` 的成败判断以“关闭后是否还存在真实匹配进程”为准，不能仅依据某次 `taskkill` 的子进程报错文本。
- 假设：用户当前看到“4 个任务但只调度 3 个”，至少有一种数据源不一致或任务类型不一致的情况存在；该计划优先消除结构性错位，而不是只做表面文案修补。

## Verification Steps

- 数据源一致性验证
  - 在同一平台下，比较任务管理页显示任务数、平台头部显示的可控 Edge 数、平台 API 实际 `requested` 数是否一致。
  - 若平台下包含非 `remote_edge` 任务，确认 UI 清楚显示“总任务数”和“可控 Edge 数”差异。
- 平台级启动/显示/隐藏验证
  - 分别点击平台级 `启动Edge / 显示Edge / 隐藏Edge`，确认 `requested` 与页面可控 Edge 数一致。
- 平台级关闭验证
  - 点击平台级 `关闭Edge` 后，不再出现当前这种“父进程已杀掉但仍提示残留 PID”的误报。
  - 对关闭成功的平台，确认相应会话的调试端口不可达、目标 `msedge.exe` 进程树消失。
- 单任务回归验证
  - 单任务 `启动Edge / 显示Edge / 隐藏Edge / 关闭Edge` 继续保持正常，不被平台级修复破坏。
- 质量验证
  - 对 `backend/main.py`、`backend/collectors/window_control.py`、`frontend/app.js`、`frontend/styles.css` 做诊断检查。
  - 对后端关键文件做语法校验。
