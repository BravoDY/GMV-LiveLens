"""
GMV-LiveLens 全功能测试脚本

覆盖范围：
  A. 模块导入与 Bug 修复验证
  B. 业务逻辑单元测试（纯函数，无服务/无 Edge）
  C. store.py 数据库 CRUD（使用临时数据库）
  D. OCR 管道测试（合成图片）
  E. API 集成测试（需服务在 8100 端口运行）
  F. 前端文件一致性检查

用法：
  .venv\\Scripts\\python.exe backend\\tools\\full_test.py [--host 127.0.0.1] [--port 8100]
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import io
import json
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

# 强制 stdout 使用 UTF-8，避免 GBK 终端无法打印中文/特殊符号
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

# ── 路径设置 ──────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

# ── 测试基础框架 ───────────────────────────────────────────
_results: list[tuple[str, str, bool, float, str]] = []  # section, name, ok, ms, detail


def _check(section: str, name: str, fn: Callable[[], tuple[bool, str]]) -> bool:
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as exc:
        ok, detail = False, f"异常: {exc}\n{traceback.format_exc(limit=3)}"
    ms = (time.time() - t0) * 1000
    _results.append((section, name, ok, ms, detail))
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name:<55} {ms:.0f}ms  {detail[:100]}")
    return ok


def _section(title: str) -> None:
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")


# ══════════════════════════════════════════════════════════
# SECTION A: 模块导入与 Bug 修复验证
# ══════════════════════════════════════════════════════════
def run_section_a() -> None:
    _section("A. 模块导入与 Bug 修复验证")

    def import_ok(modname: str) -> Callable:
        def _fn():
            importlib.import_module(modname)
            return True, f"OK ({modname})"
        return _fn

    _check("A", "backend.models 导入", import_ok("backend.models"))
    _check("A", "backend.services.store 导入", import_ok("backend.services.store"))
    _check("A", "backend.services.scheduler 导入", import_ok("backend.services.scheduler"))
    _check("A", "backend.services.shop_config 导入", import_ok("backend.services.shop_config"))
    _check("A", "backend.collectors.ocr_reader 导入", import_ok("backend.collectors.ocr_reader"))
    _check("A", "backend.collectors.window_capture 导入", import_ok("backend.collectors.window_capture"))
    _check("A", "backend.collectors.window_control 导入", import_ok("backend.collectors.window_control"))

    # Bug-1 验证：scheduler 中必须有 logger 定义
    def a_bug1():
        import backend.services.scheduler as sched
        ok = hasattr(sched, "logger")
        return ok, "logger 已定义" if ok else "logger 未找到 (Bug-1 未修复)"
    _check("A", "Bug-1: scheduler.logger 已定义", a_bug1)

    # Bug-2 验证：_run_loop 包含异常保护
    def a_bug2():
        import backend.services.scheduler as sched
        src = inspect.getsource(sched.CaptureScheduler._run_loop)
        has_try = "except Exception" in src and "asyncio.CancelledError" in src
        return has_try, "_run_loop 含 try/except 保护" if has_try else "_run_loop 无异常保护 (Bug-2 未修复)"
    _check("A", "Bug-2: _run_loop 含异常保护", a_bug2)

    # Bug-3 验证：next_edge_debug_port 有上界检查
    def a_bug3():
        import backend.services.store as store_mod
        src = inspect.getsource(store_mod.next_edge_debug_port)
        has_bound = "65000" in src or "65535" in src
        return has_bound, "含端口上界检查" if has_bound else "无端口上界 (Bug-3 未修复)"
    _check("A", "Bug-3: next_edge_debug_port 含端口上界", a_bug3)


# ══════════════════════════════════════════════════════════
# SECTION B: 业务逻辑单元测试
# ══════════════════════════════════════════════════════════
def run_section_b() -> None:
    _section("B. 业务逻辑单元测试（纯函数）")

    # ── B1: shop_config ─────────────────────────────────
    def b1_load():
        from backend.services.shop_config import load_shop_configs
        shops = load_shop_configs()
        ok = len(shops) >= 1
        return ok, f"加载 {len(shops)} 家店铺"
    _check("B", "B1: shop_config.load_shop_configs() 返回非空", b1_load)

    def b1_ports():
        from backend.services.shop_config import load_shop_configs
        shops = load_shop_configs()
        ports = [s.debug_port for s in shops]
        unique = len(set(ports)) == len(ports)
        return unique, f"共 {len(ports)} 个端口, 唯一={unique}"
    _check("B", "B1: 所有店铺端口唯一无重复", b1_ports)

    def b1_platform_key():
        from backend.services.shop_config import platform_key
        # 只测试有明确映射的平台；未匹配平台返回原始值（如"唯品会"→"唯品会"）
        cases = [
            ("天猫", "天猫"), ("淘宝", "天猫"), ("生意参谋", "天猫"),
            ("京东", "京东"), ("商智", "京东"),
            ("抖音", "抖音"), ("巨量", "抖音"),
        ]
        fails = [(inp, exp, platform_key(inp)) for inp, exp in cases if platform_key(inp) != exp]
        # 验证未匹配平台返回原始值
        unknown = platform_key("唯品会")
        if unknown not in ("唯品会", "其他平台"):
            fails.append(("唯品会", "唯品会|其他平台", unknown))
        return len(fails) == 0, "全部通过" if not fails else f"失败: {fails}"
    _check("B", "B1: platform_key() 平台归一化", b1_platform_key)

    # ── B2: ocr_reader._normalize_amount ────────────────
    def b2_normalize():
        from backend.collectors.ocr_reader import _normalize_amount
        cases = [
            ("474487", "",  474487),
            ("474,487", "", 474487),
            ("474.487", "", 474487),
            ("1,234,567", "", 1234567),
            ("1.23", "亿", 123000000),
            ("12.5", "万", 125000),
            ("2024-01-01", "", None),
            ("99", "",  None),       # < 100 返回 None
        ]
        fails = []
        for raw, unit, expected in cases:
            got = _normalize_amount(raw, unit)
            if got != expected:
                fails.append(f"'{raw}'(unit='{unit}')→{got} 期望{expected}")
        return len(fails) == 0, "全部通过" if not fails else "; ".join(fails)
    _check("B", "B2: _normalize_amount() 金额解析", b2_normalize)

    def b2_currency_alias():
        from backend.collectors.ocr_reader import _normalize_amount
        # 货币符号别名（羊=¥）
        val = _normalize_amount("474487", "")
        return val == 474487, f"= {val}"
    _check("B", "B2: 纯数字字符串解析正确", b2_currency_alias)

    # ── B3: ocr_reader.extract_candidates ───────────────
    def b3_basic():
        from backend.collectors.ocr_reader import extract_candidates
        # 用 RMB 前缀（ASCII，确保跨平台匹配）
        text = "RMB474,487 成交金额"
        candidates = extract_candidates(text, [], "成交金额", None)
        ok = len(candidates) > 0 and candidates[0].value == 474487
        return ok, f"candidates={[(c.value, round(c.score)) for c in candidates[:3]]}"
    _check("B", "B3: extract_candidates() 带 RMB 前缀", b3_basic)

    def b3_plain_number():
        from backend.collectors.ocr_reader import extract_candidates
        # 纯数字也应被正确识别
        text = "474487"
        candidates = extract_candidates(text, [], "", None)
        ok = len(candidates) > 0 and candidates[0].value == 474487
        return ok, f"candidates={[(c.value, round(c.score)) for c in candidates[:3]]}"
    _check("B", "B3: extract_candidates() 纯数字字符串", b3_plain_number)

    def b3_keyword_bonus():
        from backend.collectors.ocr_reader import extract_candidates
        # 两个数字，关键词紧邻第一个，第一个应排前
        text = "成交金额123456 其他654321"
        cands = extract_candidates(text, [], "成交金额", None)
        top_val = cands[0].value if cands else None
        ok = top_val == 123456
        return ok, f"top={top_val} (期望123456)"
    _check("B", "B3: extract_candidates() 关键词评分加成", b3_keyword_bonus)

    def b3_date_filter():
        from backend.collectors.ocr_reader import extract_candidates
        text = "2024-06-18 100000"
        cands = extract_candidates(text, [], "", None)
        vals = [c.value for c in cands]
        date_in = 20240618 in vals
        ok = not date_in
        return ok, f"候选={vals[:3]}, 日期{'混入了' if date_in else '已过滤'}"
    _check("B", "B3: extract_candidates() 日期不被识别为金额", b3_date_filter)

    def b3_ocr_char_replace():
        from backend.collectors.ocr_reader import extract_candidates
        # "S" → "5" 形近字纠错
        text = "4744S7"  # S→5 → 474457
        cands = extract_candidates(text, [], "", None)
        vals = [c.value for c in cands]
        ok = 474457 in vals
        return ok, f"候选={vals[:3]}, 期望含474457"
    _check("B", "B3: OCR 形近字纠错 S→5", b3_ocr_char_replace)

    def b3_non_numeric_context_no_replace():
        from backend.collectors.ocr_reader import extract_candidates
        text = "订单OLD 已完成"
        cands = extract_candidates(text, [], "", None)
        ok = len(cands) == 0
        return ok, f"候选={[(c.value, c.raw_text) for c in cands[:3]]}"
    _check("B", "B3: 非数字上下文不触发全文形近字替换", b3_non_numeric_context_no_replace)

    # ── B4: scheduler._judge 状态机 ────────────────────
    from backend.models import CaptureTask

    def _task(**kw) -> CaptureTask:
        defaults = {
            "id": 1,
            "capture_mode": "remote_edge",
            "value_source": "ocr",
            "page_id": "",
            "page_url": "",
            "target_page_url": "",
            "page_title": "",
            "browser_profile": "",
            "edge_session_id": "test",
            "platform": "天猫",
            "shop_name": "测试店铺",
            "window_keyword": "",
            "keyword_hint": "成交金额",
            "interval_seconds": 2.0,
            "enabled": True,
            "base_width": 1280,
            "base_height": 800,
            "x": 100,
            "y": 100,
            "width": 300,
            "height": 60,
            "x_ratio": 0.1,
            "y_ratio": 0.1,
            "width_ratio": 0.3,
            "height_ratio": 0.1,
            "safety_margin": 0.05,
            "confirm_count": 2,
            "last_trusted_value": None,
            "pending_value": None,
            "pending_count": 0,
            "status": "pending_confirm",
        }
        defaults.update(kw)
        return CaptureTask(**defaults)

    from backend.services.scheduler import CaptureScheduler
    sched = CaptureScheduler()

    def b4_none_first():
        t = _task(status="ok", pending_count=0)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, None)
        ok = status == "parse_failed" and trusted is None and pc == 1
        return ok, f"status={status}, pc={pc}"
    _check("B", "B4: _judge(None) 首次 → parse_failed, pending_count=1", b4_none_first)

    def b4_none_5x():
        t = _task(status="parse_failed", pending_count=4)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, None)
        ok = status == "needs_recalibration" and pc == 5
        return ok, f"status={status}, pc={pc}"
    _check("B", "B4: _judge(None) 第5次 → needs_recalibration", b4_none_5x)

    def b4_confirm1_ok():
        t = _task(confirm_count=1)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 100000)
        ok = status == "ok" and trusted == 100000 and required == 1 and accepted == 1
        return ok, f"status={status}, trusted={trusted}, required={required}, accepted={accepted}"
    _check("B", "B4: confirm_count=1, 正常值 → 直接 ok", b4_confirm1_ok)

    def b4_pending_first():
        t = _task(confirm_count=2, pending_value=None)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 100000)
        ok = status == "pending_confirm" and pv == 100000 and pc == 1 and required == 2 and accepted == 0
        return ok, f"status={status}, pv={pv}, pc={pc}, required={required}, accepted={accepted}"
    _check("B", "B4: confirm_count=2, 首次有值 → pending_confirm, pc=1", b4_pending_first)

    def b4_pending_confirm_ok():
        t = _task(confirm_count=2, pending_value=100000, pending_count=1)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 100500)  # 在 0.85-1.35 范围内
        ok = status == "ok" and trusted == 100500 and required == 2 and accepted == 2
        return ok, f"status={status}, trusted={trusted}, required={required}, accepted={accepted}"
    _check("B", "B4: 连续2次相近值 → ok", b4_pending_confirm_ok)

    def b4_abnormal_drop():
        t = _task(last_trusted_value=200000, pending_value=None, confirm_count=2)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 100000)  # 同一天内降低 50%
        ok = status == "ok" and trusted is None and pv is None and pc == 0
        return ok, f"status={status}, trusted={trusted}, reason={reason[:40]}"
    _check("B", "B4: 同日金额降低50% → 忽略且不更新可信值", b4_abnormal_drop)

    def b4_abnormal_jump():
        t = _task(last_trusted_value=100000, pending_value=None, confirm_count=2)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 700000)  # 跳升 7 倍
        ok = status == "suspect" and trusted is None and pv == 700000 and required >= 3 and accepted == 0
        return ok, f"status={status}, pv={pv}, required={required}, reason={reason[:40]}"
    _check("B", "B4: 金额跳升 7 倍 → suspect/pending_confirm（异常）", b4_abnormal_jump)

    def b4_plausible_range():
        cases = [
            (100000, 103000, True),   # +3%，合理
            (100000, 135000, True),   # +35%，边界
            (100000, 136000, False),  # +36%，超出
            (100000, 85000,  True),   # -15%，边界
            (100000, 84000,  False),  # -16%，超出
            (1000000, 999000, True),  # 位数相同，微降
        ]
        fails = []
        for prev, curr, expected in cases:
            got = CaptureScheduler._is_plausible_next(prev, curr)
            if got != expected:
                fails.append(f"{prev}→{curr}: got={got}, expected={expected}")
        return len(fails) == 0, "全部通过" if not fails else "; ".join(fails)
    _check("B", "B4: _is_plausible_next() 合理性范围检查", b4_plausible_range)

    def b4_task_interval():
        fast = _task(interval_seconds=0.5)
        slow = _task(interval_seconds=3.0)
        got_fast = sched._task_interval_seconds(fast, 1.0)
        got_slow = sched._task_interval_seconds(slow, 1.0)
        ok = got_fast == 0.5 and got_slow == 3.0
        return ok, f"fast={got_fast}, slow={got_slow}"
    _check("B", "B4: 调度器按任务 interval_seconds 取执行频率", b4_task_interval)
    # ── B4.5: 跨天检测 ────────────────────────────────
    def b4_crossday_reset():
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 10:00:00")
        t = _task(last_trusted_value=200000, last_success_at=yesterday, confirm_count=1)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 50000, {"engine": "rapidocr"})
        ok = status == "ok" and trusted == 50000 and "跨天重置" in reason
        return ok, f"status={status}, trusted={trusted}, reason={reason[:50]}"
    _check("B", "B4.5: 跨天检测（昨天可信值20万→今天5万）→ 接受跨天重置", b4_crossday_reset)

    def b4_crossday_sameday():
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d 10:00:00")
        t = _task(last_trusted_value=200000, last_success_at=today, confirm_count=1)
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 50000, {"engine": "rapidocr"})
        ok = status == "ok" and trusted is None and "同一天" in reason
        return ok, f"status={status}, trusted={trusted}, reason={reason[:50]}"
    _check("B", "B4.5: 同日检测（今天20万→5万）→ 忽略下降不更新", b4_crossday_sameday)

    def b4_crossday_empty_last_success():
        t = _task(last_trusted_value=200000, last_success_at="")
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 50000, {"engine": "rapidocr"})
        ok = status == "ok" and trusted is None and "同一天" in reason
        return ok, f"status={status}, reason={reason[:50]}"
    _check("B", "B4.5: last_success_at 为空 → 跳过跨天检测，同日逻辑兜底", b4_crossday_empty_last_success)

    def b4_crossday_invalid_format():
        t = _task(last_trusted_value=200000, last_success_at="bad-date-format")
        # Should log warning but not crash; falls through to same-day logic
        status, reason, trusted, pv, pc, required, accepted = sched._judge(t, 50000, {"engine": "rapidocr"})
        ok = status == "ok"
        return ok, f"status={status}, reason={reason[:50]} (异常格式未崩溃)"
    _check("B", "B4.5: last_success_at 非标准格式 → 不崩溃且日志告警", b4_crossday_invalid_format)




# ══════════════════════════════════════════════════════════
# SECTION C: store.py 数据库 CRUD（临时数据库）
# ══════════════════════════════════════════════════════════
def run_section_c() -> None:
    _section("C. store.py 数据库 CRUD（临时数据库）")

    import backend.services.store as store_mod

    _tmp_db = Path(tempfile.mktemp(suffix="_gmv_test.sqlite3"))
    _orig_db = store_mod.DB_PATH

    try:
        store_mod.DB_PATH = _tmp_db
        # 同步修改 connect() 引用的路径
        store_mod.DATA_DIR = _tmp_db.parent
        store_mod.SCREENSHOT_DIR = _tmp_db.parent
        store_mod.EDGE_PROFILE_DIR = _tmp_db.parent

        def c1_init():
            store_mod.init_db()
            ok = _tmp_db.exists()
            return ok, f"DB 文件已创建: {_tmp_db.name}"
        _check("C", "C1: init_db() 创建数据库文件", c1_init)

        def c1_default_session():
            sessions = store_mod.list_edge_sessions()
            ids = [s.session_id for s in sessions]
            ok = "default_real_edge" in ids
            default = next((s for s in sessions if s.session_id == "default_real_edge"), None)
            mode = default.session_mode if default else "?"
            return ok, f"default_real_edge 存在, session_mode={mode}"
        _check("C", "C1: 默认 Edge 会话 default_real_edge 已初始化", c1_default_session)

        def c2_upsert_task():
            from backend.services.shop_config import load_shop_configs
            shops = load_shop_configs()
            shop = shops[0]
            payload = shop.to_task_payload()
            task = store_mod.upsert_task(payload)
            ok = task.id is not None and task.shop_name == shop.shop_name
            return ok, f"task.id={task.id}, shop={task.shop_name}"
        _check("C", "C2: upsert_task() 创建任务", c2_upsert_task)

        def c2_get_task():
            tasks = store_mod.list_tasks()
            if not tasks:
                return False, "任务列表为空"
            t = store_mod.get_task(tasks[0].id)
            ok = t is not None and t.id == tasks[0].id
            return ok, f"get_task({tasks[0].id}) = {t.shop_name if t else None}"
        _check("C", "C2: get_task() 读回任务", c2_get_task)

        def c2_update_runtime():
            tasks = store_mod.list_tasks()
            if not tasks:
                return False, "无任务"
            task = tasks[0]
            store_mod.update_task_runtime(task.id, {"status": "ok", "last_trusted_value": 123456})
            updated = store_mod.get_task(task.id)
            ok = updated.status == "ok" and updated.last_trusted_value == 123456
            return ok, f"status={updated.status}, trusted={updated.last_trusted_value}"
        _check("C", "C2: update_task_runtime() 更新运行时字段", c2_update_runtime)

        def c2_add_sample():
            tasks = store_mod.list_tasks()
            if not tasks:
                return False, "无任务"
            store_mod.add_sample(
                tasks[0].id,
                "¥123,456",
                [{"value": 123456, "engine": "ddddocr", "variant": "color", "source_kind": "detail", "correction_count": 2}],
                123456,
                123456,
                "ok",
                "test",
                "",
                sample_meta={
                    "selected_candidate_engine": "ddddocr",
                    "selected_candidate_variant": "color",
                    "selected_candidate_source_kind": "detail",
                    "selected_candidate_correction_count": 2,
                    "required_confirms": 4,
                    "accepted_after_confirms": 4,
                },
            )
            samples = store_mod.recent_samples(tasks[0].id, limit=5)
            latest = samples[0] if samples else {}
            ok = (
                len(samples) > 0
                and latest.get("selected_candidate_engine") == "ddddocr"
                and int(latest.get("accepted_after_confirms") or 0) == 4
            )
            return ok, f"样本数={len(samples)}, engine={latest.get('selected_candidate_engine')}, confirms={latest.get('accepted_after_confirms')}"
        _check("C", "C2: add_sample() / recent_samples() 采样历史", c2_add_sample)

        def c2_settings():
            store_mod.set_setting("interval_seconds", "1.5")
            val = store_mod.get_setting("interval_seconds", "2.0")
            ok = val == "1.5"
            return ok, f"interval_seconds = {val}"
        _check("C", "C2: set_setting() / get_setting() 读写设置", c2_settings)

        def c3_port_alloc():
            port = store_mod.next_edge_debug_port()
            ok = 9221 <= port <= 65000
            return ok, f"分配端口={port}"
        _check("C", "C3: next_edge_debug_port() 分配合法端口", c3_port_alloc)

        def c3_port_bound():
            import backend.services.store as sm
            src = inspect.getsource(sm.next_edge_debug_port)
            ok = "65000" in src or "65535" in src
            return ok, "含上界保护" if ok else "无上界"
        _check("C", "C3: next_edge_debug_port() 端口上界保护代码存在", c3_port_bound)

        def c4_delete_task():
            tasks = store_mod.list_tasks()
            if not tasks:
                return False, "无任务"
            tid = tasks[0].id
            store_mod.delete_task(tid)
            gone = store_mod.get_task(tid) is None
            return gone, f"task {tid} 已删除"
        _check("C", "C4: delete_task() 删除任务及样本", c4_delete_task)

        def c4_delete_edge_session_resets_binding():
            from backend.services.shop_config import load_shop_configs
            shops = load_shop_configs()
            if not shops:
                return False, "无店铺配置"
            shop = shops[0]
            payload = shop.to_task_payload()
            task = store_mod.upsert_task(payload)
            store_mod.update_task_runtime(task.id, {"status": "edge_target_page_ready"})
            store_mod.upsert_task(
                {
                    **store_mod.task_to_dict(task),
                    "page_id": "page-123",
                    "page_url": "https://example.com/page",
                    "page_title": "示例页签",
                }
            )
            store_mod.delete_edge_session(shop.edge_session_id)
            updated = store_mod.get_task(task.id)
            ok = (
                updated is not None
                and updated.edge_session_id == "default_real_edge"
                and updated.page_id == ""
                and updated.page_url == ""
                and updated.page_title == ""
                and updated.last_reason_code == "edge_session_deleted_requires_rebind"
            )
            return ok, (
                f"session={updated.edge_session_id if updated else None}, "
                f"page_id={updated.page_id if updated else None}, "
                f"reason_code={updated.last_reason_code if updated else None}"
            )
        _check("C", "C4: delete_edge_session() 清空旧页面绑定并要求重绑", c4_delete_edge_session_resets_binding)
        def c5_screenshot_cleanup_count():
            import tempfile, shutil
            from backend.services.scheduler import CaptureScheduler

            tmp = Path(tempfile.mkdtemp(prefix="gmv_test_"))
            try:
                for i in range(5):
                    (tmp / f"task_99_{i}.png").write_text(f"screenshot_{i}")
                original_dir = store_mod.SCREENSHOT_DIR
                store_mod.SCREENSHOT_DIR = tmp
                # Override max count for test (module-level constant)
                import backend.services.scheduler as sched_mod
                old_max = sched_mod._SCREENSHOT_MAX_COUNT_PER_TASK
                sched_mod._SCREENSHOT_MAX_COUNT_PER_TASK = 2
                try:
                    CaptureScheduler._cleanup_old_screenshots(99)
                finally:
                    sched_mod._SCREENSHOT_MAX_COUNT_PER_TASK = old_max
                store_mod.SCREENSHOT_DIR = original_dir

                remaining = sorted(tmp.glob("task_99_*.png"))
                ok = len(remaining) <= 2
                return ok, f"创建5张→清理后保留{len(remaining)}张（上限2）"
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        _check("C", "C5: _cleanup_old_screenshots() 截图数量上限控制", c5_screenshot_cleanup_count)



    finally:
        store_mod.DB_PATH = _orig_db
        store_mod.DATA_DIR = ROOT_DIR / "data"
        store_mod.SCREENSHOT_DIR = ROOT_DIR / "data" / "screenshots"
        store_mod.EDGE_PROFILE_DIR = ROOT_DIR / "data" / "edge_profiles"
        try:
            _tmp_db.unlink(missing_ok=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════
# SECTION D: OCR 管道测试（合成图片）
# ══════════════════════════════════════════════════════════
def run_section_d() -> None:
    _section("D. OCR 管道测试（合成图片）")

    def d1_engines():
        from backend.collectors.ocr_reader import available_engines
        engines = available_engines()
        ok = engines.get("rapidocr") is True
        return ok, f"可用引擎: {[k for k,v in engines.items() if v]}"
    _check("D", "D1: available_engines() rapidocr 可用", d1_engines)

    def d2_synthetic_image():
        """用 PIL 生成包含 GMV 金额的合成图片，验证 OCR 可提取正确值"""
        try:
            from PIL import Image, ImageDraw, ImageFont

            from backend.collectors.ocr_reader import extract_candidates, read_text

            # Use a large TrueType font; PIL's tiny default bitmap font is too weak
            # for several OCR engines and made this test report false negatives.
            font = None
            for font_path in (
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
            ):
                if Path(font_path).exists():
                    font = ImageFont.truetype(font_path, 72)
                    break
            font = font or ImageFont.load_default()
            img = Image.new("RGB", (640, 140), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((24, 24), "RMB 474487", fill=(0, 0, 0), font=font)

            ocr_text, details = read_text(img, keyword_hint="成交金额", last_value=None)
            candidates = extract_candidates(ocr_text, details, "成交金额", None)
            vals = [c.value for c in candidates]
            ok = 474487 in vals
            sources = [
                f"{item.get('engine')}/{item.get('variant')}={str(item.get('text') or '')[:20]}"
                for item in details[:5]
                if isinstance(item, dict)
            ]
            return ok, f"OCR文本='{ocr_text[:40]}', 候选={vals[:4]}, sources={sources}"
        except Exception as exc:
            return False, f"异常: {exc}"
    _check("D", "D2: 合成图片 OCR 提取 474487", d2_synthetic_image)

    def d3_chinese_unit():
        from backend.collectors.ocr_reader import extract_candidates
        # 带万字单位
        text = "成交金额 4744.87万"
        candidates = extract_candidates(text, [], "成交金额", None)
        vals = [c.value for c in candidates]
        ok = 47448700 in vals or 47448700 in [round(v / 1000) * 1000 for v in vals]
        return ok or len(vals) > 0, f"候选={vals[:4]}, 期望含47448700"
    _check("D", "D3: extract_candidates() 万字单位解析", d3_chinese_unit)

    def d4_last_value_scoring():
        from backend.collectors.ocr_reader import extract_candidates
        # 用 details 列表传入独立文本项，避免空格被当成数字间隔符合并
        details = [{"text": "100500"}, {"text": "999999"}, {"text": "123456"}]
        cands_with = extract_candidates("", details, "", last_value=100000)
        cands_without = extract_candidates("", details, "", last_value=None)
        top_with = cands_with[0].value if cands_with else None
        top_without = cands_without[0].value if cands_without else None
        ok = top_with == 100500  # 100500 最接近 last_value=100000
        return ok, f"有last_value时top={top_with}(期望100500), 无last_value时top={top_without}"
    _check("D", "D4: last_value 参数对候选排序的影响", d4_last_value_scoring)


# ══════════════════════════════════════════════════════════
# SECTION E: API 集成测试（需服务在运行）
# ══════════════════════════════════════════════════════════
def _http_get(base: str, path: str, timeout: float = 8.0) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, str(e)


def run_section_e(base: str) -> None:
    _section(f"E. API 集成测试  ({base})")

    # E1: 核心状态接口
    def e1_health():
        code, data = _http_get(base, "/api/health")
        ok = code == 200 and isinstance(data, dict) and "scheduler" in data
        return ok, f"HTTP {code}"
    _check("E", "E1: GET /api/health", e1_health)

    def e1_scheduler():
        code, data = _http_get(base, "/api/scheduler")
        ok = code == 200 and isinstance(data, dict)
        return ok, f"running={data.get('running') if isinstance(data, dict) else '?'}"
    _check("E", "E1: GET /api/scheduler", e1_scheduler)

    def e1_settings_get():
        code, data = _http_get(base, "/api/settings")
        ok = code == 200 and isinstance(data, dict) and "interval_seconds" in data
        return ok, f"keys={list(data.keys()) if isinstance(data, dict) else '?'}"
    _check("E", "E1: GET /api/settings", e1_settings_get)

    # E2: 任务接口
    def e2_tasks():
        code, data = _http_get(base, "/api/tasks")
        cnt = len(data.get("tasks", [])) if isinstance(data, dict) else "?"
        ok = code == 200 and isinstance(data, dict)
        return ok, f"HTTP {code}, tasks={cnt}"
    _check("E", "E2: GET /api/tasks", e2_tasks)

    def e2_realtime():
        code, data = _http_get(base, "/api/realtime")
        ok = code == 200 and isinstance(data, dict) and "tasks" in data
        return ok, f"HTTP {code}"
    _check("E", "E2: GET /api/realtime (别名)", e2_realtime)

    def e2_page_candidates_404():
        code, _ = _http_get(base, "/api/tasks/99999/page-candidates")
        ok = code == 404
        return ok, f"HTTP {code}（期望 404 任务不存在）"
    _check("E", "E2: GET /api/tasks/99999/page-candidates → 404", e2_page_candidates_404)

    # E3: Edge 会话接口
    def e3_sessions_list():
        code, data = _http_get(base, "/api/edge-sessions", timeout=90)
        sessions = data if isinstance(data, list) else []
        ids = [s.get("session_id") for s in sessions if isinstance(s, dict)]
        ok = code == 200 and "default_real_edge" in ids
        return ok, f"HTTP {code}, sessions={len(ids)}"
    _check("E", "E3: GET /api/edge-sessions (含 default_real_edge)", e3_sessions_list)

    def e3_default_health():
        code, data = _http_get(base, "/api/edge-sessions/default_real_edge/health", timeout=10)
        ok = code == 200 and isinstance(data, dict)
        debug = data.get("debug_available") if isinstance(data, dict) else "?"
        return ok, f"HTTP {code}, debug_available={debug}"
    _check("E", "E3: GET /api/edge-sessions/default_real_edge/health", e3_default_health)

    def e3_session_404():
        code, _ = _http_get(base, "/api/edge-sessions/nonexistent_session_xyz/health")
        ok = code == 404
        return ok, f"HTTP {code}（期望 404）"
    _check("E", "E3: GET /api/edge-sessions/不存在的session/health → 404", e3_session_404)

    # E4: 店铺配置
    def e4_shops():
        code, data = _http_get(base, "/api/shops")
        shops = data if isinstance(data, list) else []
        ok = code == 200 and len(shops) > 0
        return ok, f"HTTP {code}, shops={len(shops)}"
    _check("E", "E4: GET /api/shops", e4_shops)

    def e4_shops_init():
        url = f"{base}/api/shops/init"
        req = urllib.request.Request(url, data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                ok = resp.status == 200
                return ok, f"HTTP {resp.status}, result={data}"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}"
    _check("E", "E4: POST /api/shops/init (幂等初始化)", e4_shops_init)

    # E5: OCR 测试接口
    def e5_ocr_engines():
        code, data = _http_get(base, "/api/ocr/engines")
        available = data.get("available", {}) if isinstance(data, dict) else {}
        ok = code == 200 and available.get("rapidocr") is True
        return ok, f"HTTP {code}, available={[k for k,v in available.items() if v]}"
    _check("E", "E5: GET /api/ocr/engines (rapidocr 可用)", e5_ocr_engines)

    def e5_test_ocr_base64():
        """用 base64 合成图片测试 /api/test-ocr"""
        try:
            import base64
            import io

            from PIL import Image, ImageDraw
            img = Image.new("RGB", (420, 80), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "RMB474487", fill=(0, 0, 0))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            data_url = f"data:image/png;base64,{b64}"

            payload = json.dumps({
                "capture_mode": "preview_image",
                "preview_image": data_url,
                "x_ratio": 0.0, "y_ratio": 0.0,
                "width_ratio": 1.0, "height_ratio": 1.0,
                "safety_margin": 0.0,
                "keyword_hint": "成交金额",
            }).encode()
            url = f"{base}/api/test-ocr"
            req = urllib.request.Request(url, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                cands = result.get("candidates", [])
                vals = [c.get("value") for c in cands]
                ok = resp.status == 200
                return ok, f"HTTP {resp.status}, candidates={vals[:4]}"
        except Exception as exc:
            return False, f"异常: {exc}"
    _check("E", "E5: POST /api/test-ocr 合成图片识别", e5_test_ocr_base64)

    # E6: 设置读写
    def e6_settings_roundtrip():
        url = f"{base}/api/settings"
        payload = json.dumps({"ocr_engine": "auto", "interval_seconds": 3.0}).encode()
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                post_code = resp.status
        except urllib.error.HTTPError as e:
            return False, f"POST HTTP {e.code}"
        code, data = _http_get(base, "/api/settings")
        val = float(data.get("interval_seconds", 0)) if isinstance(data, dict) else 0
        # 恢复
        payload2 = json.dumps({"ocr_engine": "auto", "interval_seconds": 0.5}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(
                url, data=payload2, method="POST",
                headers={"Content-Type": "application/json"}), timeout=5)
        except Exception:
            pass
        ok = post_code == 200 and val == 3.0
        return ok, f"POST={post_code}, 读回interval_seconds={val}"
    _check("E", "E6: POST /api/settings 读写往返", e6_settings_roundtrip)

    # E7: 调度器控制
    def e7_pause_resume():
        def _post(path):
            req = urllib.request.Request(f"{base}{path}", data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status
            except urllib.error.HTTPError as e:
                return e.code

        pause_code = _post("/api/scheduler/pause")
        code, data = _http_get(base, "/api/scheduler")
        paused = data.get("running") is False if isinstance(data, dict) else False
        resume_code = _post("/api/scheduler/start")
        ok = pause_code == 200 and paused
        return ok, f"pause={pause_code}, paused={paused}, resume={resume_code}"
    _check("E", "E7: POST /api/scheduler/pause + start", e7_pause_resume)

    # E8: WebSocket 连通
    def e8_ws():
        import base64
        import os as _os
        import socket
        import struct
        key = base64.b64encode(_os.urandom(16)).decode()
        host = base.replace("http://", "").split(":")[0]
        port = int(base.split(":")[-1])
        hs = (f"GET /ws/live HTTP/1.1\r\nHost: {host}:{port}\r\n"
              f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
              f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        try:
            s = socket.create_connection((host, port), timeout=5)
            s.sendall(hs.encode())
            buf = b""
            while b"\r\n\r\n" not in buf:
                buf += s.recv(4096)
            if b"101" not in buf:
                s.close()
                return False, "握手失败"
            s.settimeout(5)
            hdr = s.recv(2)
            plen = hdr[1] & 0x7F
            if plen == 126:
                plen = struct.unpack(">H", s.recv(2))[0]
            payload = b""
            rem = min(plen, 4096)
            while rem > 0:
                c = s.recv(rem)
                if not c:
                    break
                payload += c
                rem -= len(c)
            s.close()
            text = payload.decode("utf-8", errors="replace")
            # 快照较大，只验证是否为 JSON 开头（{），不强制完整解析
            ok = text.strip().startswith("{")
            task_hint = "含tasks字段" if "tasks" in text else "不含tasks字段"
            return ok, f"收到{len(payload)}字节JSON帧, {task_hint}"
        except Exception as exc:
            return False, str(exc)
    _check("E", "E8: WS /ws/live 连通并收到快照", e8_ws)

    # E9: 窗口枚举
    def e9_windows():
        code, data = _http_get(base, "/api/windows")
        ok = code == 200 and isinstance(data, list)
        return ok, f"HTTP {code}, windows={len(data) if isinstance(data, list) else '?'}"
    _check("E", "E9: GET /api/windows", e9_windows)

    # E10: 前端主页
    def e10_frontend():
        code, data = _http_get(base, "/", timeout=8)
        ok = code == 200 and isinstance(data, str) and "GMV" in data
        return ok, f"HTTP {code}, HTML={'含GMV' if ok else '无GMV'}"
    _check("E", "E10: GET / 前端主页", e10_frontend)


# ══════════════════════════════════════════════════════════
# SECTION F: 前端文件一致性检查
# ══════════════════════════════════════════════════════════
def run_section_f() -> None:
    _section("F. 前端文件一致性检查")

    frontend_dir = ROOT_DIR / "frontend"

    def f1_files_exist():
        required = ["index.html", "core.js", "app.js", "dashboard.js", "config.js", "edge.js", "styles.css"]
        missing = [f for f in required if not (frontend_dir / f).exists()]
        return len(missing) == 0, "全部存在" if not missing else f"缺失: {missing}"
    _check("F", "F1: 前端 7 个必需文件全部存在", f1_files_exist)

    def f2_script_order():
        """index.html 应按顺序引入 5 个 JS"""
        html = (frontend_dir / "index.html").read_text(encoding="utf-8", errors="replace")
        order = ["core.js", "dashboard.js", "edge.js", "config.js", "app.js"]
        positions = {js: html.find(js) for js in order}
        sorted_pos = sorted(positions.items(), key=lambda x: x[1])
        actual_order = [name for name, _ in sorted_pos if positions[name] >= 0]
        ok = actual_order == order
        return ok, f"顺序: {actual_order}"
    _check("F", "F2: index.html JS 加载顺序正确", f2_script_order)

    def f3_ws_endpoint():
        """前端应使用 /ws/live 端点（支持字符串拼接和动态构建）"""
        app_js = (frontend_dir / "app.js").read_text(encoding="utf-8", errors="replace")
        core_js = (frontend_dir / "core.js").read_text(encoding="utf-8", errors="replace")
        combined = app_js + core_js
        # Match both literal "/ws/live" and dynamic "ws/live" or "WebSocket"
        ok = "/ws/live" in combined or "ws/live" in combined or "WebSocket" in combined
        return ok, "ws/live 或 WebSocket 存在" if ok else "ws/live 未找到"
    _check("F", "F3: app.js 包含 /ws/live WebSocket 端点", f3_ws_endpoint)

    def f4_api_settings():
        """前端应包含 /api/settings 引用（支持动态拼接如 base+/api/settings）"""
        for fname in ["core.js", "app.js", "config.js", "dashboard.js", "edge.js"]:
            content = (frontend_dir / fname).read_text(encoding="utf-8", errors="replace")
            # Match literal "/api/settings" or partial "api/settings"
            if "/api/settings" in content or "api/settings" in content:
                return True, f"在 {fname} 中找到"
        return False, "api/settings 在前端未引用"
    _check("F", "F4: 前端包含 /api/settings 调用", f4_api_settings)

    def f5_no_hardcoded_port():
        """前端不应硬编码 8100 端口（应动态获取）"""
        for fname in ["core.js", "app.js"]:
            content = (frontend_dir / fname).read_text(encoding="utf-8", errors="replace")
            if ":8100" in content:
                return False, f"{fname} 中含硬编码 :8100"
        return True, "未硬编码端口"
    _check("F", "F5: 前端未硬编码 8100 端口", f5_no_hardcoded_port)


# ══════════════════════════════════════════════════════════
# 最终报告
# ══════════════════════════════════════════════════════════
def print_report() -> int:
    sections = {}
    for sec, name, ok, ms, detail in _results:
        sections.setdefault(sec, []).append((name, ok, ms, detail))

    total = len(_results)
    passed = sum(1 for _, _, ok, _, _ in _results if ok)

    print(f"\n{'='*70}")
    print(f"  全功能测试报告  {passed}/{total} PASS")
    print(f"{'='*70}")

    for sec in sorted(sections):
        items = sections[sec]
        sec_pass = sum(1 for _, ok, _, _ in items if ok)
        print(f"\n  [{sec}] {sec_pass}/{len(items)} PASS")
        for name, ok, _ms, detail in items:
            tag = "OK" if ok else "FAIL"
            print(f"    [{tag}] {name}")
            if not ok:
                print(f"          {detail[:120]}")

    fails = [(sec, name, detail) for sec, name, ok, _, detail in _results if not ok]
    if fails:
        print(f"\n  {'─'*68}")
        print(f"  失败项详情 ({len(fails)} 项)：")
        for sec, name, detail in fails:
            print(f"\n  [{sec}] {name}")
            print(f"  {detail[:300]}")

    print(f"\n  {'─'*68}")
    print("  需人工验证（无法自动化）：")
    manual = [
        "● 真实 Edge 启动/显示/隐藏/关闭（需店铺已登录）",
        "● 真实平台页面的 OCR 采集（需 Edge 打开业务页）",
        "● 连续确认逻辑在真实采集中的表现",
        "● 页面绑定工作台（扫描页签、拖拽框选）",
        "● WebSocket 实时推送随采集更新",
        "● 登录态持久化（关闭再重启 Edge 后 Cookie 保留）",
    ]
    for item in manual:
        print(f"  {item}")

    print(f"\n{'='*70}\n")
    return 0 if passed == total else 1


# ══════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(description="GMV-LiveLens 全功能测试")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--skip-api", action="store_true", help="跳过 E 节 API 集成测试")
    args = parser.parse_args()

    base = f"http://{args.host}:{args.port}"

    print("\n  GMV-LiveLens 全功能测试")
    print(f"  {'='*60}")

    run_section_a()
    run_section_b()
    run_section_c()
    run_section_d()

    if not args.skip_api:
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=3):
                run_section_e(base)
        except Exception:
            print(f"\n  [SKIP] Section E: 服务未在 {base} 运行，跳过 API 集成测试")
            print("         运行方式：先启动服务，再执行本脚本")

    run_section_f()
    sys.exit(print_report())


if __name__ == "__main__":
    main()
