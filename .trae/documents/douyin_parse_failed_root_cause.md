# 抖音官旗店频繁「识别失败」根因分析

## 一、代码层面完整等价性分析

### 1.1 两个店铺配置完全相同

| 配置项 | 抖音官旗店 | GOLF官旗店 | 差异? |
|--------|-----------|-----------|------|
| platform | 抖音 | 抖音 | 相同 |
| default_page_url | `compass.jinritemai.com/screen/shop/single` | 完全一致 | 相同 |
| keyword_hint | 成交金额 | 成交金额 | 相同 |
| capture_mode | remote_edge | remote_edge | 相同 |
| interval_seconds | 1.0 | 1.0 | 相同 |
| confirm_count | 2 | 2 | 相同 |
| width/height/x/y ratio | 0.1/0.06/0/0 | 0.1/0.06/0/0 | 相同 |
| safety_margin | 0.2 | 0.2 | 相同 |
| target | 2,300,000 | 80,000 | **不同** |
| debug_port | 9251 | 9252 | **不同** |
| user_data_dir | `edge_profiles\抖音_抖音官旗店` | `edge_profiles\抖音_GOLF官旗店` | **不同** |

**代码路径相同**：两个店铺使用完全相同的采集、OCR、大屏只读逻辑。

### 1.2 「识别失败」(parse_failed) 产生的两个入口

