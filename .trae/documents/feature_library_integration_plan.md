# OCR 特征库正式关联计划

## 1. 摘要
用户要求将之前发现并硬编码的“OCR 形近字纠错规律”沉淀为一个正式的“特征库”，并让主项目与自动化监控脚本都直接读取这个库，实现真正的代码解耦和自动化关联。本计划将把原本在代码里写死的长串 `.replace()` 和正则表达式，重构为集中的字典与列表配置，并让项目逻辑动态加载该配置。

## 2. 现状分析
- 目前 `backend/collectors/ocr_reader.py` 中的 `extract_candidates` 使用了极为冗长的 `ocr_text.replace(...).replace(...)` 硬编码链条。
- 货币符号的误识别（如“半”、“羊”）被硬编码在 `AMOUNT_PATTERN` 正则和 `_candidate_reason` 函数中。
- `backend/tools/find_ocr_anomalies.py` 中的 `KNOWN_INNER_FIXES` 也是一份冗余配置。
这种分散的硬编码不利于后续的维护，如果“体检脚本”发现了新特征，开发者需要修改三个不同的地方。

## 3. 提议的变更
### 3.1 建立中央特征库 (修改 `ocr_reader.py`)
在 `backend/collectors/ocr_reader.py` 顶部定义正式的特征库配置：
```python
# --- OCR 形近字纠错特征库 ---
OCR_CHAR_REPLACEMENTS = {
    # 0的形近字
    "o": "0", "O": "0", "D": "0", "U": "0", "u": "0",
    # 1的形近字
    "l": "1", "I": "1", "i": "1", "j": "1", "J": "1",
    # 4的形近字
    "P": "4", "h": "4", "H": "4", "旧": "4", "忙": "4",
    # 5的形近字
    "s": "5", "S": "5",
    # 7的形近字
    "门": "7", ">": "7",
}

# 容易被误识别为货币符的汉字/符号特征库
OCR_CURRENCY_ALIASES = ["半", "举", "夫", "羊", "旧"]
```

### 3.2 动态挂载正则与逻辑 (修改 `ocr_reader.py`)
- 利用 `OCR_CURRENCY_ALIASES` 动态生成 `AMOUNT_PATTERN` 正则表达式。
- 在 `_candidate_reason` 评分中同样使用该动态生成的正则。
- 在 `extract_candidates` 函数中，使用 `for old_char, new_char in OCR_CHAR_REPLACEMENTS.items():` 的循环方式替代硬编码的长链条 `.replace`。

### 3.3 监控脚本关联 (修改 `find_ocr_anomalies.py`)
让脚本直接从项目导入特征库，实现单点维护（Single Source of Truth）：
```python
from backend.collectors.ocr_reader import OCR_CHAR_REPLACEMENTS, OCR_CURRENCY_ALIASES

KNOWN_INNER_FIXES = set(OCR_CHAR_REPLACEMENTS.keys())
KNOWN_PREFIX_FIXES = set(OCR_CURRENCY_ALIASES)
```

## 4. 假设与决策
- **决策**：将特征库沉淀在 `ocr_reader.py` 的顶部常量中，而不是单独的 json/yaml 配置文件中。这样既能保证性能（避免频繁读取文件），又易于同属于 OCR 领域的代码共存。

## 5. 验证步骤
1. 实施代码修改。
2. 运行 `python backend/tools/find_ocr_anomalies.py`，确认脚本成功读取了主项目中的特征库。
3. 执行几条单元测试，确保 `extract_candidates` 依然能正确纠错（如 `"1旧60496"` 被正确转换为 `1460496`）。