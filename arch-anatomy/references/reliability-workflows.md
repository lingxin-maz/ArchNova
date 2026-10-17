# v2.5：评测、回放、数学目标和反证

## 有来源记录的模型评测

训练/调试用案例、答案键、模拟数据和模型响应必须分开。每次 prepare 用随机 opaque ID 和随机顺序，避免 scope_universal 等案例名泄漏标签；推理请求不包含答案键或 ID 映射。输入、提示词和会话均绑定哈希。已经见过案例或答案的宿主必须标 prior-exposure=known；未知填 unknown，不能声称独立盲测。

```bash
python scripts/review_evaluation.py prepare assets/review-eval/cases.json --key-output PRIVATE/session-key.json -o session.json
# 宿主只读 session.json，逐项判断后写 {"responses":[{case_id,input_hash,verdict,rationale},...]}。
python scripts/review_evaluation.py collect assets/review-eval/cases.json --session session.json --key PRIVATE/session-key.json --responses host-responses.json --identity HOST --model MODEL --run-id run-1 --prior-exposure known -o host-run.json
python scripts/review_evaluation.py score assets/review-eval/cases.json --gold assets/review-eval/gold.json --predictions host-run.json -o score.json
```

支持 --simulation，显式把合成响应标成模拟。旧的无来源 predictions[] 也只能作为 scorer_diagnostics；顶层模型准确率置 null。真实端点用 run --endpoint --model --run-id --prior-exposure；端点不接收 gold/key，响应必须原样回传当前任务 ID 和 hash，不能由程序替错模型的响应。保留请求对象和模型原始 JSON 响应对象、哈希、模型身份及已知暴露状态。

多轮评测以 {"runs":[run1,run2,...]} 汇总，run_id 不重复，所有轮次完整覆盖。单轮 repeat_agreement 为 null。当前内置 14 例为调试/诊断集，开发者已经接触过其标签；任何测试通过或宿主高分都不能估计真实论文审查准确率。声明与哈希不能鉴证模型确实独立运行，外部可信 runner 或全新独立数据集仍可提高证据强度。

## 实验原始响应回放

实验执行保存每个 case/repetition 的原始 UTF-8 raw_json、SHA-256 和解析值。验证时重读 raw_json，核对哈希/解析值，检查 case/repetition 不重复、不遗漏，再重算全部 outputs/state/gradients 的误差和阈值。不信任存储的 passed 或 errors；伪造正面状态但数值不匹配会失败。

```bash
python scripts/experiment_runner.py assets/experiment-example/spec.json --execute -o run.json
python scripts/experiment_runner.py run.json --replay -o replay.json
```

replay 不执行任何代码。加入 implementation_experiments 的收据还会绑定实际 proposal、接口、adapter 及依赖文件哈希。旧收据没有原始响应必须重跑。有限样本、手写 adapter 或梯度近似不证明全域等价，保存的原始响应也不能防止恶意伪造整个运行历史。

## 数学检查对应真正的目标

对采用精确检查的 theory、derivation claim 或 swap，显式登记 formal_statement：natural_statement 必须逐字对应目标 statement（claim 则为 predicate+空格+object）；semantics=real_scalar、quantifier=forall、relation=equals；variables 列 symbol/meaning/type，nonzero 列明域限制，lhs/rhs 写机器表达式。

mathematical_checks.case 必须与 formal_statement 的变量顺序、符号、类型、非零条件与运算 AST 一致；x=x 不能绑定 x+x=2*x，额外假设 x!=0 也不能悄悄缩窄一个原本没有该条件的目标。当前绑定是有界实标量有理表达式的精确对应，不声称翻译一般数学语言、矩阵、PDE 或浮点程序。

```bash
python scripts/math_binding.py anatomy.draft.json --check-id check:my-equation -o anatomy.bound.json
python scripts/semantic_review.py prepare anatomy.bound.json -o tasks.json
```

每个绑定检查还生成 formalization:...:target/variables/domain/operators 义务。宿主 AI 必须确认自然语言、符号含义和实际架构相符；机器语法对应不能替代这一语义判断。陈述/域/映射改变后旧绑定与审查失效。未绑定检查不会被拿来证明或反驳任意目标，主 checker 会拒绝。

## 主动寻找相反与边界证据

从最容易失败的假设、数据条件、反例或复现问题构造 1..4 个具体查询，intent=limitation/failure/contradiction/replication；支持 Crossref 与 arXiv 的有界只读 API。不得把网络错误或无结果当作反证不存在。

```bash
python scripts/counterevidence.py search anatomy.draft.json --plan counter-plan.json --limit 3 -o counter-search.json
# plan = {target_id,rationale,queries:[{provider:"arxiv",intent:"limitation",query:"..."}]}
```

脚本保存 query/endpoint、原始 API 响应与哈希，再从响应重建 candidates。元数据命中只是线索。宿主必须逐个分类 supporting/opposing/limiting/irrelevant/unresolved 并说明理由；不得漏掉不利候选。前三种科学分类必须保存该 candidate 的原始来源、提取文本、逐字 quote/span/hash 并登记 sources/evidence_snapshots；不能只用标题认定反驳。摘要可以证明其明确写出的范围限制，不能冒充全文定理或完整实验核验。

review 格式：{search_hash,reviewer:{identity,model},reviewed_at,assessments:[{candidate_id,classification,rationale,evidence:[{source_id,snapshot_id,quote,span,content_hash,locator,retrieved_at}]}]}。

```bash
python scripts/counterevidence.py apply anatomy.draft.json --search counter-search.json --review counter-review.json -o anatomy.counter.json
```

apply 后重新 prepare 语义任务，实际的 opposing/limiting 引文会进入 payload 和专门义务；supported 必须引用并解释它们。候选未审/未解决会阻止背书。每个保留 proposal 与 endorsed 结论都要有检索记录；背书还要求至少一次完成的检索。网络受阻可如实发布 open/conditional，但不能假装已经解决相反材料。检索或评审内容变化使旧语义任务 hash 失效。
