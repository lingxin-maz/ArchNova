# 可选工具环境与维护测试

复制 skill 目录即可让宿主 Agent 使用 ArchNova。本文仅适用于需要运行辅助脚本或维护代码的人，不是普通技能使用者的安装步骤。

## 什么时候需要环境

- 论文/代码阅读、架构设计、模型诊断、训练策略与实验计划：使用宿主 Agent，无需 Python 依赖。
- 机械 JSON/schema 校验、参考 IR、有限训练、回放：按所选脚本需要 Python 和 jsonschema。
- 显式 PyTorch tracing：还需要兼容 PyTorch；JAX/CUDA 能力以具体后端实现为准，不自动承诺支持。
- 真实训练、GPU 延迟/显存：需要对应数据、框架、设备与实际收据。

Agent 先检查现有环境。缺依赖时继续可完成的分析/设计，将受影响执行步骤标记 unavailable；只有用户要求启用工具环境时才安装。不能把人工式核对称为机器验证，不能跳过正式发布门却声称通过。

## 仅维护者或启用工具时安装

从源码仓库根目录执行：

```shell
python -m pip install -r archnova/requirements.txt
python -B -m unittest discover -s archnova/tests
python archnova/scripts/build_ontology.py --check
python archnova/scripts/capability_audit.py archnova
python archnova/scripts/build_codex_skill.py
```

从已安装 skill 根目录运行脚本时路径不带 archnova/ 前缀。详细严格执行协议见 `optional-tool-workflow.md`。
