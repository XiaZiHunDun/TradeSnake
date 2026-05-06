# ML 模块 Auditor 检查清单

## 数据验证

- [ ] `cp_store.get_snapshot(date)` 在有数据日期返回非空列表
- [ ] `duckdb.get_klines_bulk_for_date()` 返回正确格式的 DataFrame
- [ ] `_get_codes_for_date()` fallback 限制 500 只股票以内
- [ ] `build_target()` 计算的 horizon 日收益率正确

## 模型质量

- [ ] Val AUC > 0.52（至少略好于随机）
- [ ] Val MAE < 3.0
- [ ] OOS IC 显著为正（t-stat > 1.5）

## 特征质量

- [ ] 技术因子 IC 经过验证（通过 alpha_analyzer）
- [ ] CP 战力因子（growth/momentum/value/quality）已纳入特征列表
- [ ] 特征无前瞻偏差（只使用当前时点可获得的数据）

## Walk-Forward 验证

- [ ] 至少 5 个 fold 完成
- [ ] 平均 OOS Sharpe > 0.3
- [ ] 无 fold 出现 NaN 或异常值

## 代码质量

- [ ] `features.py` 中 `ALL_FEATURES` 与实际使用一致
- [ ] `StockPredictor` 支持 save/load
- [ ] 超时处理（单个 fold 不应超过 5 分钟）