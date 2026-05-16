# Checklist

- [x] Edge 按钮点击不再跳转到采集配置页
- [x] 采集全部按钮可见可点击
- [x] 服务正常启动 (health=ok)
- [x] 实时看板 API 返回 9 个 task
- [x] 周期看板 API 返回品牌分组正确的 GMV
- [x] 缓存状态 API 正常 (cached=true, stale=false)
- [x] SQL 注入风险：参数化查询覆盖
- [x] 硬编码密钥：无
- [x] requirements.txt 包含 pymysql 和 python-dotenv
- [x] 周期模式 platforms 结构非空（5 平台：天猫/京东/唯品/抖音/得物）
- [x] dashboard_query.py 无未使用 import
