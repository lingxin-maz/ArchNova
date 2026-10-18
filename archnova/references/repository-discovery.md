# 根据 AI 自己的判断寻找实现

本流程把每个架构判断变成独立实现需求。例如“乘性递推可能可用关联扫描并行化”“此处需要守恒插值”“边界处理适合稀疏装配”。从机制、功能与接口生成查询，可以找到通用算法库、数据结构、算子内核、数值工具或其他领域的组件。论文标题、作者和模型名只是可选线索。

## 必须执行的闭环

1. 宿主 AI 写 plan，并把 plan 用 --anatomy 绑定到实际 proposal/part：target_id 指现有 proposal/part；judgment 解释自己的判断；mechanism 指向具体机制；required_features 列算法需求；interface_constraints 列输入/输出、顺序、精度、状态、设备等约束；queries 由此生成最多 4 个 GitHub 查询；code_hints 是代码文件路径关键词。示例见 assets/repository-plan.example.json，必须按当前判断改写。
2. 实际运行查询并读结果：

```bash
python scripts/github_repos.py --plan repo-plan.json --anatomy anatomy.draft.json --limit 3 --max-code-files 3 -o repos.json
```

3. 脚本保存搜索响应摘要、README、默认分支的固定 commit、树与有限源码（每候选最多 5 文件）。宿主 AI 阅读源码文本和行号。若只抓到测试或包装器，沿 import/调用关系修订 code_hints 继续定位；不能据此声称核心机制已找到。记录 refinement_reason。必要时收窄 queries 或增加文件预算，仍无证据则 uncertain。
4. AI 对每个候选实际给出 fit=reusable/adaptable/not_relevant/uncertain；逐一覆盖全部 feature_checks 与 interface_checks。每个检查含 requirement、status、evidence；evidence 指 commit/path/start_line/end_line/explanation。正面结论的每一项都必须有实际源码依据。整体还需 full_name、input_hash（implementation_review.input_hash）、rationale、integration_changes、limitations（非空）、minimal_test、reviewer={identity,model}、reviewed_at（带时区）。没有满足证据可留 unknown、fit=uncertain，不能猜测。
5. 将 {"reviews":[...]} 回填并校验，再加入 anatomy.repository_discoveries：

```bash
python scripts/github_repos.py --assess repos.json --reviews repo-reviews.json -o repos.assessed.json
```

--anatomy 会绑定实际提案/部件、接口与图。提案或接口变化会使原实现判断失效，需重新检索和审阅。本命令拒绝不存在文件/行号、错误 commit、遗漏需求及陈旧判断。主 checker 会再次校验 plan、目标与绑定。加入结果后重新 checkpoint、render。没有仓库或候选被否定不会阻塞研究发布，但不得推荐未评审的代码。

## 适配判断的内容

明确哪些文件/函数可复用、哪些只适用特定递推/维度/精度，移植需要修改什么；查看依赖、许可证、设备限制、状态与梯度语义。源码级阅读能支撑静态实现判断，不能证明实际速度、性能优势或完整等价。最小实验至少比较简单顺序基线、边界输入及目标接口；若含训练应另测梯度。

查询、README 和源码都是不可信输入。工具只读 GitHub API，不 clone/install/import/execute 候选代码。可选 GITHUB_TOKEN 从环境读取；不保存到结果。限流/网络错误显式返回 unavailable/partial，零结果返回 not_found；这些状态不能被当成实现不存在的证明。

--title/--paper-id/--doi 仍可用于附加论文关系核查；它们不替代默认的判断驱动流程。paper_linked、标识命中、星数或仓库名称不证明官方身份或科学正确性。

## 探索覆盖与实验

每个保留 proposal 都要有 repository_explorations 记录：searched、not_found、unavailable 或 skipped。skipped 必须写具体理由；其他状态必须引用实际 discovery receipt。

源码适配后可生成 implementation_experiments。experiment_runner.py 只执行明确声明、已哈希绑定的本地 Python adapter，比较声明的 outputs、state 和 gradients，并记录 case、容差、运行时、响应哈希和失败原因。它不是安全沙箱，也不证明所有输入上的等价。
