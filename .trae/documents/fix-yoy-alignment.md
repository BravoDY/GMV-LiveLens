# 同比标签对齐修复 — 计划

## 当前问题

用户期望"同比"标签像"总达成进度"一样，**标签和数值在网格列中靠右对齐**（参考右下图），形成上下标签↘数值的整齐堆叠。当前仅 "同比" 标签本身做了 `text-align:right`，但其父 div 仍是左对齐，视觉上 "同比" 两字没有跟下方的 `-63.0%` 右边缘对齐。

### 参考：总达成进度（正确效果）
```html
<div style="text-align:right;">           ← 父级右对齐
  <div class="metric-label">总达成进度</div>  ← 标签靠右
  <div class="total-progress-value">12.1%</div>  ← 数值也靠右
</div>
```
两者右边缘在一条垂线上，视觉整齐。

### 当前：同比（需修复）
```html
<div>                                    ← 父级无对齐
  <div class="metric-label" style="text-align:right;">同比</div>  ← 仅标签右对齐，但父级左对齐下无效
  <div class="total-yoy-value">-63.0%</div>  ← 左对齐
</div>
```
两者右边缘不在一条垂线，"同比"标签视觉上孤立。

---

## 修复方案

**父级 div 加 `text-align:right`**，与"总达成进度"列完全一致。

```html
<div style="text-align:right;">
  <div class="metric-label">同比</div>
  <div class="total-yoy-value${yoyClass}">${yoy}</div>
</div>
```

效果：
```
  总目标            总达成进度    │      同比
  ¥230,910,000      12.1%        │    -63.0%    ← 标签和数值均靠右
```

---

## 涉及文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `frontend/dashboard-shared.js` L213 | 移除 `style="text-align:right;"` 从 label，加到父级 div | 与 达成进度 列一致 |

## 风险

- **L1**：10 字符改动，纯 HTML 对齐
