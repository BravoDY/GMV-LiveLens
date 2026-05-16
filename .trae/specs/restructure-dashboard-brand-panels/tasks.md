# Tasks
- [x] Task 1: 扩展店铺配置元数据，打通 `brand` 到前端状态
  - [x] SubTask 1.1: 在 `backend/services/shop_config.py` 的 `ShopConfig` 中增加 `brand` 字段，并从 `data/shops.csv` 读取
  - [x] SubTask 1.2: 让 `/api/shops` 返回的配置对象包含 `brand`，保证 `state.shopConfigs` 可直接访问
  - [x] SubTask 1.3: 在 `frontend/core.js` 的 `liveTasks()` 映射链路中把配置侧 `brand` 合并到实时任务对象

- [x] Task 2: 重构实时看板下半区渲染结构为双品牌面板
  - [x] SubTask 2.1: 调整 `frontend/index.html` 的店铺区域容器结构，去掉“统一卡片网格”的语义入口
  - [x] SubTask 2.2: 在 `frontend/dashboard.js` 中新增按 `brand` 分组的视图模型与渲染函数
  - [x] SubTask 2.3: 将左侧固定渲染为 `大货独立店`，右侧固定渲染为 `子品牌独立店`，标题直接显示 `brand` 原文
  - [x] SubTask 2.4: 实现 `brand` 缺失或非法值时默认归入左侧的兜底逻辑
  - [x] SubTask 2.5: 确保双品牌区域都不再渲染“预留位 / 新增店铺”占位卡

- [x] Task 3: 按说明书做像素级样式复刻，并保留项目现有动态反馈
  - [x] SubTask 3.1: 在 `frontend/styles.css` 中新增品牌面板布局、面板标题、面板背景与响应式断点样式
  - [x] SubTask 3.2: 将店铺卡在新双列品牌面板中调整到与目标设计一致的间距、字号、标签与进度条节奏
  - [x] SubTask 3.3: 保留现有店铺卡的平台色、顶部边框变化反馈、数字高亮、异常态与实时刷新表现
  - [x] SubTask 3.4: 去除说明书里不适用于本项目的“按店名猜分组”“主品牌/子品牌旧标题文案”等实现

- [x] Task 4: 验证双品牌看板的结构与回归行为
  - [x] SubTask 4.1: 静态检查相关前端与后端文件的诊断结果
  - [x] SubTask 4.2: 验证顶部 Summary 保持原功能，下半区仅保留两个品牌区域
  - [x] SubTask 4.3: 验证各店铺按 `platform + shop_name + brand` 正确落位，非法 `brand` 默认落左
  - [x] SubTask 4.4: 验证 WebSocket 刷新、卡片变化动画与响应式断点未回归，且页面不存在预留位卡片

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
