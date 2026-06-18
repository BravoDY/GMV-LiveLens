# Graphify 手动操作手册

---

## 前置状态（已全部就绪）

| 事项 | 说明 |
|---|---|
| 全局 `.graphifyignore` | `C:\Users\yjd22\.graphifyignore` ✅ |
| `graphifyy` v0.8.14 | ✅ |
| Trae `/graphify` 技能 | `~/.claude/skills/graphify/SKILL.md` ✅ |

---

## 你现在就可以做

### 在 Trae 里直接调用（推荐，已可用）

在 Trae 输入框输入：

```
/graphify .
```

AI 助手会自动在 `api_to_mysql` 项目目录执行图谱生成，然后基于图谱理解项目架构。

---

### 在终端里手动跑（需先加 PATH）

管理员 PowerShell 执行一次：

```powershell
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";C:\Users\yjd22\AppData\Roaming\Python\Python314\Scripts", "User")
```

重启终端后 `graphify .` 即可。

---

## 两条路的关系

| 方式 | 前提 | 命令 |
|---|---|---|
| Trae 内 `/` 调用 | 无需 PATH，`graphify install` 已完成 ✅ | `/graphify .` |
| 终端直接敲 | 需加 PATH | `graphify .` |

**两条路互不依赖，选哪个都行。**
