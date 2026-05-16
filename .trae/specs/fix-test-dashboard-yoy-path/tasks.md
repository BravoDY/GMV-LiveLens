# Tasks

- [x] Task 1: 修复 `test-dashboard/dashboard.js` `renderDashboard()` 数据读取路径
  - `state.snapshot?.platforms` → `state.snapshot?.public_dashboard?.platforms`（从 `pd` 中取）
  - `state.snapshot?.shops` → `state.snapshot?.public_dashboard?.shops`（从 `pd` 中取）
  - 更新 index.html 中 JS 版本号 → `v=20260516-yoy-path-0001`

- [x] Task 2: 验证前端渲染
  - 后端 API 各平台 YOY 独立：Summary=-23.14%, 天猫=-17.05%, 京东=29.22%, 唯品=-99.17%, 抖音=-27.07%, 得物=-56.99% ✅
  - 前端 JS 文件正确从 `state.snapshot?.public_dashboard` 读取 ✅
