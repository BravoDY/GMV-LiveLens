## Summary

- 目标 1：让点击 `启动Edge` 后，浏览器默认跳转到 `shops.csv` 中定义的目标 URL，而不是始终打开 `edge://newtab/`。
- 目标 2：让任务管理中的每个任务默认带上来自 `shops.csv` 的目标网页地址，但只写入 `page_url`，不强制立即绑定真实 `page_id`。
- 目标 3：保留 `url_patterns / url_must_contain` 的原始职责，只用于扫描已打开标签页时做候选匹配与筛选，不再混用为“默认打开地址”。
- 已确认决策：
  - 默认打开地址采用**新增独立字段**，不复用 `url_patterns`
  - 任务默认只写入 `page_url`，不自动强绑 `page_id`

## Current State Analysis

### 1. `shops.csv` 当前字段语义

- 文件：`data/shops.csv`
- 当前事实：
  - 现有列只有 `platform, shop_name, keyword_hint, url_patterns, url_must_contain, enabled`
  - 你当前 CSV 中：
    - 天猫行的 `url_patterns` 已经是完整 URL，例如 `https://sycm.taobao.com/datawar/screen.htm`
    - 京东、抖音等行的 `url_patterns` 则是多个域名/片段，例如 `jd.com/merchant;shangzhi.jd.com;pop.jd.com`
- 结论：
  - 当前 `url_patterns` 既包含“完整 URL”又包含“匹配片段”，语义并不统一
  - 如果直接把它拿来当默认打开地址，京东/抖音等平台会变成不可执行或不稳定的 URL

### 2. `url_patterns / url_must_contain` 当前实际用途

- 文件：`backend/services/shop_config.py`
- 当前事实：
  - `ShopConfig` 会把 `url_patterns`、`url_must_contain` 从 CSV 读出来，见 `load_shop_configs()`
  - `to_task_payload()` 也会把这两个字段带到内存字典中，但不会带入任务最终落库字段
- 文件：`backend/main.py`
- 当前事实：
  - `/api/shops/match` 会扫描某个 `edge_session` 里的所有标签页
  - `_url_score()` 用法是：
    - `url_must_contain`：所有关键字都必须出现在 URL 中，否则得分为 0
    - `url_patterns`：每命中一个 pattern 就累加 1 分
  - 最终候选页按得分排序，返回给绑定工作台
- 结论：
  - **当前这两个字段只用于“扫描现有标签页后的自动匹配打分”**
  - **它们目前完全不参与 Edge 启动时的默认跳转**

### 3. 任务当前为什么没有默认页面地址

- 文件：`backend/services/shop_config.py`
- 当前事实：
  - `to_task_payload()` 会明确把 `page_id`、`page_url`、`page_title` 初始化为空字符串
- 文件：`backend/services/store.py`
- 当前事实：
  - `sync_tasks_with_shop_configs()` 会从 `ShopConfig` 同步任务
  - 但它显式过滤掉 `url_patterns`、`url_must_contain`、`debug_port`、`user_data_dir`
  - 同步字段列表 `synced_fields` 中也没有任何“默认目标 URL”相关字段
  - `upsert_task()` 的 `page_url` 来自 payload；如果 payload 里是空，就会一直为空
- 结论：
  - **任务初始化时没有默认 URL 来源**
  - **任务的 `page_url` 现在只会在手动/自动绑定真实标签页后才有值**

### 4. Edge 当前启动时为什么不会去 `shops.csv` 的 URL

- 文件：`backend/collectors/remote_edge.py`
- 当前事实：
  - `_start_edge()` 当前启动参数里固定使用 `--new-window edge://newtab/`
  - 也就是说，不管任务或 CSV 怎么写，当前启动 Edge 默认都是新标签页
- 结论：
  - **当前代码没有任何“按店铺目标 URL 启动”的链路**

### 5. 任务绑定当前是“真实标签页绑定”，不是“目标 URL 绑定”

- 文件：`backend/main.py`
- 当前事实：
  - `/api/shops/bind` 只会把真实页面的 `page_id/page_url/page_title/edge_session_id` 写回任务
  - `/api/tasks/{task_id}/rebind-page` 也是写真实页面绑定结果
- 结论：
  - 当前系统里：
    - `page_url` 更像“当前已绑定真实页面地址”
    - 而不是“来自 CSV 的期望目标地址”
  - 如果要把 CSV 目标地址默认写入任务，需要明确区分“默认期望地址”和“当前真实绑定地址”的职责边界

## Proposed Changes

### 1. 为 `shops.csv` 新增独立默认打开地址字段

- 文件：`data/shops.csv`
- 文件：`backend/services/shop_config.py`
- 计划：
  - 新增字段，例如 `default_page_url`
  - `load_shop_configs()` 读取该字段
  - `ShopConfig` dataclass 增加 `default_page_url`
  - `to_task_payload()` 把它带入任务初始 payload
- 为什么：
  - 避免继续混用 `url_patterns`
  - 兼容你现在“天猫写完整 URL、京东/抖音写匹配片段”的现状

### 2. 保持 `url_patterns / url_must_contain` 只做匹配规则

- 文件：`backend/main.py`
- 文件：`backend/services/shop_config.py`
- 计划：
  - 保持 `/api/shops/match` 里的现有评分逻辑不变
  - 文档与注释上明确说明：
    - `url_patterns`：候选页打分规则
    - `url_must_contain`：候选页硬性筛选条件
    - `default_page_url`：启动后默认打开地址
