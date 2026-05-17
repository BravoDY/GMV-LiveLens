# 验收检查清单

## 问题复现与量化
- [ ] 已使用浏览器 DevTools 录制导航切换流程，明确卡顿时长（ms）
- [ ] 已定位阻塞 UI 的具体 API 请求（端点 + 响应时间）
- [ ] 已明确触发条件（是否首次加载 / 特定导航切换必现 / 随机）

## 后端优化
- [ ] `GET /api/edge-sessions` 响应时间 ≤ 3s（原 2-20s）
- [ ] 每个会话健康检查超时 ≤ 5s，超时后返回降级数据而非阻塞整体响应
- [ ] MySQL `connect_timeout` 改为 5s，`read_timeout` 改为 15s
- [ ] MySQL 连接失败时周期看板 API 返回降级数据，不抛 500
- [ ] MySQL 连接池已实现（最大 5 连接），非每次新建连接

## 前端优化
- [ ] 非 `dashboard` 视图下，1.2s 轮询不触发 `renderDashboard()` 的 DOM 渲染
- [ ] 切换到 `dashboard` 视图时立即用缓存数据渲染（无白屏）
- [ ] `managerGrid` 仅在可见时渲染，非可见时保留旧快照

## 性能监控
- [ ] `switchView()` 控制台输出 `[Perf] switchView: Xms` 日志
- [ ] `api()` 和 `callEdgeAction()` 输出请求耗时日志
- [ ] 超过 2s 的慢请求输出 `[Perf] SLOW` 警告

## 回归验证
- [ ] 首次加载页面 ≤ 5s
- [ ] 反复切换三个导航 tab 各 10 次，每次 ≤ 100ms
- [ ] 周期看板数据集切换，MySQL 不可达时降级正常（不卡死）
- [ ] `smoke_api.py` 全部 14 项通过
