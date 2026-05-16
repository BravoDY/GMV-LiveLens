# dashboard-test导航栏切换实现计划

## Summary

- 目标：实现 `http://127.0.0.1:8100/dashboard-test` 的顶部导航栏切换，使测试副本看板能够在 `实时` 与 `to_date.csv` 驱动的周期数据集之间切换，并在切换后刷新同一套看板模板的数据。
- 成功标准：
  - 页面顶部能稳定显示 `实时` + 动态周期导航项。
  - 点击任一导航项后，请求正确的 `dataset_id` 并重渲染测试看板。
  - 选中态、加载态、失败态可感知，轮询刷新不丢当前选中项。
  - 本次不再额外实现 `shops.csv` 与 `shops_name.csv` 的新关联链路，按用户最新口径“可以不用关联了”处理。

## Current State Analysis

### 已确认的现状

- 测试副本页面入口已存在：`c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\test-dashboard\index.html`
  - 页面已预留导航容器：`#testDatasetNav`
  - 已加载测试副本脚本：
    - `frontend/test-dashboard/dashboard.js`
    - `frontend/test-dashboard/app.js`
- 测试副本接口已存在：`c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\routers\dashboard_test.py`
  - `GET /dashboard-test`
  - `GET /api/dashboard-test?dataset_id=...`
  - `GET /api/dashboard-datasets-test`
- 数据集构造已存在：`c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\services\dashboard_dataset.py`
  - 已固定加入 `realtime`
  - 已按 `to_date.csv.chinese_product` 生成周期数据集
  - 已输出 `dataset_id`、`title`、`dates`、`to_dates`、`start_date`、`end_date`
- 看板查询已存在：`c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\services\dashboard_query.py`
  - `build_dashboard_view(dataset_id)` 已支持：
    - `realtime`
    - `period`
  - 返回数据中已包含：
    - `datasets`
    - `selected_dataset_id`
    - `generated_at`

### 当前前端切换链路的不足

- `frontend/test-dashboard/app.js` 已能：
  - 调 `/api/dashboard-datasets-test` 渲染按钮
  - 点击按钮后更新 `window.__DASHBOARD_DATASET_ID__`
  - 调 `/api/dashboard-test?dataset_id=...`
- 但仍存在几个不完整点，导致“已有切换雏形，但还不算完整导航切换”：
  - 初始化时导航和数据分两次加载，未校准后端返回的 `selected_dataset_id`
  - 轮询刷新时只刷新当前数据，不回写导航状态和有效性校验
  - 没有显式 loading/empty/error 状态管理
  - 当前选中项不做持久化，刷新页面会回到默认 `realtime`
  - 页面虽然有测试导航样式，但 `index.html` 与 `styles.css` 存在重复定义，需统一收口，避免样式分叉

### 与用户最新要求相关的边界

- 用户已明确：本次“可以不用关联了”。
- 因此本轮导航切换实现不把精力放在：
  - `shops.csv -> shops_name.csv`
  - `companyshop_name` 新映射层
- 本轮仅保证：
  - 测试副本页面的导航交互可用
  - 切换能驱动现有测试接口返回不同 dataset 的看板数据

## Proposed Changes

### 1. 前端测试副本导航状态收口

#### 文件

- `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\test-dashboard\app.js`

#### 修改内容

- 把当前零散的 `window.__DASHBOARD_DATASET_ID__` 用法收口成统一状态管理：
  - 当前选中 `dataset_id`
  - 是否正在加载
  - 最近一次数据集列表
- 初始化流程改为：
  1. 先拉取 `/api/dashboard-datasets-test`
  2. 确定默认或已记忆的 `dataset_id`
  3. 渲染导航按钮
  4. 再拉取对应 `/api/dashboard-test?dataset_id=...`
- 点击导航时：
  - 立即切换选中态
  - 显示 loading 状态
  - 请求成功后重渲染看板
  - 请求失败则回退或保留当前有效状态，并展示失败提示
- 轮询刷新时：
  - 始终带上当前选中的 `dataset_id`
  - 不重置用户选中项
- 增加本地记忆：
  - 使用 `localStorage` 保存最近一次选择的 `dataset_id`
  - 页面刷新后优先恢复

#### 原因

