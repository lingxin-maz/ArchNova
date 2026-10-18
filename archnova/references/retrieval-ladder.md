# 检索阶梯（Retrieval Ladder）

用途：补齐部件缺失证据、建立下游问题谱系、扫描前沿工作。所有检索都必须**可核查**——记录查询、端点、命中与失败原因。本文件优先保证「在本机真能跑」，而不是「理论上最好」。

---

## 1. 工具矩阵（本机实测状态）

| 工具 | 状态 | 用途 | 备注 |
|---|---|---|---|
| `search_arxiv` | ✅ 免费可用 | 按标题/关键词/分类检索 | 支持 `ti:` `au:` `cat:` 语法与日期过滤 |
| `read_arxiv_paper` | ✅ 免费 | 取 arXiv 全文（分片） | 长文用 `offset`/`max_chars` 续读 |
| `download_arxiv` | ✅ 免费 | 拿摘要页与 PDF 直链 | 不返回正文 |
| `read_by_doi` / `download_by_doi` | ✅ 免费 | 任意 DOI 取全文 | 付费墙需机构网络 |
| `web_fetch` | ✅ | 抓任意页面/API | 做 API 查询的主力 |
| `web_search` | ✅ | 兜底发现 | 结果需交叉核验 |
| `scripts/literature.py` | ✅ 内置 | OpenAlex / S2 / Crossref 封装 | 见 §3 |
| `search_papers` / `search_semantic` / `search_pubmed` / `search_biorxiv` 等 AI4Scholar 工具 | ⚠️ **本机未配 API key，调用直接报错** | — | **不要写进主路径**。除非确定已配置 `AI4SCHOLAR_API_KEY`，否则一律走上面的免费组合 |
| `get_pubmed_*` / `get_semantic_*` | ⚠️ 同上 | — | 同上 |

**规则**：技能的流程不得依赖可能不可用的工具。若探测到 AI4Scholar 可用（一次 `get_ai4scholar_credits` 成功即证明），可把它作为**加速层**叠加；不可用时主路径必须完整。

---

## 2. 三类检索的目标不同

| 检索 | 问的问题 | 合格标准 |
|---|---|---|
| 上游（被引） | 这个部件的原始思想从哪来？论文没说清的细节在哪篇里说清了？ | 每篇上游必须对应**一个具体槽位**，不允许「相关文献」凑数 |
| 下游（引用） | 别人解决了它的什么问题？又制造了什么新问题？ | 必须写出 `problem → mechanism → new_problem` 三元组 |
| 前沿 | 当前最强的做法是什么？谁在同一条思路上推进？ | 必须能落回某个槽位或某条成本主项 |

---

## 3. API 配方（已实测通过）

### 3.1 OpenAlex（主力：免费、无需 key、支持引用图双向）

**按标题定位（拿 work id）**

```bash
curl -s "https://api.openalex.org/works?filter=title.search:attention%20is%20all%20you%20need&per-page=3&select=id,title,publication_year,cited_by_count,doi"
```

**上游：它引用了谁**

```bash
# 第一步：取 referenced_works 列表
curl -s "https://api.openalex.org/works/W2626778328?select=id,title,referenced_works"
# 第二步：批量取详情（一次最多 50 个 id，用 | 分隔）
curl -s "https://api.openalex.org/works?filter=ids.openalex:W1|W2|W3&per-page=50&select=id,title,publication_year,doi,cited_by_count"
```

**下游：谁引用了它（按被引次数降序）**

```bash
curl -s "https://api.openalex.org/works?filter=cites:W2626778328&sort=cited_by_count:desc&per-page=25&select=id,title,publication_year,cited_by_count,doi,abstract_inverted_index"
```

**按关键词/CONCEPT 搜**

```bash
curl -s "https://api.openalex.org/works?search=state%20space%20model%20long%20context&per-page=10&select=id,title,publication_year,cited_by_count"
```

> ⚠️ **配额**：无 key 时按 IP 共享免费日额度。因此：`per-page` 控制在 25 以内、用 `select` 只取需要的字段、**把结果落盘缓存**（`literature.py` 默认写 `.cache/`），同一查询不要重复打。若返回 403/429 或额度提示，转 S2 → Crossref → `web_search`。

