# ruff: noqa: E402
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 从主项目导入特征库，实现单点维护 (Single Source of Truth)
from backend.collectors.ocr_reader import OCR_CHAR_REPLACEMENTS, OCR_CURRENCY_ALIASES

DB_PATH = Path('data/gmv_livelens.sqlite3')

# 动态加载主项目特征库配置
KNOWN_INNER_FIXES = set(OCR_CHAR_REPLACEMENTS.keys())
KNOWN_PREFIX_FIXES = set(OCR_CURRENCY_ALIASES)

# 合法的数字内部字符（小数点、千分位逗号等）
VALID_INNER_CHARS = {',', '.', '，', '。'}

# 合法的数字前缀字符（货币符、冒号等）
VALID_PREFIX_CHARS = {'￥', '¥', 'R', 'M', 'B', 'C', 'N', 'Y', '$', '：', ':', '额', '比', '约', '为', '是', '计', '量'}


def _join_shop_key(row: sqlite3.Row) -> str:
    platform = (row["platform"] or "").strip()
    shop_name = (row["shop_name"] or "").strip()
    return f"{platform} / {shop_name}".strip(" /")


def _extract_unknown_inner_chars(text: str) -> list[str]:
    found: list[str] = []
    inner_matches = re.findall(r'(?<=\d)([^\d\s]+)(?=\d)', text)
    for match in inner_matches:
        if all(char in VALID_INNER_CHARS for char in match):
            continue
        for char in match:
            if char not in VALID_INNER_CHARS and char not in KNOWN_INNER_FIXES:
                found.append(char)
    return found


def _extract_unknown_prefix_chars(text: str) -> list[str]:
    found: list[str] = []
    prefix_matches = re.findall(r'(?:^|[^\d])([^\d\s\.,，。A-Za-z]+)\s*(?=\d)', text)
    for match in prefix_matches:
        last_char = match[-1]
        if last_char not in VALID_PREFIX_CHARS and last_char not in KNOWN_PREFIX_FIXES and last_char not in ['万', '亿']:
            found.append(last_char)
    return found


