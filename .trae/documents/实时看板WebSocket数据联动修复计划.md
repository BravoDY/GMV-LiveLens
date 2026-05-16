# 实时看板数据不联动大屏只读和OCR — 根因与修复计划

## 一、现象

- 后端调度器已正确运行，`capture_once` 写入 SQLite 成功
- 但前端实时看板的 GMV 数字不自动更新
- 手动刷新浏览器 `/` 页面后才能看到最新值

## 二、根因分析

### 数据流追踪

```
后端 scheduler._run_loop()
  └─ capture_once() → store → SQLite ✅
  └─ _notify() → broadcast_snapshot()        [common.py:L203-L214]
       └─ for ws in clients: ws.send_json()  [common.py:L208-L210]
            └─ clients 集合始终为空 ❌
```

### 两条关键证据

1. **后端 WebSocket 广播机制完整** — [common.py:L24](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/routers/common.py#L24) 定义了 `clients: set[WebSocket] = set()`，[system.py:L167-L178](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/backend/routers/system.py#L167-L178) 注册了 `/ws/live` 端点，调度器通过 `_notify()` → `broadcast_snapshot()` 推送到所有连接的 WebSocket 客户端。

2. **前端没有任何 WebSocket 客户端代码** — 全项目搜索 `new WebSocket` / `WebSocket`：**零结果**。`clients` 永远为空。

3. **内部页面也没有 HTTP 轮询** — [app.js:L82-L108](file:///c:/Users/yjd22/Desktop/python项目/GMV-LiveLens/frontend/app.js#L82-L108) 中 `startInternalDashboard()` 仅在页面加载时调用一次 `loadTasks()`，之后没有任何定时拉取。仅公开看板 (`/dashboard`) 有 1.2s 轮询。

### 根因结论

**实时看板数据不联动的原因是：前端从未建立与后端的实时数据通道（既无 WebSocket 也无 HTTP 轮询）。** 后端辛勤采集并广播，但无人接收。

## 三、修复方案

### 方案选择：添加 WebSocket 客户端（最优）

相比 HTTP 轮询，WebSocket 的优势：
- 实时性好（后端采集完立即推送，无需等 1.2s）
- 减少服务器负载（推送而非拉取）
- 代码量最小（~20 行）

### 实现

在 `frontend/core.js` 中新增 `connectLiveWebSocket()` 函数：

```javascript
let wsReconnectTimer = null;

function connectLiveWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setWsStatus("实时连接");
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  };

  ws.onmessage = (event) => {
    try {
      const snapshot = JSON.parse(event.data);
      if (snapshot && snapshot.type === "snapshot") {
        renderSnapshot(snapshot);
      }
    } catch {}
  };

  ws.onclose = () => {
    setWsStatus("实时断开", "bad");
    wsReconnectTimer = setTimeout(connectLiveWebSocket, 3000);
  };

  ws.onerror = () => { ws.close(); };
}
```

在 `app.js` 的 `startInternalDashboard()` 末尾调用：

```javascript
connectLiveWebSocket();
```

### 文件变更

| 文件 | 变更 |
|------|------|
| `frontend/core.js` | 新增 `connectLiveWebSocket()` 函数 |
| `frontend/app.js` | `startInternalDashboard()` 末尾调用 `connectLiveWebSocket()` |
| `frontend/index.html` | JS 版本号更新 |

## 四、验证方案

1. 刷新 `/` 页面 → 状态显示「实时连接」
2. 后端调度器自动采集 → 前端 GMV 数字实时跳动
3. `POST /api/tasks/62/capture-once` → 前端无刷新自动更新
4. 关闭服务 → 前端显示「实时断开」→ 3s 后自动重连
