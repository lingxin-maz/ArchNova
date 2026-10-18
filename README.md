# ArchNova

面向神经网络的架构分析、功能导向创新设计、模型诊断和训练策略探索 skill。

## 安装与使用

将 `archnova/` 文件夹放入 Agent 的 skills 目录即可，例如 `.codex/skills/archnova/`，随后在对话中请求使用 ArchNova。

**默认无需安装 Python 依赖、深度学习框架或额外模型 API。** 当前 Agent 直接阅读技能指引、参考资料和组件规范，完成分析与设计。

例如：

> 使用 ArchNova 分析这份论文和代码，总结模型特点与不足，按功能跨架构提出两个改进候选，并给出逐层设计、训练策略、消融和可信度验证方案。

## 能力

- 论文与源码架构拆解、模型画像与不足诊断。
- 跨网络族按功能复用组件，探索新架构和微观设计。
- 形状/状态/参数共享、感受野、注意力、跳连与成本分析。
- 训练策略、基线、消融、反例、泛化与部署验证计划。
- 区分事实、推导、创新假设和未决证据。

## 目录

```text
archnova/
  SKILL.md             Agent 技能入口
  references/          按需阅读的设计与验证指南
  component-library/   组件素材与来源规范
  ontology.json        架构本体
  assets/              Schema 与示例
  scripts/             可选 Python 辅助工具
  requirements.txt     仅供可选工具/开发测试
  tests/               维护者回归测试
  evals/               评测配置
```

## 可选工具与开发

脚本用于机械 JSON 校验、有限原型实验、回放和打包，不是加载 skill 或进行设计的前提。仅在需要相应工具时检查环境；安装说明和维护命令见 `archnova/references/optional-tools.md`。

真实训练和 GPU 测量仍需相应运行环境及原始收据。缺少环境时，Agent 可以继续设计和证据审查，但不能宣称实验完成或机器校验通过。

维护者可运行 `python archnova/scripts/build_codex_skill.py` 生成 `dist/archnova-codex-skill.zip`；生成物不提交到源码仓库。

## 可信度边界

创新提案不自动等于科学突破。参数估算、人工式接口核对、机器校验、有限样本结果与泛化/优越性证明分别报告。真实论文评测的原始材料与人工待审记录不包含在源码包中。

## 许可证

见 `LICENSE`。