- 为什么：
  - 避免一个字段承担两种职责，后续 CSV 越写越乱

### 3. 让任务在同步时默认写入 CSV 的目标 URL

- 文件：`backend/services/store.py`
- 文件：`backend/services/shop_config.py`
- 计划：
  - `to_task_payload()` 增加来自 `default_page_url` 的默认 `page_url`
  - `sync_tasks_with_shop_configs()` 的同步字段增加 `page_url`
  - 仅在“任务尚未绑定真实页面”或“当前 `page_id` 为空”时，用 CSV 的 `default_page_url` 更新 `page_url`
  - 若任务已经绑定了真实页面，可根据设计选择保留当前真实绑定，不盲目覆盖
- 为什么：
  - 你要求“任务管理中每个任务的网页都绑定为 shops.csv 的 URL 地址”
  - 但又不希望强绑 `page_id`，因此最合理的是先让任务拥有“默认目标 page_url”

### 4. 让启动 Edge 默认优先打开任务/会话对应的目标 URL

- 文件：`backend/collectors/remote_edge.py`
- 文件：`backend/main.py`
- 文件：`backend/services/store.py`
- 计划：
  - 给 `RemoteEdge` 增加“启动目标 URL”参数输入能力
  - `启动Edge` 时，不再一律打开 `edge://newtab/`
  - 目标 URL 优先级建议：
    1. 当前任务的 `page_url`（来自 CSV 默认 URL 或后续真实绑定）
    2. 对应店铺配置的 `default_page_url`
    3. 最后才回退到 `edge://newtab/`
  - 平台批量启动时，每个任务使用自己的目标 URL
- 为什么：
  - 这样才能做到“点击启动后就落到店铺后台目标页”
  - 同时保持单任务、多任务行为一致

### 5. 明确“默认目标 URL”与“真实绑定 URL”的落库策略

- 文件：`backend/models.py`
- 文件：`backend/services/store.py`
- 文件：`backend/main.py`
- 计划：
  - 评估是否需要新增单独字段，例如：
    - `target_page_url` 或 `expected_page_url`
  - 推荐方案：
    - 新增 `target_page_url` 保存 CSV 默认目标地址
    - 现有 `page_url` 继续保留为真实绑定页地址
  - 如果暂时不新增字段，则需要在实现中非常小心：
    - 避免 `page_url` 同时被当作“目标地址”和“真实已绑定地址”导致语义冲突
- 为什么：
  - 这是本次需求里最核心的长期可维护性问题
  - 如果继续复用 `page_url`，短期能跑，但后续绑定页与目标页会互相覆盖

### 6. 调整任务管理与配置页文案，让用户理解三类 URL 字段

- 文件：`frontend/app.js`
- 文件：`frontend/config.js`
- 文件：可能涉及 `README.md`
- 计划：
  - 在任务管理或配置页中明确展示：
    - 默认目标 URL
    - 当前真实绑定 URL
    - 当前绑定状态
  - 说明：
    - 启动 Edge 打开的是默认目标 URL
    - 任务实际采集依赖的仍是最终绑定页
- 为什么：
  - 否则从 UI 上看，用户很容易以为“page_url 就一定等于当前实时绑定页”

## Assumptions & Decisions

- 已确认决策：
  - 默认打开地址采用新增独立字段，不复用 `url_patterns`
  - 任务默认只写入 URL，不自动强绑 `page_id`
- 已确认的代码事实：
  - `url_patterns / url_must_contain` 目前只在 `/api/shops/match` 中用于候选匹配打分
  - `sync_tasks_with_shop_configs()` 当前不会把这些字段同步进任务落库字段
  - `RemoteEdge._start_edge()` 当前固定打开 `edge://newtab/`
- 关键设计判断：
  - 如果长期看项目可维护性，最好新增 `target_page_url`
  - 若只把 CSV URL 直接写入 `page_url`，会与“真实绑定页 URL”职责混淆

## Verification steps

### 1. CSV 语义验证

- 修改 `shops.csv`，为至少一个天猫店铺填写 `default_page_url`
- 保持 `url_patterns` 为现有匹配规则
- 验证 CSV 读取后：
  - `default_page_url` 被正确解析
  - `url_patterns / url_must_contain` 仍可正常读取

### 2. 任务同步验证

- 执行店铺同步流程
- 验证：
  - 任务管理中的对应任务默认拥有 CSV 目标 URL
  - 未绑定真实页面时，任务显示的是 CSV 默认 URL
  - 已绑定真实页面时，不会被无意覆盖

### 3. 启动 Edge 验证

- 对单个任务点击 `启动Edge`
- 验证：
  - 启动后默认打开该任务对应的目标 URL
  - 若缺少目标 URL，才回退到 `edge://newtab/`
- 对平台批量 `启动Edge`
- 验证：
  - 每个任务/会话都尽量打开各自的目标 URL

### 4. 绑定匹配验证

- 打开目标后台页后执行 `/api/shops/match`
- 验证：
  - `url_patterns / url_must_contain` 仍然只负责候选页筛选和打分
  - 自动匹配结果不因默认打开 URL 改造而被破坏

### 5. 回归验证

- `显示Edge / 隐藏Edge / 关闭Edge` 行为不受影响
- 现有多会话 `edge_session_id` 隔离不受影响
- 手动重新绑定页面、预览页面、OCR 采集流程不受影响

