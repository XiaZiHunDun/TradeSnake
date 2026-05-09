# API 检查清单

## Auditor 检查项

### 生命周期管理
- [x] background_refresh_task 正确启动和取消
- [x] pool_rebalance_background_task 正确启动和取消
- [x] asyncio.Lock 保护 cp_engine.stocks
- [x] 启动时从 SQLite stocks 表预加载

### 后台刷新
- [x] 差异化池刷新（核心池5min/活跃池30min）
- [x] 收盘后预测保存（16:00后）
- [x] K线增量填充（16:00后，最近7天）
- [x] adj_factor Tushare→SQLite（16:00后）
- [x] adj_factor SQLite→DuckDB 回填
- [x] 分钟K线轮换填充（16:30后，每天50只）

### 路由注册
- [x] cp.router（战力/推荐/换股）
- [x] history.router（历史数据）
- [x] simulator.router（模拟交易）
- [x] backtest.router（回测优化）
- [x] risk.router（风险分析）
- [x] prediction.router（预测分析）
- [x] system.router（系统管理）

### CORS与异常
- [x] CORS 配置正确（支持环境变量覆盖）
- [x] 全局异常处理器捕获所有未处理异常
- [x] WebSocket ping/pong 心跳

### 限流
- [ ] 限流器状态持久化（未实现）

## Fixer 修复后检查

- [ ] 修复后无语法错误
- [ ] 修复未引入新问题
- [ ] asyncio.Lock 无死锁风险

## Verifier 验证项

- [ ] 代码与文档一致
- [ ] 修复位置正确
- [ ] 无引入新 bug
- [ ] 后台任务正确清理
