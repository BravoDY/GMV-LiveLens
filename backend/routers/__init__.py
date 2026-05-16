from backend.routers.dashboard import router as dashboard_router
from backend.routers.dashboard_test import router as dashboard_test_router
from backend.routers.edge_sessions import router as edge_sessions_router
from backend.routers.ocr import router as ocr_router
from backend.routers.platforms import router as platforms_router
from backend.routers.shops import router as shops_router
from backend.routers.system import router as system_router
from backend.routers.tasks import router as tasks_router

ALL_ROUTERS = (
    dashboard_router,
    dashboard_test_router,
    system_router,
    platforms_router,
    shops_router,
    tasks_router,
    ocr_router,
    edge_sessions_router,
)
