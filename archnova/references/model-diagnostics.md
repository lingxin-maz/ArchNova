# 模型画像、训练策略与微观设计

`model_diagnostics.py` 会读取已验证的 IR 和 task contract，输出 characteristics、deficits、training_strategies 和 micro_designs。每项都区分 observed、derived、proposed，并带验证门和失败条件。

```bash
python scripts/model_diagnostics.py --model initial.json --task task.json --system system.json -o diagnostics.json
```

训练策略和微观设计是实验假设，不能直接当成已验证改进；innovation pipeline 在提供 task/model 时会自动附加这份诊断报告。
