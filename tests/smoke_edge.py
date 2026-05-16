"""remote_edge 文件级拆分冒烟测试。

该测试不依赖真实 Edge 登录态或调试端口，重点验证：
1. 旧导入路径仍然可用；
2. 新包导出面完整；
3. 基础非浏览器逻辑与数据结构保持兼容。
"""

from __future__ import annotations

# ruff: noqa: E402
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.collectors.edge import RemoteEdge as NewRemoteEdge
from backend.collectors.edge import remote_edge_manager as new_remote_edge_manager
from backend.collectors.remote_edge import (
    ACTION_TIMEOUTS,
    DEBUG_PORT,
    EdgeActionTimeoutError,
    RemoteEdge,
    RemoteEdgeManager,
    RemotePageInfo,
    remote_edge_manager,
)


def main() -> None:
    assert RemoteEdge is NewRemoteEdge, "旧路径 RemoteEdge 未正确兼容到新包"
    assert remote_edge_manager is new_remote_edge_manager, "旧路径 remote_edge_manager 未正确兼容到新包"
    assert isinstance(remote_edge_manager, RemoteEdgeManager), "remote_edge_manager 类型不正确"
    assert ACTION_TIMEOUTS["start_edge"] == 35.0, "ACTION_TIMEOUTS 兼容值异常"

    timeout = EdgeActionTimeoutError("health", "test_stage", 6.0)
    assert timeout.reason_code == "edge_action_timeout"
    assert timeout.action == "health"

    page = RemotePageInfo(page_id="p1", title="demo", url="https://example.com", is_closed=False)
    assert page.page_id == "p1"
    assert not page.is_closed

    with tempfile.TemporaryDirectory() as temp_dir:
        client = RemoteEdge(
            session_id="smoke_edge_client",
            name="Smoke Edge",
            debug_port=DEBUG_PORT + 55,
            user_data_dir=str(Path(temp_dir) / "edge_profile"),
            session_mode="isolated",
        )
        quick = client.health_quick()
        assert quick["session_id"] == "smoke_edge_client"
        assert quick["debug_port"] == DEBUG_PORT + 55
        assert quick["session_mode"] == "isolated"
        assert quick["profile_initialized"] is False

        client.mark_stale("smoke_test")
        assert client.is_stale is True
        assert client.health_quick()["stale_reason"] == "smoke_test"

    print("smoke_edge ok")


if __name__ == "__main__":
    main()
