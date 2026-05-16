# Tasks

- [x] Task 1: 移除 ddddocr 的纯数字限制
  - [x] SubTask 1.1: 打开 `backend/collectors/ocr_reader.py` 文件。
  - [x] SubTask 1.2: 定位到 `_dddd_engine` 函数（约 57-66 行）。
  - [x] SubTask 1.3: 删除 `try: engine.set_ranges(0) except Exception: pass` 相关的代码块，只保留引擎初始化和返回逻辑。

# Task Dependencies
无依赖。