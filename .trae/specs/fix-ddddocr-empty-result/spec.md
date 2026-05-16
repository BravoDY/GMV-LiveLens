# Fix ddddocr Empty Result Spec

## Why
用户在使用 `ddddocr` 引擎识别包含 `¥` 和 `,` 等符号的金额图片时，发现最终识别结果为空（“未识别”，OCR 原文为 `-`）。
经过排查，原因是 `backend/collectors/ocr_reader.py` 中初始化 `ddddocr` 时，调用了 `engine.set_ranges(0)`。这个设置强制要求模型只输出纯数字（0-9）。当图片中存在非常明显的非数字符号（如人民币符号 `¥` 和千分位逗号 `,`）时，模型无法找到高置信度的纯数字路径，从而直接返回空字符串。
为了让 `ddddocr` 能够正常输出包含符号的原始文本，并交由后续强大的正则匹配逻辑（`extract_candidates`）提取金额，我们需要移除这个限制。

## What Changes
- 移除 `backend/collectors/ocr_reader.py` 中 `_dddd_engine` 函数里的 `engine.set_ranges(0)` 限制。
- 让 `ddddocr` 输出包含字母和符号的原始字符串，由后端的 `extract_candidates` 利用 `AMOUNT_PATTERN` 正则表达式统一处理。

## Impact
- Affected specs: 无
- Affected code: `backend/collectors/ocr_reader.py`

## MODIFIED Requirements
### Requirement: ddddocr 引擎初始化
**原逻辑**：初始化时使用 `set_ranges(0)` 限制仅输出数字。
**新逻辑**：初始化时不调用 `set_ranges`，允许输出任意字符，依靠已有的正则过滤机制提取正确的金额数字。
