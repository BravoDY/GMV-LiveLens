# Graphify 集成方案：GMV-LiveLens 及通用项目

---

## 一、Graphify 是什么（30 秒回顾）

将代码库转化为可查询的结构化知识图谱，AI 助手可直接在图中导航而非逐个文件读取，上下文消耗减少最高 71.5 倍。

- **第一阶段（AST）**：tree-sitter 零 LLM 成本提取 23 种语言的代码结构（类、函数、导入、调用）
- **第二阶段（语义）**：LLM 提取非代码文件的语义关系和设计意图
- **输出**：`graph.html`（交互可视化）+ `graph.json`（可查询图谱）+ `GRAPH_REPORT.md`（审计报告）
- **附加能力**：MCP 服务器（AI 助手直连）、文件监听（实时同步）、增量缓存（SHA256）

---

## 二、GMV-LiveLens 集成方案

### 阶段 1：基础安装与首次运行

**目标**：对 GMV-LiveLens 生成第一份代码知识图谱

#### Step 1：安装

```powershell
pip install graphifyy
```

如果需要在 AI 助手中注册为技能（当前项目用的是 Trae IDE）：

```powershell
graphify install
```

#### Step 2：首次生成图谱

```powershell
# 在项目根目录执行
graphify .
```

这会对 `c:\Users\yjd22\Desktop\python项目\GMV-LiveLens` 下的所有代码和文档生成图谱。

输出默认位置：`graphify-out/graph.html`、`graphify-out/graph.json`、`graphify-out/GRAPH_REPORT.md`

#### Step 3：审查输出

| 输出文件 | 用途 | 关注点 |
|---|---|---|
| `GRAPH_REPORT.md` | God Nodes（枢纽节点）、意外连接、推荐查询 | 检查哪些模块是"超连接节点"，验证模块拆分是否合理 |
| `graph.html` | 交互式可视化图谱 | 浏览器打开后查看模块关系，搜"edge"、"ocr"、"scheduler" 验证图谱准确性 |
| `graph.json` | 持久化图谱 | 后续 AI 助手查询时的数据源 |

#### Step 4：处理预期问题

| 预期问题 | 对策 |
|---|---|
| `data/` 目录过大（Edge Profile、SQLite） | 将 `data/` 加入 `.gitignore` 风格排除，Graphify 支持 `--ignore` 参数 |
| 前端 JS 是原生 JS 非模块化，AST 提取效果有限 | 正常现象，前端部分主要靠文档和注释来定义关系 |
| OCR 模块（`backend/ocr/`）中可能含二进制/tesseract 引用 | 这些文件会被 tree-sitter 跳过，不影响整体 |

### 阶段 2：配置过滤规则

**目标**：排除无关目录，聚焦核心代码

项目根目录创建 `.graphifyignore`（或使用 `--ignore` 参数）：

```
data/
__pycache__/
*.pyc
.env
*.sqlite3
node_modules/
.trae/
```

### 阶段 3：日常使用工作流

**目标**：让 Graphify 在开发过程中持续发挥作用

#### 工作流 A：手动增量更新

```powershell
# 仅处理变更文件（基于 SHA256 缓存）
graphify . --update
```

**触发时机**：完成一个较大的功能分支后、准备让 AI 助手做代码审查前

#### 工作流 B：文件监听自动同步

```powershell
graphify . --watch
```

**注意**：这会持续运行一个守护进程。建议仅在密集开发时使用，日常不推荐常驻。

#### 工作流 C：向 AI 助手查询图谱

生成图谱后，AI 助手可以直接读取 `graph.json` 或 `GRAPH_REPORT.md` 快速理解项目架构，而不需要逐个文件读取。

---

## 三、通用项目集成模板（以后每个项目都能用）

### 3.1 一次性初始化（新项目接入）

```powershell
# 1. 安装（全局，仅需一次）
pip install graphifyy

# 2. 进入项目目录
cd your-project

# 3. 创建过滤规则（可选但推荐）
cat > .graphifyignore << EOF
node_modules/
__pycache__/
*.pyc
.env
*.sqlite3
data/
dist/
build/
.git/
EOF

# 4. 生成图谱
graphify .

# 5. 打开可视化审查
# 浏览器打开 graphify-out/graph.html
```

### 3.2 项目生命周期中的使用节点

| 阶段 | 操作 | 目的 |
|---|---|---|
| **接手新项目** | `graphify .` | 快速理解代码架构、模块边界 |
| **Feature 开发前** | `graphify . --update` | 获取最新架构上下文 |
| **PR 提交前** | 读 `GRAPH_REPORT.md` 检查 God Nodes | 发现过度耦合的模块 |
| **重构后** | `graphify . --update` 对比前后图谱 | 验证拆分是否合理 |
| **新人上手** | 直接把 `graph.html` 分享给同事 | 交互式探索项目结构 |

### 3.3 高级：Git Hooks 自动更新

在项目 `.git/hooks/post-merge` 和 `post-checkout` 中自动触发 `graphify . --update`，确保切换分支后图谱始终是最新的。不过这属于可选配置，初期不需要。

### 3.4 高级：CI 中生成图谱

在 `.github/workflows/` 中添加一个 job，将图谱作为构建产物上传，让 PR 审查者可以直接查看变更对项目架构的影响。

---

## 四、适用性判断：什么项目值得用 Graphify

| 项目特征 | 适合度 | 说明 |
|---|---|---|
| 多模块后端（如 GMV-LiveLens 的 routers/collectors） | ✅ 高 | AST 提取效果最好 |
| 单文件脚本 | ❌ 低 | 图谱价值不大 |
| 前端 SPA（React/Vue） | ✅ 中 | 组件依赖关系有参考价值 |
| 原生 JS 前端 | ⚠️ 低 | AST 提取效果有限，依赖文档补充 |
| 含大量文档的项目 | ✅ 高 | 语义提取阶段发挥作用 |

---

## 五、GMV-LiveLens 专属建议

### 当前最值得做的

1. **`pip install graphifyy` → `graphify .`** → 浏览器打开 `graph.html`，看看代码结构被自动分析成了什么样
2. **重点审查 `GRAPH_REPORT.md` 中的 God Nodes** — 如果 `remote_edge.py`（兼容壳）或 `scheduler.py` 被标记为超连接节点，这是正常的；但如果某个不该是枢纽的模块被标记，说明可能过度耦合
3. **将 `graph.html` 和 `GRAPH_REPORT.md` 加入 `.gitignore`**（这些是衍生文件，不需要提交到仓库）

### 暂不推荐的

- 文件监听常驻（`--watch`）会占用资源，GMV-LiveLens 已有 Edge 进程需要管理，不建议加更多常驻进程
- MCP 服务器在当前阶段不需要，除非你打算让 AI 助手频繁查询代码图谱来辅助开发