- 当前页面已具备按钮与接口，但缺少完整状态机。
- 导航切换是本次的核心能力，必须保证初始化、点击、轮询、刷新 4 个阶段口径一致。

### 2. 前端测试副本导航渲染与样式统一

#### 文件

- `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\test-dashboard\index.html`
- `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\test-dashboard\styles.css`

#### 修改内容

- 统一测试导航的 class 命名和样式来源，避免目前：
  - `index.html` 里有内联样式
  - `styles.css` 里也有 `.test-dataset-chip` / `.test-dataset-nav`
- 最终收口为测试副本自己的样式文件负责导航展示：
  - 导航容器横向滚动
  - 激活态
  - loading 态
  - disabled / 错误态（如需要）
- 保持现有测试页视觉风格，不改动主看板骨架，只增强顶部导航区域。

#### 原因

- 当前导航样式定义分散，后续调试时容易出现样式不一致。
- 用户目标是“测试副本能稳定验证导航切换”，因此顶部导航必须可视化反馈明确。

### 3. 后端测试接口最小增强

#### 文件

- `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\routers\dashboard_test.py`
- `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\backend\services\dashboard_query.py`

#### 修改内容

- 保持现有测试接口路径不变，避免影响访问地址：
  - `/dashboard-test`
  - `/api/dashboard-test`
  - `/api/dashboard-datasets-test`
- 重点做最小增强：
  - 确认 `/api/dashboard-test` 返回的 `selected_dataset_id` 始终与请求参数一致或有可预期回退
  - 若前端传入非法 `dataset_id`，后端返回稳定可处理结果，不让测试页陷入异常循环
  - 如有必要，在返回结构中补充前端切换所需的最小元数据，但不改大结构

#### 原因

- 当前切换核心链路已存在，后端不需要重做，只需要保证接口在“非法参数 / 空数据集 / 周期集不存在”时足够稳定。

### 4. 测试页渲染与数据模式兼容

#### 文件

- `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens\frontend\test-dashboard\dashboard.js`

#### 修改内容

- 保持当前 `normalizePublicDashboardSnapshot()` 和 `renderSnapshot()` 主思路不变。
- 针对测试副本切换补兼容：
  - 当返回 `summary.yoy`、`selected_dataset_id`、周期摘要信息时，测试页能正确展示或至少不破坏现有总览卡
  - 当周期数据返回的 `shops` 结构较实时数据更简化时，继续映射成当前卡片模板需要的字段
- 必要时增加轻量空态文案：
  - 周期无店铺数据
  - 周期切换失败

#### 原因

- `dashboard.js` 当前已经能吃测试接口 payload，但它原本更偏向“兼容性渲染”，还缺少针对导航切换状态的明确兜底。

## Assumptions & Decisions

- 本次实现目标是“让 `/dashboard-test` 导航栏切换可用”，不是重构正式看板。
- 不新增 `shops.csv` 与 `shops_name.csv` 的关联映射逻辑；如后续需要，再单独起任务处理。
- 优先复用现有：
  - `build_dataset_overview()`
  - `build_dashboard_view(dataset_id)`
  - `normalizePublicDashboardSnapshot()`
- 导航默认选中逻辑采用：
  - 优先本地记忆的有效 `dataset_id`
  - 否则回退 `realtime`
- 样式以测试副本自身文件为准，不再继续扩大 `frontend/index.html` 或正式样式的影响范围。

## Verification Steps

- 静态核对：
  - 确认 `dashboard-test` 页面加载后能渲染导航按钮列表
  - 确认按钮数量与 `/api/dashboard-datasets-test` 返回一致
- 交互验证：
  - 点击 `实时` 能看到实时数据
  - 点击任一 `product:*` 周期按钮后，请求带上正确 `dataset_id`
  - 按钮高亮与当前 dataset 保持一致
  - 轮询刷新后不丢当前选中项
  - 刷新浏览器后能恢复上次选择
- 容错验证：
  - 数据集接口失败时导航区域给出错误反馈
  - 看板接口失败时状态条显示失败，不死循环报错
  - 无效 `dataset_id` 时前后端都能稳定回退
- 工程验证：
  - 检查修改后的 `frontend/test-dashboard/*.js`、`*.css` 无明显语法问题
  - 检查后端相关文件无新增诊断错误
