# Checklist

- [x] 周期 API 返回的 `shops[*]` 包含 `brand` 字段 — ✅ 9 家店铺均有 brand，4 家子品牌正确
- [x] 测试环境「集团全周期」中 DESCENTE迪桑特童装旗舰店等子品牌店铺在「子品牌独立店」面板 — ✅ brand 字段已携带
- [x] 正式环境任务管理视图点击后显示任务卡片 — ✅ `renderManagerGrid()` 已实现
- [x] 任务卡片展示 shop_name、platform、brand、status、GMV、Target、进度 — ✅ 卡片 HTML 包含全部字段
- [x] 点击任务卡片可跳转到采集配置编辑 — ✅ `bindManagerCardClicks()` 委托事件已实现
- [x] 所有 GMV 数字为整数 + 千分符格式 — ✅ `Math.round().toLocaleString("zh-CN")`
- [x] 所有 Target 数字为整数 + 千分符格式 — ✅ `formatTarget` 复用 `formatCurrency`
