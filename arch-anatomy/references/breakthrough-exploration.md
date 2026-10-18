# 突破性架构探索设计器

`breakthrough_explorer.py` 实现 B→C 路线：用组件组合扩大候选空间，用机制假设和复杂度约束控制搜索，用反例、消融、基线、重复种子和成本门限制晋级。

```bash
python scripts/breakthrough_explorer.py --system system.json --components component-index.json --budget 8 -o exploration.json
```

每个候选包含：结构新颖性、机制假设、复杂度代理、基线关系、验证门、失败条件和证据状态。`breakthrough_score` 是启发式先验，不能等同于科学突破证明。

候选只有在以下收据齐全后才可晋级：候选/基线指标、消融指标、反例搜索、重复种子、复杂度/资源和来源证据。任何缺失、反例或无法复现都会保持 `blocked` 或 `unresolved`。
