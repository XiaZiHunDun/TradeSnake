# CPEngine 检查清单

## Auditor 检查项

### 公式正确性
- [ ] CP 计算公式正确性（growth/value/quality/momentum）
- [ ] WEIGHTS 权重配置
- [ ] 归一化 clip_percentile=0.975
- [ ] 缓存机制（real_time_score 计算）
- [ ] 并行计算与主流程一致性
- [ ] get_cp_explanation() 注释正确性

### 数据流
- [ ] 输入数据校验（ST股过滤）
- [ ] 各因子 NaN 处理
- [ ] 涨跌停判断 abs(change_pct) < 9.9

### 性能
- [ ] 并行计算线程数
- [ ] 缓存命中率
- [ ] 批量计算效率

## Fixer 修复后检查

- [ ] 修复后无语法错误
- [ ] 修复后单元测试通过
- [ ] 修复未引人新问题

## Verifier 验证项

- [ ] 代码与文档一致
- [ ] 修复位置正确
- [ ] 无引人新 bug
