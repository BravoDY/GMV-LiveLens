# 京东大屏只读支持 Spec

## Why
当前正式大屏只读链路只支持天猫/生意参谋，京东平台虽然已有独立店铺会话与网页空间隔离基础，但还没有京东专属的大屏只读解析。用户已经确认京东实时看板页面 `https://sz.jd.com/sz/view/realTime/realKanBans.html` 中“今日成交金额累计”就是需要写入正式任务与实时看板的真实 GMV，因此需要补齐京东平台的通用支持。

## What Changes
- 将 `screen_readonly` 正式能力从“仅支持天猫”扩展为“支持天猫与京东”。
- 为京东新增专属的大屏页识别规则，锁定 `realKanBans.html` 作为京东大屏只读的受控页面空间。
- 为京东新增页面内只读取值规则，从当前真实已登录页面上下文中读取“今日成交金额累计”作为正式采集值。
- 更新前端平台提示、保存校验和测试说明，让京东平台也能像天猫一样选择并保存 `大屏只读`。
- 保持天猫现有只读逻辑不变，避免把京东规则混入天猫分支。

## Impact
- Affected specs: 采集配置工作台、页面只读正式采集链路、平台专属大屏解析、真实 Edge 页面隔离、实时看板任务卡片
- Affected code:
  - `backend/main.py`
  - `backend/collectors/remote_edge.py`
  - `backend/services/scheduler.py`
  - `backend/services/shop_config.py`
  - `frontend/config.js`
  - `frontend/edge.js`
  - `frontend/core.js`
  - `frontend/index.html`

## ADDED Requirements
### Requirement: 京东平台必须支持正式大屏只读模式
系统 SHALL 允许京东平台任务像天猫一样选择 `大屏只读` 作为正式采集方式，并让该选择进入保存、调度和看板展示链路。

#### Scenario: 京东任务选择大屏只读
- **WHEN** 用户为京东店铺任务选择 `大屏只读` 并保存
- **THEN** 任务正式采集方式保存为 `screen_readonly`
- **AND** 后续调度不再走 OCR 主值链路
- **AND** 实时看板展示该京东任务的正式只读结果

### Requirement: 京东大屏只读必须锁定受控页面空间
系统 SHALL 将京东实时看板页 `realKanBans.html` 视为京东大屏只读的专属受控页面空间，只在当前已绑定的真实 Edge 页面上下文内识别和读取。

#### Scenario: 京东页面已进入实时看板
- **WHEN** 当前绑定页或其受控 frame 已进入 `https://sz.jd.com/sz/view/realTime/realKanBans.html`
- **THEN** 系统将该页面识别为京东大屏只读有效页面
- **AND** 只在该受控页面空间内执行后续取值
- **AND** 不得误复用天猫 `screen.htm` 识别规则

#### Scenario: 京东页面尚未进入实时看板
- **WHEN** 京东任务处于 `screen_readonly` 模式，但当前绑定页还未进入 `realKanBans.html`
- **THEN** 系统返回明确的等待/未就绪状态
- **AND** 给出“先进入京东实时看板页再读取”的提示
- **AND** 调度器继续按受控频率重试

### Requirement: 京东大屏只读必须读取今日成交金额累计
系统 SHALL 在京东实时看板受控页面空间内读取“今日成交金额累计”作为正式大屏只读值，并将其作为京东任务正式 GMV 主值。

#### Scenario: 京东大屏取值成功
- **WHEN** 当前真实页面可稳定读到“今日成交金额累计”
- **THEN** 系统返回结构化的只读结果、页面状态、时间信息和原因说明
- **AND** 调度器将该数值写入任务正式运行态
- **AND** 实时看板店铺卡片展示的 GMV 与该正式值一致

### Requirement: 京东大屏只读必须遵守低风险页面内读取边界
系统 SHALL 继续遵守页面内读取原则：所有京东大屏只读动作都发生在真实已登录页面上下文内，不做浏览器外 Cookie/Token 重放。

#### Scenario: 京东正式读取大屏值
- **WHEN** 京东 `screen_readonly` 任务运行
- **THEN** 系统只使用当前真实 Edge 页面的 DOM、运行时状态或页面内网络上下文读取数值
- **AND** 不将京东登录态复制到浏览器外独立请求链路

## MODIFIED Requirements
### Requirement: 平台支持判断
系统从“正式大屏只读仅支持天猫”调整为“正式大屏只读按平台专属规则支持天猫与京东”。每个平台都必须使用自己的页面识别与取值规则，互不混用。

### Requirement: 采集配置工作台的平台提示
系统从“京东平台提示暂不支持大屏只读”调整为“京东平台允许选择并保存大屏只读，同时提示目标页应进入京东实时看板 `realKanBans.html`”。

## REMOVED Requirements
### Requirement: 京东平台禁止保存正式大屏只读
**Reason**: 用户已提供京东真实大屏页和目标值口径，希望京东也像天猫一样作为平台通用能力接入。  
**Migration**: 将原有“京东不支持大屏只读”的前后端拦截，替换为“京东走独立规则支持大屏只读”的平台分支。
