# archnova v2.5 修改与验证说明

唯一契约源是 ontology.json。v2.5 增加证明依赖 DAG、接口/状态审查上下文、实现探索覆盖、本地适配实验、审查质量评测、主动反证检索、数学目标绑定、原始响应回放和两种发布模式。Python 3.7+ 与 jsonschema 执行 Draft 4 schema、关系、累积摘要、证据快照、受限数值、语义审查与报告一致性检查。旧版本先 migrate，再补齐，禁止静默升级为已验证结果。

## 研究产物执行路径

1. 从 assets/anatomy.skeleton.json 建立草稿，填写实际来源、claims、数据流、成本、提案、指标与证明材料。空骨架预期失败。
2. 保存原始文件和 UTF-8 提取文本；evidence_snapshots 登记哈希、来源版本和提取工具。引文 span 是 Unicode 半开区间 [start,end)。校验会读取文件并重算 SHA-256、逐字核对 quote。
3. 依据自己的架构判断执行 GitHub 机制检索与源码适配审查，见 repository-discovery.md；评审结果放 repository_discoveries。没有相关实现是合法结果。
4. 为定理、推导和行为/实现等价填写 proof_outline，列出陈述、定义域、量词、假设、逐步推理和 premise_ids。theory 和 swap 必须有稳定且全局唯一的 id。
5. 用 semantic_review.py prepare 导出材料；宿主 AI 逐项审阅，apply 回填，见 semantic-review.md。只有有材料且无未决义务才允许 supported。实际反例不能被正面模型判断覆盖。
6. 处理 blocking_items 后运行 checkpoint_anatomy.py，生成严格本地校验通过的 G0–G8 摘要。摘要只检测陈旧，不是签名或真实执行证明。审查 apply 保留已有阻塞项。
7. render_report.py 从 JSON 确定性生成报告，check_anatomy.py --strict --report 核对全部投影；兼容 CRLF/LF。
8. honest_report 模式允许 open/conditional/rejected/insufficient，但每条结论必须有 disposition；endorsed 只能对应 supported。supported_conclusions 模式全部结论必须 endorsed+supported。两种模式都要求证明无环、提案实现探索有记录、实验收据一致，并联网解析引用。

## 本地验收

从技能目录运行：

```bash
python scripts/build_ontology.py --check
python -B -m unittest discover -s tests -v
python scripts/render_report.py assets/anatomy.fixture.json -o ../archnova-workspace/fixture-report.md
python scripts/check_anatomy.py assets/anatomy.fixture.json --strict --report ../archnova-workspace/fixture-report.md
python scripts/build_package.py
```

合成 fixture 的 release 必须失败。发布网络分支测试使用明确标注的 test-only 模型响应与远程元数据 stub；它测试程序契约，不能当作科学证明或联网验证。

## 能力边界

- 引文：AI 比较实际引文上下文与断言的范围、量词、条件和因果强度；记录 supported/partial/contradicted/insufficient。输入哈希失配会拒绝旧审查。模型可能判断错误，不保证事实绝对正确。
- 数学：AI 审查定理及行为等价的假设、定义域、逐步推理和前提。proof_checks.py 对有理表达式使用精确分数与多项式交叉乘法，保留非零分母条件并找精确反例；不处理一般定理、神经网络完整函数等价或浮点实现误差。
- GitHub：按 AI 判断检索，保存查询、响应哈希、commit、源码与行号；AI 给出适配结论。有限文件抓取可能遗漏关键实现。代码没有自动运行，速度、精度或训练效果尚需实验。
- 数值：受限 AST 求值、单位一致性和结构化决策规则，不等于实验真正执行或统计因果结论成立。
- 实验与研究：本工具不保证新架构优于基线、置信区间计算正确或真实实验发生。

## 迁移与打包

migrate_anatomy.py 支持无版本 v1、2.0.0、2.1.0、2.2.0、2.3.0、2.4.0、2.5.0，输出 blocked 当前草稿；不编造证据、证明、语义判断或实现适配。旧 benchmark 分数不作为本版效果证明。build_package.py 生成可复现 .skill 和逐文件 SHA-256 清单。

## 质量评测

review_evaluation.py 将答案键与盲测任务分离，拒绝缺案例、旧 hash 和不完整运行。保存 exact accuracy、unsafe acceptance、false rejection、abstention、appropriate abstention、repeat agreement 及各自分母。合成评测只说明流程和已知案例，不估计真实学术判断准确率。

## v2.5 可靠性门

详见 reliability-workflows.md：模型评测保留随机任务、提示词和原始判断，模拟不计为模型准确率；实验收据从 raw_json 与观测重算；数学检查必须绑定实际 formal_statement；proposal 与 endorsed 结论必须执行主动反证检索，所有相反候选显式处理后才可背书。


## 本地论文导入

对 PDF 或本地全文先运行 `scripts/ingest_document.py`。它把原文件和 UTF-8 提取文本复制到 bundle 内，生成可移植的 `original_path/text_path`、双 SHA-256 和提取时间；草稿的 `evidence_snapshots[]` 应直接使用该 receipt。原文件不在 bundle 内时 checker 会拒绝，避免报告依赖机器上的偶然路径。

```bash
python scripts/ingest_document.py --original paper.pdf --bundle run --source-id source:paper --snapshot-id snapshot:paper --source-version v1 --retrieved-at 2026-10-17T15:30:00+08:00 --output run/snapshot.json
```
