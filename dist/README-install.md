# arch-anatomy skill 分发

可直接复制到 `.codex/skills/arch-anatomy/` 的目录：`dist/arch-anatomy/`

可分发压缩包：`dist/arch-anatomy-codex-skill.zip`

安装方式：

```powershell
Expand-Archive .\dist\arch-anatomy-codex-skill.zip $env:USERPROFILE\.codex\skills
```

解压后必须存在：

```text
.codex/skills/arch-anatomy/SKILL.md
.codex/skills/arch-anatomy/scripts/
.codex/skills/arch-anatomy/references/
.codex/skills/arch-anatomy/assets/
```

包不包含论文运行目录、workspace、旧版本归档、私钥或临时缓存。
