# arch-anatomy

Arch Anatomy 是一个面向论文和代码项目的可验证架构分析 skill。它支持论文材料导入、代码项目索引、多模态图像任务、多 Agent 调度、引文支撑检查、数学目标绑定、GitHub 实现检索、主动反证检索、实验收据回放和发布门检查。

## 安装到 Codex

解压 `dist/arch-anatomy-codex-skill.zip` 到 `%USERPROFILE%\\.codex\\skills`，得到：

```text
.codex/skills/arch-anatomy/SKILL.md
```

也可以直接复制 `dist/arch-anatomy/` 到 `.codex/skills/arch-anatomy/`。

## 开发验证

```powershell
python -B -m unittest discover -s arch-anatomy/tests -p 'test*.py'
python arch-anatomy/scripts/build_ontology.py --check
python C:/Users/mazjz/.codex/skills/.system/skill-creator/scripts/quick_validate.py arch-anatomy
```

当前 skill 源码位于 `arch-anatomy/`；可安装分发物位于 `dist/`。
