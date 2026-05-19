# 同比文案日期压缩 + 标题精简 — 实施计划

## 需求
1. 将同比文案中的日期从 `YYYY/M/DD` 改为 `YY/MM/DD`（如 `2026/5/18` → `26/05/18`），解决移动端文案过宽显示不全的问题
2. 将左上角标题从 `DST平台GMV实时监控` 改为 `平台GMV实时监控`

---

## 影响范围分析

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `frontend/dashboard-shared.js` | 函数内部逻辑更改 | `formatDateRangeDisplay()` 中的 `fmt` 格式转换函数 |
| `frontend/index.html` | 1 处文本更改 | `<h1 class="header-title">` 的文本内容 |

不涉及 CSS、后端代码。

---

## 步骤 1 — 日期格式压缩：YYYY/M/DD → YY/MM/DD

**文件**: `frontend/dashboard-shared.js`
**位置**: `formatDateRangeDisplay()` 函数内的 `fmt` 辅助函数 ([dashboard-shared.js#L196](file:///d:/User_Project/GMV-LiveLens/frontend/dashboard-shared.js#L196))

### 现状
```javascript
const fmt = (d) => (d || "").replace(/-/g, "/");
```
输入 `"2026-05-18"` → 输出 `"2026/5/18"`（仅替换分隔符，不补零、不截断年份）

### 目标
输入 `"2026-05-18"` → 输出 `"26/05/18"`

### 修改方案
```javascript
const fmt = (d) => {
  if (!d) return "";
  const parts = d.split("-");
  if (parts.length !== 3) return d;
  const yy = parts[0].slice(-2);
  const mm = parts[1];
  const dd = parts[2];
  return `${yy}/${mm}/${dd}`;
};
```

### 影响范围
- PC 端 `.total-card-date-range` 内的同比文案
- 移动端 `.mobile-yoy-row` 内的同比文案（共用同一函数）
- 实时模式: `[ 26/05/18 ]   同比   [ 25/05/21 ]`
- 周期模式: `[ 26/05/18 累计至 26/05/18 ]   同比   [ 25/05/18 累计至 25/05/18 ]`

### 兼容性
- 输入空值 → 返回空字符串 （与原行为一致）
- 输入格式异常（非标准 `YYYY-MM-DD`）→ 返回原值兜底


## 步骤 2 — 标题精简

**文件**: `frontend/index.html`
**位置**: 第 15 行 ([index.html#L15](file:///d:/User_Project/GMV-LiveLens/frontend/index.html#L15))

### 修改
```diff
- <h1 class="header-title">DST平台GMV实时监控</h1>
+ <h1 class="header-title">平台GMV实时监控</h1>
```

### 影响范围
- 仅页面左上角标题文本，无任何 CSS/JS 关联


## 验证清单
- [ ] PC 端同比日期显示为 YY/MM/DD 格式 (如 `26/05/18`)
- [ ] 移动端同比日期显示为 YY/MM/DD 格式，不再超出容器宽度
- [ ] 周期模式日期同样压缩为 YY/MM/DD 格式
- [ ] 空数据时无 JS 报错
- [ ] 左上角标题变为 "平台GMV实时监控"
