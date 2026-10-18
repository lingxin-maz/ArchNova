# 前沿能力设计模式

六项尚未完成的能力统一以 design-only contract 表示：

1. JAX jaxpr lowering：保留 primitive、aval、effect、sharding 和未支持项。
2. autodiff/backprop：显式 primal、tangent、cotangent、loss 和 optimizer state。
3. convolution/recurrent/custom ops：绑定 layout、padding、causality、state transition 和 derivative policy。
4. CUDA measurement：把 kernel lowering、同步策略、设备身份、raw profiler output 与正确性测试分开。
5. rank-5+：使用 named axes、layout legality、memory budget 和 property tests。
6. paper-to-fact：使用 source snapshot、hash、evidence span、contradiction graph 和 reviewer receipt。

生成合同：

```bash
python scripts/frontier_capability_design.py generate -o frontier-design.json
python scripts/frontier_capability_design.py validate frontier-design.json
```

这些设计不会把未实现能力包装成可运行功能。每个 capability 必须先通过设计合同中的验证门，保存可回放收据，再从 `design_only` 提升为 `prototype_candidate` 或 `validated`。论文抽取的事实、推断和创新提案必须分开保存，AI 生成内容不能自动标为人工金标准。
## 自动创新闭环

`innovation_pipeline.py` 将 profile、组件、task contract、候选搜索、训练、Benchmark、holdout 和 evidence promotion 组织成一条可回放流水线：`design_only`、`blocked`、`unresolved` 和 `validated` 状态分别保存原因和收据。它不会把没有真实训练、GPU 或证据审查的结果标记为 validated。
