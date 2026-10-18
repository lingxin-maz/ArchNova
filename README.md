# ArchNova

面向神经网络的架构分析、组件检索、功能导向设计与证据验证 skill。

## 项目结构

```text
archnova/
  SKILL.md             技能入口
  requirements.txt     Python 依赖
  ontology.json        架构本体
  assets/              Schema 与示例
  component-library/   组件素材库
  references/          使用协议与设计参考
  scripts/             分析、设计、验证和构建工具
  tests/               回归测试
  evals/               评测配置
LICENSE
README.md
```

## 安装

将 `archnova/` 文件夹复制到所需位置的 `.codex/skills/archnova/`。
安装 Python 工具依赖：

```shell
python -m pip install -r archnova/requirements.txt
```

PyTorch/JAX 为可选依赖；基础测试与参考运行时不要求安装它们。

## 主要入口

- 架构设计：`scripts/architecture_design.py`
- 模型诊断与训练策略建议：`scripts/model_diagnostics.py`
- 网络系统 profile：`scripts/network_system.py`
- 候选探索：`scripts/breakthrough_explorer.py`
- 设计流水线：`scripts/innovation_pipeline.py`
- 实验与回放：`scripts/design_loop.py`
- 文献候选检索：`scripts/research_watch.py`

以上路径相对于 `archnova/`。具体参数通过各脚本 `--help` 查看；使用流程见 `SKILL.md` 和 `references/`。

## 验证

```shell
python -B -m unittest discover -s archnova/tests
python archnova/scripts/build_ontology.py --check
python archnova/scripts/capability_audit.py archnova
```

## 构建安装包

```shell
python archnova/scripts/build_codex_skill.py
```

生成 `dist/archnova/` 和 `dist/archnova-codex-skill.zip`。生成物不纳入源码仓库，可作为 GitHub Release 附件发布。

## 能力边界

组件组合、模型诊断和训练策略包含规则与设计假设；生成产物不代表科学突破或已完成模型训练。参考运行时、框架支持和实验限制见 `references/executable-design-loop.md`。结构检查通过不等于泛化、GPU 性能或新架构优越性得到证明。

真实论文评测只在仓库保留配置与方法；原始论文、第三方源码、历史输出和人工待审材料不包含在源码包中，不能据此报告人工金标准分数。

## 许可证

见 `LICENSE`。