### 3.2 Semantic Scholar（补充：有 citation context，但常 429）

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:1706.03762/citations?fields=title,year,externalIds,contexts,intents&limit=20"
curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:1706.03762/references?fields=title,year,externalIds&limit=20"
```

价值最高的字段是 `contexts`（引用它的原句）与 `intents`（背景/方法/结果）——**下游分析里「它解决了什么问题」最好用引用原句当证据**，而不是自己概括。

**429 处理**：退避 2s → 5s → 10s，三次失败即放弃并转 OpenAlex；记入 `gaps`。

### 3.3 Crossref（保底：元数据权威）

```bash
curl -s "https://api.crossref.org/works?query.bibliographic=deep%20operator%20network&rows=5&select=title,DOI,published,author"
```

用途：只用来**校正 DOI 与年份**，不用来发现论文（它的相关性排序较差）。

### 3.4 arXiv（预印本与最新工作）

```bash
# 按 id 批量核验标题（防止编号编造）
curl -s "http://export.arxiv.org/api/query?id_list=2312.00752,2010.08895&max_results=2"
# 按关键词找最新
curl -s "http://export.arxiv.org/api/query?search_query=all:%22neural%20operator%22&sortBy=submittedDate&sortOrder=descending&max_results=10"
```

**核验纪律**：报告里每个 arXiv id / DOI 在发布前都必须被解析过一次且标题匹配。`scripts/check_anatomy.py --verify-refs` 会强制执行。

---

## 4. 上游补齐：先定位缺口，再定向检索

不要「搜一下相关文献」。正确顺序：

1. 在部件表里找 `M` 项，写出**缺的到底是什么**：
   - 缺机制（「不知道路由是否可微」）
   - 缺数值（「不知道 λ」）
   - 缺定义（「不知道 Δ 的离散化方式」）
   - 缺动机（「不知道为什么这么设计」）
2. 按缺口类型选检索词：
   | 缺口 | 检索策略 |
   |---|---|
   | 缺机制/定义 | 在该文 `referenced_works` 里找标题含相关术语的；再 `search_arxiv` 该术语的原始论文 |
   | 缺数值/超参 | 优先找**官方代码仓库**（`web_search "<模型名> github"`）或后续复现论文的附录；代码不是论文事实，标 `U` 并在 note 注明「来自官方实现」 |
   | 缺动机 | 找该文引用的、提出该思想的原始论文，读其 motivation 段 |
3. 每补上一个缺口，在 `upstream` 里写清 `fills_gap`（对应哪个 part id 与哪个缺口）。
4. 一篇上游只算数一次。不要把同一篇论文列三行来凑数量。

### 判定「补齐成功」的标准

补上的证据必须**直接回答**该缺口，而不是「相关」。例如缺口是「λ 的数值」，那么上游给出了 λ=1.0 才算补齐；上游只是也用了一个加权损失，不算。

---

## 5. 下游分析：建立问题谱系，而不是罗列

下游论文不是「后来者」，而是「对本文缺陷的回应」。对每篇下游记录三元组：

```
addressed_problem: 它认为前作有什么问题（用引用原句或摘要原句）
mechanism:        它用什么改动解决（落到具体槽位，如「把 D2 的 softmax 换成核特征映射」）
new_problem:      它引入了什么新代价/新失效模式
```

`new_problem` 是最有价值的一栏，也是多数综述缺失的一栏。判据：如果这个改动被采用，**下一个研究者会立刻遇到什么麻烦**？

示例形态（不是真实论文，仅示意结构）：
- 用线性注意力换掉 softmax → 解决了 O(N²)，但引入「无 softmax 归一化导致注意力弥散、长程检索精度下降」→ 新问题：如何恢复尖锐度（后续工作用 gating / 局部窗口混合）。
- 用 SSM 换掉注意力 → 解决了线性时间，但引入「状态容量有限、精确检索能力弱」→ 新问题：混合架构（attention + SSM 并联）。

### 数量与质量

- 至少 3 篇下游，且**彼此不能是同一改进路线**（否则说明你只找到一脉）。
- 优先选被引高 + 时间跨度大（早期响应 vs 近期修正）的组合。
- 若某篇下游只有引用没有摘要，标 `M` 并说明。

---

## 6. 前沿扫描

目标不是「列出大厂论文」，而是**找到与当前架构同一槽位上的最强替代品**。

检索顺序：

1. 用槽位术语而非论文名检索：例如槽位是 M1（交互范围），就搜 `linear attention`、`sparse attention`、`state space model`、`hybrid attention`；槽位是 R5（条件注入），就搜 `conditional neural operator`、`multi-fidelity neural network`。
2. 按机构过滤：`web_search "<术语> site:arxiv.org <机构名>"`，或用 `search_arxiv` 的 `au:` 字段搜该团队常见作者。
3. 关注**技术报告**（Technical Report）而非只有会议论文——DeepSeek-V3 (arXiv:2412.19437)、DeepSeek-V2 (arXiv:2405.04434) 这类报告的架构细节密度高。
4. 每篇前沿工作必须回答：「它在哪个槽位上更好？代价是什么？」回答不了就不写。

**常见前沿团队与其关注点**（用于检索关键词，不是用于凑引用）：DeepSeek（MoE 路由、MLA、FP8）、Moonshot/Kimi（长上下文、Muon 优化器）、Qwen（GQA、长序列）、OpenAI（推理时计算、稀疏）、DeepMind（神经算子、谱方法、算子理论）、Meta FAIR（SSM、长上下文）。

---

## 7. 失败记录格式

检索不到时必须写进 `gaps`，包含：

```json
{"item": "λ 的具体数值", "queries": ["PI-DeepONet lambda loss weighting"],
 "endpoints": ["openalex:title.search", "arxiv:all", "web_search"],
 "reason": "论文正文未给；官方仓库未公开；复现论文只提到『加权求和』未给数值",
 "alternative": "按可配置标量实现，默认 1.0，并在实验中做 λ∈{0.1,1,10} 敏感性分析"}
```

**不允许**的写法：「未找到相关文献」（太笼统，无法复核）。

---

## 8. 成本控制

一次完整的深度解剖大约需要 15–30 次 API 调用。控制方式：

- 所有 `literature.py` 查询默认落盘 `.cache/<hash>.json`，同一查询 24h 内不重复请求；
- OpenAlex 一律带 `select=`，把响应压到最小；
- 先标题检索拿 id，再批量取详情（`ids.openalex:` 一次最多 50 个）；
- 下游只取前 25 篇按被引排序，够用；
- 全文只用 `read_arxiv_paper` 读**需要的分片**，不要一次拉全文。
