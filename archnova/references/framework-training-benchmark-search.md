# PyTorch/JAX、训练、Benchmark 与搜索扩展

## 框架适配

```bash
python scripts/framework_adapters.py --framework pytorch --source model.py --entry Model --inputs inputs.json --allow-runtime -o graph.json
python scripts/framework_adapters.py --framework jax --source model.py --entry apply --inputs inputs.json -o graph.json
```

适配器固定源码 SHA-256，并优先返回显式 `unavailable`。默认不 import 用户代码；显式 `--allow-runtime` 时可对无参数构造的 PyTorch 模块执行受控 Torch FX tracing，并返回标准化节点与 unsupported 列表。无对应运行时或未显式授权时只产生 AST 静态候选。静态函数名和调用名不是实际执行图，不能写成 code_observed。PyTorch FX 仍只覆盖可映射的静态算子；动态控制流、参数化构造、未映射模块会返回 partial/failed。JAX 仍需要 jaxpr 适配器。运行时适配器需要固定环境、版本、输入、随机种子和安全边界；本技能不会把不受限第三方 import 伪装成安全编译。

## 权重训练

`training_runtime.py` 支持当前受限 IR 的有限差分矩阵 SGD，用于验证训练收据与 trainable 参数绑定：

```bash
python scripts/training_runtime.py --model model.json --task task.json -o train.json --epochs 25 --learning-rate 0.1
python scripts/training_runtime.py replay train.json
```

它不是 PyTorch/JAX autodiff、GPU、混合精度、分布式或大模型训练。参数必须显式 trainable；当前支持 64x64 以内参数矩阵的坐标有限差分，训练收据保存初始/最终模型哈希、历史和学习率，回放会拒绝改模型。安装框架后可添加框架训练适配器，但必须复用同一 task hash 和数据拆分。

## CPU/GPU Benchmark

```bash
python scripts/benchmark_runtime.py --model model.json --task task.json --device cpu --warmup 5 --repetitions 50 -o benchmark.json
python scripts/benchmark_runtime.py --model model.json --task task.json --device cuda --warmup 10 --repetitions 100 -o gpu.json
```

CPU 结果是 Python 参考运行时 wall time；GPU 在没有 torch/CUDA/受审阅 lowering 时返回 `unavailable`，不返回伪造零耗时。任何 GPU 结果必须保存设备、框架版本、dtype、同步策略、warmup、重复数和原始样本；跨机器不直接比较。

## 结构搜索

```bash
python scripts/architecture_search.py --model model.json --task task.json --rules relu absolute -o search.json
```

搜索只生成去重后的 IR 候选，绑定 task hash、父模型 hash、规则和预算；不会读取 holdout，也不会把候选声明为通过。真正的接受仍由 design_loop 执行开发集/留出实验。搜索规则扩展时必须增加语义 IR、预算和回归测试。

## 运行边界

当前 runtime IR 支持二维、无量纲、float64、十二种显式算子：基础逐元素/线性算子，以及 transpose、softmax、reshape、concat、layernorm。PyTorch/JAX、训练和 GPU 扩展已经有接口与不可用状态，但尚未声称任意网络、任意算子或硬件性能已支持。将来新增 lowering 时要保留原始框架图、目标 IR、转换差异和执行收据。

## 动态算子注册

算子可以通过 `operator_registry.py fetch` 获取 HTTPS JSON 元数据，要求版本、许可证、来源 SHA-256、实现入口和 verification 状态齐全。远程记录只进入本地缓存和候选库，不执行远程代码；未有本地 reviewed implementation 时保持 `blocked`。

```bash
python scripts/operator_registry.py fetch --url https://example.org/operator.json --sha256 SHA256 -o operator.json
python scripts/operator_registry.py validate operator.json
```