| 入口 | 文件 | 行号 | 场景 |
|------|------|------|------|
| `_judge()` → selected is None | [scheduler.py](file:///d:/User_Project/GMV-LiveLens/backend/services/scheduler.py#L696-L699) | L697 | OCR 完全没读到候选金额 |
| `capture_once()` → Exception | [scheduler.py](file:///d:/User_Project/GMV-LiveLens/backend/services/scheduler.py#L407-L414) | L407 | 截图/OCR 过程抛异常 |

---

## 二、根因推论（按可能性排序）

### 根因 A（最可能）：value_source 不一致 — 抖音官旗店用了 OCR 模式

**关键发现**：

`defaultValueSourceForTask()` 在 [config.js:L124-L142](file:///d:/User_Project/GMV-LiveLens/frontend/config.js#L124-L142) 中的逻辑：

```javascript
function defaultValueSourceForTask(task) {
  const platform = currentTaskPlatform(task);
  const saved = normalizeValueSourceKey(task?.value_source || "");
  if (saved === "screen_readonly") return "screen_readonly";
  if (saved === "ocr") {
    // 如果有 OCR 运行时数据，保持 OCR
    const hasPersistedOcrRuntime = Boolean(
      task?.last_sample_at || task?.last_success_at 
      || task?.last_value_source === "ocr" 
      || task?.last_ocr_text || task?.last_screenshot_path
    );
    if (hasPersistedOcrRuntime || taskHasPersistedOcrSelection(task)) {
      return "ocr";     // ⬅ 一旦使用过 OCR，就永远卡在 OCR 模式
    }
  }
  if (supportsScreenReadonlyPlatform(platform)) return "screen_readonly";
  return "ocr";
}
```

**推论**：
- 如果"抖音官旗店"之前用 OCR 模式跑过几次并产生过 `last_sample_at` 或 `last_ocr_text`，它就会被**永久锁定在 OCR 模式**
- 而"GOLF官旗店"可能是后来创建的或直接被设成了 `screen_readonly`
- OCR 模式下是**截取页面左上角 10%×6% 的固定区域**进行字符识别，而抖音罗盘的"今日用户支付金额"可能不在这个位置
- screen_readonly 模式则直接通过 DOM 解析精确找到金额元素，成功率远高于 OCR

**验证方法**：检查"抖音官旗店"的 `value_source` 字段值是否为 `"ocr"`

### 根因 B：DOM 渲染时序 — 抖音官旗店页面数据量大，渲染更慢

`_read_douyin_screen_pay_amount()` 中的 DOM 解析依赖：

1. **URL 匹配** [L744](file:///d:/User_Project/GMV-LiveLens/backend/collectors/edge/_readonly.py#L744)：`compass.jinritemai.com/screen/shop/single`
2. **DOM 节点查找** [L666-L743](file:///d:/User_Project/GMV-LiveLens/backend/collectors/edge/_readonly.py#L666-L743)：找 textContent == `"今日用户支付金额"` 的 DOM 元素
3. **金额提取** `collectAmountCandidates()` [L605-L629](file:///d:/User_Project/GMV-LiveLens/backend/collectors/edge/_readonly.py#L605-L629)：在相邻节点中找 ¥数字，且要求恰好 1 个候选
4. **线性文本回退** [L641-L665](file:///d:/User_Project/GMV-LiveLens/backend/collectors/edge/_readonly.py#L641-L665)：页面纯文本扫描

**失败条件及对应 reason_code**：

| 条件 | reason_code |
|------|-------------|
| URL 不匹配 `compass.jinritemai.com/screen/shop/single` | `screen_target_not_found` |
| DOM 和 linear 都找不到指标 | `douyin_screen_root_not_found` |
| 找到指标区域但金额解析失败 | `douyin_screen_payamt_missing` |

这些 reason_code 在 [SCREEN_READONLY_WAITING_REASON_CODES](file:///d:/User_Project/GMV-LiveLens/backend/collectors/edge/_readonly.py#L5-L18) 中被归类为 `readonly_waiting`（可恢复的重试状态），**不会**导致 `parse_failed`。

**结论**：如果抖音官旗店真的走 screen_readonly 模式，失败状态应该是 `readonly_waiting` 而非 `parse_failed`。`parse_failed` = 识别失败 明确表示**任务在 OCR 模式下运行**。

### 根因 C：Edge Profile / 浏览器状态差异

两个店铺使用独立的 Edge Profile（`user_data_dir`），可能状态不同：
- 登录态状态
- 页面缩放级别
- 窗口位置/大小
- 页面是否停留在正确的单店大屏页

---

## 三、推荐行动方案

### 方案 1（首要，立即执行）：将抖音官旗店切换为 screen_readonly 模式

这是**最可能解决**问题的方案，且改动量最小。

**操作**：在前端看板的任务管理界面，「抖音官旗店」的「当前采集方式」下拉框中，选择「大屏只读」（screen_readonly）并保存。

**原理**：
- screen_readonly 通过 DOM 解析直接读取 `今日用户支付金额` 元素的值，不依赖截图 OCR
- 该模式是专为抖音罗盘大屏设计的，准确率远高于 OCR
- GOLF官旗店几乎不失败的极可能就是因为它已经在用 screen_readonly

**但需要确认**：screen_readonly 要求 Edge 页面停留在 `compass.jinritemai.com/screen/shop/single`，且该页面上"今日用户支付金额"指标卡片已渲染完成。

### 方案 2（次要）：如果 screen_readonly 仍偶发失败，增加渲染等待

在 [_readonly.py](file:///d:/User_Project/GMV-LiveLens/backend/collectors/edge/_readonly.py) 的 `_read_douyin_screen_pay_amount()` 中，当前 DOM 解析是即时执行的。如果页面数据量大（抖音官旗店 GMV 高），页面渲染/数据加载更慢，可在金额解析前增加等待：

```python
# 在 _read_douyin_screen_pay_amount 的 JS 中，在 resolveMetricCard() 之前
// 等待方式1: 等待指定DOM元素出现
const waitForMetric = () => {
  // 给 DOM 多一次渲染机会
  return new Promise(resolve => setTimeout(resolve, 1500));
};
await waitForMetric();
```

### 方案 3（兜底）：诊断具体 reason_code

在数据库中查询抖音官旗店的最近失败原因：
```sql
SELECT last_reason, last_reason_code, status, last_value_source 
FROM capture_tasks WHERE shop_name = '抖音官旗店';
```

根据 `last_reason_code` 精确定位问题：
- `douyin_screen_root_not_found` → 指标卡片未渲染，等页面加载完
- `douyin_screen_payamt_missing` → 卡片在但金额为空，数据尚未返回
- `screen_target_not_found` → 页面 URL 不对，不在正确的大屏页
- 空或其他（OCR 模式） → 回到方案 1

---

## 四、总结

| 最可能的根因 | 解决方案 | 改动量 |
|-------------|----------|--------|
| 抖音官旗店的 `value_source=ocr`，截取固定像素区域做 OCR，页面布局导致区域没覆盖到金额 | 切换为 `screen_readonly`（大屏只读） | 零代码，仅前端操作 |

**为什么 GOLF 不失败**：极大概率 GOLF 已经在使用 screen_readonly 模式。

**为什么 OCR 会失败**：OCR 截取的是页面左上角 10%×6% 的固定像素区域（`crop_by_ratio 0,0,0.1,0.06`），抖音罗盘大屏的"成交金额"不一定出现在这个位置，尤其在不同窗口大小、缩放比例、店铺数据量不同的情况下。
