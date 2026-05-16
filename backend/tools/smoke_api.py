"""
GMV-LiveLens API 冒烟测试脚本

用法：
    .venv\\Scripts\\python.exe backend\\tools\\smoke_api.py [--host 127.0.0.1] [--port 8100]

前提：服务已在目标端口运行。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

# ---------- 工具 ----------

def _get(base: str, path: str, timeout: float = 5.0) -> tuple[int, dict | str]:
    url = f"{base}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, str(e)


def _ws_ping(host: str, port: int, timeout: float = 5.0) -> tuple[bool, str]:
    """用原生 socket 完成 WebSocket 握手，收到第一帧即返回。"""
    import base64
    import os
    import socket
    import struct

    key = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f"GET /ws/live HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.sendall(handshake.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        if b"101" not in response:
            sock.close()
            return False, f"握手失败：{response[:200]!r}"
        # 读取第一个 WebSocket 帧（最多等 timeout 秒）
        sock.settimeout(timeout)
        header = sock.recv(2)
        if len(header) < 2:
            sock.close()
            return False, "未收到数据帧"
        payload_len = header[1] & 0x7F
        if payload_len == 126:
            ext = sock.recv(2)
            payload_len = struct.unpack(">H", ext)[0]
        elif payload_len == 127:
            ext = sock.recv(8)
            payload_len = struct.unpack(">Q", ext)[0]
        payload = b""
        remaining = min(payload_len, 4096)
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                break
            payload += chunk
            remaining -= len(chunk)
        sock.close()
        text = payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
            return True, f"收到快照，tasks={len(data.get('tasks', []))}"
        except json.JSONDecodeError:
            return True, f"收到非 JSON 帧（{len(payload)} bytes）"
    except Exception as e:
        return False, str(e)


# ---------- 测试用例 ----------

class SmokeRunner:
    def __init__(self, base: str, host: str, port: int) -> None:
        self.base = base
        self.host = host
        self.port = port
        self.results: list[tuple[str, bool, float, str]] = []

    def check(self, name: str, fn: Callable[[], tuple[bool, str]]) -> None:
        t0 = time.time()
        try:
            ok, detail = fn()
        except Exception as exc:
            ok, detail = False, f"异常：{exc}"
        elapsed = time.time() - t0
        self.results.append((name, ok, elapsed, detail))
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name:<45} {elapsed*1000:.0f}ms  {detail}")

    def run_all(self) -> int:
        print(f"\n{'='*70}")
        print(f"  GMV-LiveLens 冒烟测试  目标: {self.base}")
        print(f"{'='*70}\n")

        # T01 服务健康
        def t01():
            code, data = _get(self.base, "/api/health")
            payload = data.get("data", data) if isinstance(data, dict) else data
            ok = code == 200 and isinstance(payload, dict) and "scheduler" in payload
            return ok, f"HTTP {code}"
        self.check("T01 服务健康 /api/health", t01)

        # T02 调度器状态
        def t02():
            code, data = _get(self.base, "/api/scheduler")
            ok = code == 200 and isinstance(data, dict) and "running" in data
            return ok, f"HTTP {code}, running={data.get('running') if isinstance(data, dict) else '?'}"
        self.check("T02 调度器状态 /api/scheduler", t02)

        # T03 任务列表
        def t03():
            code, data = _get(self.base, "/api/tasks")
            ok = code == 200 and isinstance(data, dict) and "tasks" in data
            cnt = len(data.get("tasks", [])) if isinstance(data, dict) else "?"
            return ok, f"HTTP {code}, tasks={cnt}"
        self.check("T03 任务列表 /api/tasks", t03)

        # T04 Edge 会话列表（含 default_real_edge）
        # 注意：该端点对每个会话执行健康检查（6s 超时/个），11 个会话最多需 66s，timeout 设大
        def t04():
            code, data = _get(self.base, "/api/edge-sessions", timeout=90.0)
            if code != 200:
                return False, f"HTTP {code}"
            sessions = data if isinstance(data, list) else data.get("sessions", []) if isinstance(data, dict) else []
            ids = [s.get("session_id") for s in sessions if isinstance(s, dict)]
            ok = "default_real_edge" in ids
            return ok, f"HTTP {code}, sessions={len(ids)}, default_real_edge={'OK' if ok else 'MISSING'}"
        self.check("T04 Edge 会话列表含 default_real_edge", t04)

        # T05 默认 Edge 会话健康检查（允许 debug_available=false，只要 HTTP 200）
        def t05():
            code, data = _get(self.base, "/api/edge-sessions/default_real_edge/health", timeout=10.0)
            ok = code == 200
            debug_ok = data.get("debug_available") if isinstance(data, dict) else "?"
            return ok, f"HTTP {code}, debug_available={debug_ok}"
        self.check("T05 default_real_edge 健康检查", t05)

        # T06 店铺配置
        def t06():
            code, data = _get(self.base, "/api/shops")
            shops = data if isinstance(data, list) else data.get("shops", []) if isinstance(data, dict) else []
            ok = code == 200 and len(shops) > 0
            return ok, f"HTTP {code}, shops={len(shops)}"
        self.check("T06 店铺配置 /api/shops", t06)

        # T07 OCR 引擎列表（rapidocr 可用）
        # 响应格式：{"mode": "auto", "available": {"rapidocr": true, ...}, "output": "..."}
        def t07():
            code, data = _get(self.base, "/api/ocr/engines")
            available = data.get("available", {}) if isinstance(data, dict) else {}
            ok = code == 200 and available.get("rapidocr") is True
            enabled = [k for k, v in available.items() if v]
            return ok, f"HTTP {code}, available={enabled}"
        self.check("T07 OCR 引擎 rapidocr 可用", t07)

        # T08 全局设置
        def t08():
            code, data = _get(self.base, "/api/settings")
            ok = code == 200 and isinstance(data, dict) and "interval_seconds" in data
            return ok, f"HTTP {code}, keys={list(data.keys()) if isinstance(data, dict) else '?'}"
        self.check("T08 全局设置 /api/settings", t08)

        # T09 窗口列表
        def t09():
            code, data = _get(self.base, "/api/windows")
            ok = code == 200
            cnt = len(data) if isinstance(data, list) else "?"
            return ok, f"HTTP {code}, windows={cnt}"
        self.check("T09 窗口列表 /api/windows", t09)

        # T10 前端主页
        def t10():
            code, data = _get(self.base, "/", timeout=8.0)
            ok = code == 200 and isinstance(data, str) and "GMV" in data
            return ok, f"HTTP {code}, html={'含GMV' if ok else '不含GMV'}"
        self.check("T10 前端主页 /", t10)

        # T11 WebSocket 连通
        def t11():
            return _ws_ping(self.host, self.port)
        self.check("T11 WebSocket /ws/live 连通", t11)

        # T12 /api/realtime 别名
        def t12():
            code, data = _get(self.base, "/api/realtime")
            ok = code == 200 and isinstance(data, dict) and "tasks" in data
            return ok, f"HTTP {code}"
        self.check("T12 /api/realtime 别名", t12)

        # T13 缺失的 page-candidates 端点（无任务时应返回 404，不应 500）
        def t13():
            code, _ = _get(self.base, "/api/tasks/99999/page-candidates")
            ok = code in (404, 200)  # 任务不存在→404，存在→200
            return ok, f"HTTP {code}（404=任务不存在，200=找到任务）"
        self.check("T13 /api/tasks/{id}/page-candidates 端点存在", t13)

        # T14 /api/settings POST 写入再读回
        # 正确格式：{"ocr_engine": "auto", "interval_seconds": 2.0}（两个字段均需提供）
        def t14():
            url = f"{self.base}/api/settings"
            payload = json.dumps({"ocr_engine": "auto", "interval_seconds": 2.0}).encode()
            req = urllib.request.Request(url, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    post_code = resp.status
            except urllib.error.HTTPError as e:
                post_code = e.code
            # 读回验证
            get_code, data = _get(self.base, "/api/settings")
            val = data.get("interval_seconds") if isinstance(data, dict) else None
            ok = post_code in (200, 204) and float(val or 0) == 2.0
            # 恢复默认
            payload2 = json.dumps({"ocr_engine": "auto", "interval_seconds": 0.5}).encode()
            req2 = urllib.request.Request(url, data=payload2, method="POST",
                                          headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req2, timeout=5)
            except Exception:
                pass
            return ok, f"POST={post_code}, interval_seconds={val}"
        self.check("T14 /api/settings POST 写入并读回", t14)

        # 汇总
        passed = sum(1 for _, ok, _, _ in self.results if ok)
        total = len(self.results)
        print(f"\n{'='*70}")
        print(f"  结果：{passed}/{total} PASS")
        failed = [(n, d) for n, ok, _, d in self.results if not ok]
        if failed:
            print("\n  失败项：")
            for name, detail in failed:
                print(f"    [x] {name}: {detail}")
        print(f"{'='*70}\n")
        return 0 if passed == total else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="GMV-LiveLens API 冒烟测试")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()

    base = f"http://{args.host}:{args.port}"
    runner = SmokeRunner(base, args.host, args.port)
    sys.exit(runner.run_all())


if __name__ == "__main__":
    main()
