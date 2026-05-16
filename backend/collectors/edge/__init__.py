from __future__ import annotations

from ._actions import RemoteEdgeActionsMixin
from ._network import NETWORK_WATCH_BOOTSTRAP_SCRIPT, RemoteEdgeNetworkMixin
from ._page import SAME_TAB_SCRIPT, RemoteEdgePageMixin
from ._readonly import SCREEN_READONLY_WAITING_REASON_CODES, RemoteEdgeReadonlyMixin
from ._session import (
    ACTION_TIMEOUTS,
    DEBUG_HOST,
    DEBUG_PORT,
    DEBUG_URL,
    EdgeActionTimeoutError,
    PageCleanupResult,
    RemoteEdgeCloseState,
    RemoteEdgeHealth,
    RemoteEdgeManager,
    RemoteEdgeNavigationState,
    RemoteEdgeSessionMixin,
    RemoteEdgeWindowState,
    RemotePageInfo,
    _validate_user_data_dir,
)
from ._window import RemoteEdgeWindowMixin


class RemoteEdge(
    RemoteEdgeActionsMixin,
    RemoteEdgeWindowMixin,
    RemoteEdgeReadonlyMixin,
    RemoteEdgeNetworkMixin,
    RemoteEdgePageMixin,
    RemoteEdgeSessionMixin,
):
    pass


remote_edge_manager = RemoteEdgeManager()

__all__ = [
    "ACTION_TIMEOUTS",
    "DEBUG_HOST",
    "DEBUG_PORT",
    "DEBUG_URL",
    "EdgeActionTimeoutError",
    "NETWORK_WATCH_BOOTSTRAP_SCRIPT",
    "PageCleanupResult",
    "RemoteEdge",
    "RemoteEdgeCloseState",
    "RemoteEdgeHealth",
    "RemoteEdgeManager",
    "RemoteEdgeNavigationState",
    "RemoteEdgeWindowState",
    "RemotePageInfo",
    "SCREEN_READONLY_WAITING_REASON_CODES",
    "SAME_TAB_SCRIPT",
    "_validate_user_data_dir",
    "remote_edge_manager",
]
