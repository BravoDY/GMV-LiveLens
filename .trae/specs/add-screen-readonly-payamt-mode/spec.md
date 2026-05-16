# 大屏只读模式 Spec

## Why
当前项目主要依赖 OCR 读取大屏金额，但大促期间滚动数字跳动快、弹窗干扰多，OCR 稳定性会明显下降。已经确认真实大屏 `screen.htm` 会在页面内轮询 `overview.json` 并返回 `payAmt`，因此需要先做一个低风险的“大屏只读模式”测试版，用于验证页面内直读是否稳定。

## What Changes
- 在采集配置工作台增加“大屏只读模式”测试入口，允许用户在打开目标大屏后手动开启只读监听。
- 只在真实已登录页面上下文中读取 `screen.htm` 对应的 `payAmt` 数据，不做浏览器外接口重放。
- 将监听到的 `payAmt` 数值和更新时间先记录到网页系统中的可视区域，供用户观察稳定性。
- 明确测试版边界：本轮不入库、不替换 OCR 主链路、不接入正式采集结果。

## Impact
- Affected specs: 采集配置工作台、真实 Edge 调试能力、页面内只读监听测试能力
- Affected code:
  - `frontend/index.html`
  - `frontend/edge.js`
  - `frontend/app.js`
  - `backend/main.py`
  - `backend/collectors/remote_edge.py`

## ADDED Requirements
### Requirement: 大屏只读模式入口
系统 SHALL 在采集配置工作台提供一个手动开启的大屏只读模式入口，用于当前已绑定页面的测试性监听。

#### Scenario: 用户手动开启只读模式
- **WHEN** 用户已打开真实大屏页面，并在工作台点击“开启只读”之类的按钮
- **THEN** 系统开始在当前真实页面上下文中监听大屏 `payAmt`
- **AND** 不发起浏览器外重放请求
- **AND** 不影响现有 OCR 预览、测试 OCR、保存配置等主链路

### Requirement: 只读模式必须锁定大屏 payAmt 数据源
系统 SHALL 基于大屏 `screen.htm` 页面内可访问的数据源读取 `payAmt`，并以该值作为测试展示的主值。

#### Scenario: 大屏页正常轮询
- **WHEN** 当前真实页面已切换到包含大屏数字的 `screen.htm`
- **THEN** 系统优先读取 `overview.json` 返回中的 `payAmt.value`
- **AND** 若页面尚未进入大屏，则给出明确提示，说明当前还无法读取大屏值

### Requirement: 只读模式结果必须展示在网页系统中
系统 SHALL 将监听到的 `payAmt` 结果写到网页系统中的一个可见区域，供用户观察跳动和稳定性。

#### Scenario: 监听到新值
- **WHEN** 页面内轮询返回新的 `payAmt.value`
- **THEN** 工作台显示最新数值、最近更新时间和最近若干条采样记录
- **AND** 用户无需查看浏览器控制台或后端日志即可判断是否稳定

### Requirement: 测试版只做前端可见记录，不写正式采集结果
系统 SHALL 将本轮大屏只读模式限制为测试版能力，避免未验证稳定前直接影响正式监控链路。

#### Scenario: 用户观察测试结果
- **WHEN** 用户开启只读模式并持续观察数值变化
- **THEN** 系统只在测试区域显示记录
- **AND** 不写入正式任务结果、不覆盖 OCR 结果、不改变现有告警与看板数据口径

## MODIFIED Requirements
### Requirement: 采集配置工作台调试能力
系统从“仅提供页面预览和网络监听调试”调整为“同时提供页面预览、网络监听调试和大屏只读模式测试入口”，但这些能力仍属于调试/验证用途，不默认参与正式采集链路。

## REMOVED Requirements