def _load_candidates(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _selected_candidate_signals(row: sqlite3.Row) -> list[str]:
    signals: list[str] = []
    engine = str(row["selected_candidate_engine"] or "")
    variant = str(row["selected_candidate_variant"] or "")
    source_kind = str(row["selected_candidate_source_kind"] or "")
    correction_count = int(row["selected_candidate_correction_count"] or 0)
    required_confirms = int(row["required_confirms"] or 0)
    accepted_after_confirms = int(row["accepted_after_confirms"] or 0)
    if engine == "ddddocr":
        signals.append("ddddocr")
    if source_kind == "joined_text":
        signals.append("joined_text")
    if variant in {"yellow_digits", "otsu", "adaptive_binary", "invert_gray"}:
        signals.append("binary_variant")
    if correction_count >= 2:
        signals.append("heavy_fix")
    if required_confirms >= 3:
        signals.append("guarded_accept")
    if accepted_after_confirms >= 4:
        signals.append("late_accept")
    return signals


def _pick_selected_candidate(row: sqlite3.Row) -> dict:
    selected_value = row["selected_value"]
    if selected_value is None:
        return {}
    candidates = _load_candidates(row["candidates_json"])
    for item in candidates:
        try:
            if int(item.get("value")) == int(selected_value):
                return item
        except Exception:
            continue
    return {}


def _shop_strategy_hint(signal: str) -> str:
    if signal in {"ddddocr", "binary_variant", "joined_text"}:
        return "优先做店铺级实验配置，避免直接扩大为全局规则"
    if signal == "heavy_fix":
        return "优先排查是否需要补充全局纠错字符"
    return "先继续观察样本，必要时再做店铺级实验"

def run_analysis():
    if not DB_PATH.exists():
        print(f"错误: 找不到数据库文件 {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 获取所有有 OCR 文本的样本，并带出店铺信息，便于按店铺定位问题
    rows = conn.execute(
        '''
        SELECT
            s.ocr_text,
            s.candidates_json,
            s.selected_value,
            s.trusted_value,
            s.status,
            s.reason,
            s.selected_candidate_engine,
            s.selected_candidate_variant,
            s.selected_candidate_source_kind,
            s.selected_candidate_correction_count,
            s.required_confirms,
            s.accepted_after_confirms,
            t.platform,
            t.shop_name
        FROM gmv_samples s
        JOIN capture_tasks t ON t.id = s.task_id
        WHERE s.ocr_text IS NOT NULL
        '''
    ).fetchall()

    inner_counter = Counter()
    prefix_counter = Counter()
    correction_inner_counter = Counter()
    correction_prefix_counter = Counter()
    shop_issue_counter = Counter()
    risky_accept_counter = Counter()
    shop_strategy_counter = Counter()

    for r in rows:
        text = r['ocr_text']
        shop_key = _join_shop_key(r)

        # 1. 查找夹在数字中间的“非数字序列”
        # (?<=\d) : 前面必须是数字
        # ([^\d\s]+) : 匹配一个或多个非数字、非空格的字符
        # (?=\d) : 后面必须是数字
        inner_matches = re.findall(r'(?<=\d)([^\d\s]+)(?=\d)', text)
        for m in inner_matches:
            # 过滤掉合法的千分位和句号等
            # 如果序列里只有合法的标点符号，则跳过
            if all(char in VALID_INNER_CHARS for char in m):
                continue
            # 将序列拆分为单个字符进行统计
            for char in m:
                if char not in VALID_INNER_CHARS:
                    inner_counter[char] += 1
                    shop_issue_counter[(shop_key, "inner", char)] += 1

        # 2. 查找紧挨在数字前面的字符（潜在的误识别货币符）
        # (?:^|[^\d]) : 字符串开头或非数字
        # ([^\d\s\.,，。A-Za-z]+) : 非数字、非空格、非标点、非字母的字符序列
        # \s* : 可能有空格
        # (?=\d) : 紧跟着数字
        prefix_matches = re.findall(r'(?:^|[^\d])([^\d\s\.,，。A-Za-z]+)\s*(?=\d)', text)
        for m in prefix_matches:
            # 我们通常只关注紧挨着数字的最后一个字符
            last_char = m[-1]
            if last_char not in VALID_PREFIX_CHARS and last_char not in ['万', '亿']:
                prefix_counter[last_char] += 1
                shop_issue_counter[(shop_key, "prefix", last_char)] += 1

        reason = str(r["reason"] or "")
        selected_value = r["selected_value"]
        trusted_value = r["trusted_value"]
        corrected = (
            "人工" in reason
            or "纠错" in reason
            or (selected_value is not None and trusted_value is not None and selected_value != trusted_value)
        )
        if corrected:
            for char in _extract_unknown_inner_chars(text):
                correction_inner_counter[char] += 1
            for char in _extract_unknown_prefix_chars(text):
                correction_prefix_counter[char] += 1

        selected_candidate = _pick_selected_candidate(r)
        if selected_candidate:
            engine = str(selected_candidate.get("engine") or r["selected_candidate_engine"] or "")
            variant = str(selected_candidate.get("variant") or r["selected_candidate_variant"] or "")
            source_kind = str(selected_candidate.get("source_kind") or r["selected_candidate_source_kind"] or "")
            correction_count = int(
                selected_candidate.get("correction_count")
                or r["selected_candidate_correction_count"]
                or 0
            )
            selected_signal_row = {
                "selected_candidate_engine": engine,
                "selected_candidate_variant": variant,
                "selected_candidate_source_kind": source_kind,
                "selected_candidate_correction_count": correction_count,
                "required_confirms": r["required_confirms"],
                "accepted_after_confirms": r["accepted_after_confirms"],
            }
            accepted = r["status"] == "ok" and r["trusted_value"] is not None
            if accepted:
                for signal in _selected_candidate_signals(selected_signal_row):
                    risky_accept_counter[signal] += 1
                    shop_strategy_counter[(shop_key, signal)] += 1

    print("=========================================")
    print("      OCR 形近字异常分析与监控报告       ")
    print("=========================================\n")

    print(f"共扫描历史样本数量: {len(rows)} 条\n")

    print("【第一类：数字内部断裂异常字符 (Sandwiched Characters)】")
    print("说明：这些字符出现在两个数字之间，极大概率是把 0-9 认成了字母或汉字。")
    print("-" * 50)
    inner_found = False
    for char, count in inner_counter.most_common(20):
        inner_found = True
        status = "[KNOWN] 已在代码中处理" if char in KNOWN_INNER_FIXES else "[NEW] 未收录 (需人工排查)"
        print(f" 字符: '{char}' | 出现次数: {count:<4} | 状态: {status}")
    if not inner_found:
        print(" 很健康，未发现任何数字内部断裂异常！")

    print("\n【第二类：数字前缀异常字符 (Prefix Characters)】")
    print("说明：这些字符紧贴在数字左侧，极大概率是把 ￥ 等货币符认成了汉字。")
    print("-" * 50)
    prefix_found = False
    for char, count in prefix_counter.most_common(20):
        prefix_found = True
        status = "[KNOWN] 已在代码中处理" if char in KNOWN_PREFIX_FIXES else "[WATCH] 待观察 (可能是正常中文或需收录)"
        print(f" 字符: '{char}' | 出现次数: {count:<4} | 状态: {status}")
    if not prefix_found:
        print(" 很健康，未发现任何前缀异常！")

    print("\n【第三类：人工纠错驱动的新增规则候选】")
    print("说明：仅统计人工纠错或最终可信值与候选值不一致的样本，更适合发现真正影响最终结果的新规则。")
    print("-" * 50)
    if correction_inner_counter:
        print(" 数字内部候选（建议考虑加入 OCR_CHAR_REPLACEMENTS）:")
        for char, count in correction_inner_counter.most_common(10):
            print(f"  字符: '{char}' | 出现次数: {count}")
    else:
        print(" 未发现需要新增的数字内部字符候选。")
    if correction_prefix_counter:
        print(" 前缀候选（建议考虑加入 OCR_CURRENCY_ALIASES）:")
        for char, count in correction_prefix_counter.most_common(10):
            print(f"  字符: '{char}' | 出现次数: {count}")
    else:
        print(" 未发现需要新增的前缀字符候选。")

    print("\n【第四类：高风险来源已被接受的统计】")
    print("说明：这些信号代表异常值并非只出现过，而是已经穿透到了最终接受链路。")
    print("-" * 50)
    if risky_accept_counter:
        for signal, count in risky_accept_counter.most_common(10):
            print(f" 信号: {signal:<14} | 被接受次数: {count}")
    else:
        print(" 未发现明显的高风险接受来源。")

    print("\n【第五类：店铺级实验优先候选】")
    print("说明：若某类高风险来源集中在单店铺，应优先做店铺级实验，而不是直接扩大全局规则。")
    print("-" * 50)
    if shop_strategy_counter:
        for (shop_key, signal), count in shop_strategy_counter.most_common(12):
            hint = _shop_strategy_hint(signal)
            print(f" 店铺: {shop_key} | 信号: {signal:<14} | 次数: {count:<4} | 建议: {hint}")
    else:
        print(" 未发现明显的店铺级实验优先候选。")

    print("\n【第六类：店铺级异常聚集】")
    print("说明：用于判断异常是否集中在某一店铺，从而优先考虑店铺级预处理实验，而不是全局改规则。")
    print("-" * 50)
    if shop_issue_counter:
        for (shop_key, issue_type, char), count in shop_issue_counter.most_common(15):
            print(f" 店铺: {shop_key} | 类型: {issue_type:<6} | 字符: '{char}' | 次数: {count}")
    else:
        print(" 未发现明显的店铺级异常聚集。")

    print("\n=========================================")
    print("分析完成。如发现新的高频 [NEW] 未收录字符，\n请将其加入 backend/collectors/ocr_reader.py。")
    print("=========================================")

if __name__ == '__main__':
    run_analysis()
