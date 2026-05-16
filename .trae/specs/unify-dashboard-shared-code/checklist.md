# Checklist

- [x] `dashboard-shared.js` 包含完整的 19+ 个共用函数且可独立运行
- [x] `dashboard.js` 瘦身后仅保留 Manager Grid 专属函数 + `renderDashboard` (266行)
- [x] `test-dashboard/dashboard.js` 瘦身后仅保留 `renderDataStatusBanner` + `renderDashboard` (47行)
- [x] `index.html` 在 core.js 后正确引入了 `dashboard-shared.js`
- [x] `test-dashboard/index.html` 在 core.js 后正确引入了 `/static/dashboard-shared.js`
- [x] `/` 页面 API：9 tasks 正常
- [x] `/dashboard` 页面 API：9 shops 正常
- [x] `/dashboard-test` 页面 API：9 shops 正常
