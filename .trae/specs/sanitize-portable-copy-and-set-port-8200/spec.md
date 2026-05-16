# 副本脱敏与 8200 端口切换 Spec

## Why
用户准备把 `D:\GMV-LiveLens-portable` 交给别人使用，但该副本当前仍可能包含浏览器 Cookie、缓存、保存密码及其它可还原账号状态的本地数据，存在隐私与账号安全风险。同时，默认端口仍是 `8100`，用户希望统一改为 `8200`。

## What Changes
- 仅针对 `D:\GMV-LiveLens-portable` 副本执行浏览器 Profile 脱敏，不修改原工作项目
- 清理副本内 Edge Profile 中的 Cookie、缓存、会话恢复、保存密码及其它敏感浏览器数据
- 保留项目运行所需的目录结构，但不保留任何可直接复用的登录态
- 将副本默认服务端口从 `8100` 改为 `8200`
- 同步更新启动脚本、环境自检、文档和相关默认访问地址

## Impact
- Affected specs: 副本安全交付、浏览器 Profile 脱敏、默认启动端口、部署文档
- Affected code: `D:\GMV-LiveLens-portable\data\edge_profiles\`、`D:\GMV-LiveLens-portable\第0步_首次安装并启动.bat`、`D:\GMV-LiveLens-portable\第1步_启动GMV服务.bat`、`D:\GMV-LiveLens-portable\backend\services\runtime_env.py`、`D:\GMV-LiveLens-portable\backend\tools\check_portable_env.py`、`D:\GMV-LiveLens-portable\README.md`

## ADDED Requirements
### Requirement: 副本交付前必须脱敏浏览器 Profile
系统 SHALL 在交付 `D:\GMV-LiveLens-portable` 前清理副本中的浏览器隐私数据，包括 Cookie、缓存、保存密码、会话恢复痕迹及其它可泄露账号状态的浏览器文件。

#### Scenario: 用户准备把副本交给别人
- **WHEN** 用户要求清理副本里的浏览器隐私数据
- **THEN** 副本中的浏览器 Profile 不再包含可直接复用的登录态
- **AND** 副本中不再保留可暴露账号密码或最近登录状态的浏览器敏感文件

### Requirement: 脱敏必须仅作用于副本目录
系统 SHALL 只清理 `D:\GMV-LiveLens-portable` 内的浏览器数据，不得删除或污染原项目目录中的登录态与运行数据。

#### Scenario: 原项目仍需继续使用
- **WHEN** 脱敏流程执行完成
- **THEN** 原项目目录保持不变
- **AND** 只有副本目录中的 Profile 被清理

### Requirement: 默认端口必须切换为 8200
系统 SHALL 将副本项目的默认启动端口统一改为 `8200`，并同步更新启动入口、环境自检输出及文档示例。

#### Scenario: 用户在新电脑首次运行副本
- **WHEN** 用户双击副本中的推荐启动脚本
- **THEN** 系统默认监听 `127.0.0.1:8200`
- **AND** 文档和检查输出与该端口保持一致

### Requirement: 文档必须明确脱敏后的使用影响
系统 SHALL 在文档中明确说明：脱敏后的副本不会保留任何平台登录态，接收方首次使用时必须重新登录。

#### Scenario: 接收方按文档使用副本
- **WHEN** 接收方阅读副本使用说明
- **THEN** 能明确知道登录态已被清理
- **AND** 能明确知道首次运行后需要手动登录和重新绑定

## MODIFIED Requirements
### Requirement: 副本交付默认访问地址
副本交付时的默认访问地址必须从 `http://127.0.0.1:8100` 改为 `http://127.0.0.1:8200`。

## REMOVED Requirements
### Requirement: 副本保留原始浏览器登录态
**Reason**: 该行为会泄露用户账号状态、Cookie 和潜在保存密码，不适合对外交付。
**Migration**: 交付前清理副本中的 Profile 敏感文件；接收方首次使用时重新登录目标平台账号。
