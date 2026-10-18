# 网络架构设计协议

`architecture_design.py` 将架构设计输入转成结构化设计交付物：

```bash
python scripts/architecture_design.py \
  --task-type long_context_nlp \
  --input-shape '[128,64]' \
  --output-shape '[128,320]' \
  --sequence-length 128 \
  --depth 8 \
  --width 512 \
  --attention-heads 16 \
  -o architecture-design.json
```

设计合同会检查：

- 输入/输出形状兼容性
- 感受野或序列长度
- 注意力头数与 hidden width 整除关系
- 深度与宽度
- 跳跃连接位置
- 归一化、正则化、激活函数
- 参数量代理
- 逐层描述
- 数据流向图
- 性能基准计划
- 部署要求

任务类型包含表格分类、图像分类、目标检测、时间序列、序列建模、NLP、长上下文 NLP、深层图像、神经算子、多模态和自定义架构。设计产物仍需进入 prototype、训练、Benchmark、holdout 和创新晋级流程，不能仅凭模板选择宣称优越性。

任务类型只提供初始先验，组件来源由功能需求决定。可跨族选择 local_spatial、long_range_dependency、memory_state、spectral_or_physics、sparse_routing、cross_modal_alignment、graph_relation、stable_optimization 和 low_latency 功能组件。
