# DataManager 检查清单

## Auditor 检查项

### DuckDB 操作
- [ ] DuckDB 读连接使用 _get_read_conn()
- [ ] K 线 ASC 排序
- [ ] query() 方法使用共享锁

### 数据源
- [ ] Tushare TOKEN 统一
- [ ] 缓存 key 一致性
- [ ] 熔断机制有效性

### 数据质量
- [ ] adj_factor 回填逻辑
- [ ] Tushare revenue fallback 机制
- [ ] 分钟K线自动填充

## Fixer 修复后检查

- [ ] 修复后无语法错误
- [ ] 修复未引人新问题

## Verifier 验证项

- [ ] 代码与文档一致
- [ ] 修复位置正确
- [ ] 无引人新 bug
