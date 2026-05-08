# mining.py 老路径 vs Claude Agent SDK：单章节 A/B 对比

> v0.17-C subagent · 2026-05-08
>
> **对比目标章节**：交底书第一节「一、背景技术」（mining.py 中 `build_sections()` 返回的第 1 个 dict）
>
> **对比代码位置**：
> - 老路径：`backend/app/mining.py` `build_sections()` 第 1 个元素
> - 新路径：`backend/app/agent_section_demo.py` `mine_section_via_agent("prior_art", ctx)`
>
> **统一输入 ctx**（见 `backend/test_agent_section.py`）：
> ```python
> {
>     "title": "基于区块链的供应链溯源轻量化方案",
>     "domain": "区块链",
>     "description": "针对供应链溯源场景中传统区块链 TPS 低、节点资源占用高的问题，"
>                    "提出一种结合轻量化签名与边缘节点筛序的混合共识机制，"
>                    "在保持公开可验证性的同时把单节点存储降低 60% 以上。",
>     "intake": {"stage": "prototype"},
> }
> ```
>
> **运行时配置**：`use_real_llm=False` / `use_real_zhihuiya=False` → mock 路径；
> 两侧均无真 LLM 出文，对比聚焦在 **结构 / 控制流 / 工具组合 / 事件协议 / 工程成本**。

---

## Section A · 老路径输出（mining.py）

**调用链**：`mining.build_sections(ctx) → list[dict]`，取第 0 项。

**外部 API 调用次数**：**0**（模板生成阶段只埋 `[LLM_INJECT::xxx]` 占位；后续 `chat.py` SSE
流式阶段才会按占位回填，且回填路径是直调 `llm.stream_chat`，不调智慧芽）。

**产出文件名**：`01-背景技术.md`（phase=`auto`，43 行）

**实际 markdown 摘录**：

```markdown
# 一、背景技术

> **PGTree 节点目标**：客观铺陈技术领域全景与最相近的现有方案，**不贬损**、不下结论；
> 为第二节"缺点"和第三节"问题"做事实铺垫。

## 1.1 技术领域定位
- **本案领域**：区块链
- **细分赛道**：<!-- [LLM_INJECT::subdomain::结合标题《基于区块链的供应链溯源轻量化方案》与 description，给出 1 句话细分赛道定位（≤30 字）] -->
- **典型应用场景**：<!-- [LLM_INJECT::scenarios::列举 3 个典型应用场景，bullet 形式] -->

## 1.2 你报门时的描述（原文）
> 针对供应链溯源场景中传统区块链 TPS 低、节点资源占用高的问题，...

## 1.3 与本发明最相近的现有技术（拟检索 3-5 篇）
**检索种子词**：<!-- [LLM_INJECT::search_seeds::从 description 抽取 5-8 个英文检索关键词（含同义词），逗号分隔] -->

| # | 标题 / 出处 | 公开年 | 核心技术手段 | 与本案差距 |
|---|---|---|---|---|
| A | <!-- [LLM_INJECT::prior_art_a_title::占位 1，等检索回填] --> | — | — | — |
...

## 1.4 现有技术整体演进脉络（≤120 字）
<!-- [LLM_INJECT::prior_art_evolution::用 1 段话讲清楚：早期方案 → 主流方案 → 当前 SOTA 的演进，最后落到本案要改进的位置] -->

---
<details>
<summary>🔍 Examiner 自检（背景技术）— 点开查看 6 维度</summary>
... 6 维度自检表 ...
</details>
```

**特征**：

- 输出是「**带占位的骨架**」，不是「带数据的成品」。
- 表格框/小节顺序/Examiner 自检 全部由 Python f-string 写死。
- 跑 1 次 `build_sections` 完成全部 7 节模板，**0 次** 智慧芽 / Anthropic 调用。
- 真正的「字面内容」在后续 `chat.py` 流式阶段按 `LLM_INJECT` 标记逐个替换；
  替换顺序是写死的（按出现位置），LLM 看不到全局，无法决定「先查哪条数据再写哪段」。

---

## Section B · agent 路径输出（agent_section_demo.py）

**调用链**：`mine_section_via_agent("prior_art", ctx) → AsyncIterator[dict]`

**事件流（`backend/storage/_compare_v017c/agent_events.json`，14 条）**：

| # | type | 关键字段 |
|---|---|---|
| 1 | thinking | "准备为「基于区块链的供应链溯源轻量化方案」生成背景技术…" |
| 2 | tool_use | name=`search_patents` input=`{"query": "TAC: (区块链 AND 供应链)"}` |
| 3 | tool_result | `命中 2458 件` |
| 4 | tool_use | name=`applicant_ranking` input=`{"query": "...", "n": 5}` |
| 5 | tool_result | `top 申请人：[IBM:312, 阿里:278, 腾讯:201]` |
| 6-13 | delta | 8 段 markdown chunk（流式拼接） |
| 14 | done | `stop_reason=mock_complete, tool_calls=2` |

**外部 API 调用次数**：**2**（mock 中尝试 `query_search_count`，无 token 时降级；真 SDK
下还可能调 `patent_trends`，由 LLM 自主决定）。

**拼接后的最终 markdown（30 行）**：

```markdown
# 一、背景技术

## 1.1 技术领域定位
- **本案领域**：区块链
- **细分赛道**：基于区块链的供应链溯源轻量化方案（基于用户描述判定）
- **典型应用场景**：
  - 跨企业供应链溯源
  - 食品/药品冷链合规
  - 跨境贸易单据存证

## 1.2 报门描述原文
> 针对供应链溯源场景中传统区块链 TPS 低、节点资源占用高的问题，...

## 1.3 最相近的现有技术（基于智慧芽实时检索）
- 检索式 `TAC: (区块链 AND 供应链)` 命中 **2458** 件，赛道处于活跃期。
- 头部申请人：IBM（312 件）、阿里巴巴（278 件）、腾讯（201 件）。
- 候选对照专利由命中集排序后人工筛选 3-5 篇填入下表：

| # | 标题 / 出处 | 公开年 | 核心手段 | 与本案差距 |
|---|---|---|---|---|
| A | （由代理人在命中集中筛选） | — | — | — |
...

## 1.4 演进脉络
早期方案多依赖中心化数据库做溯源；主流方案转向联盟链 + 智能合约；当前 SOTA
向跨链零知识压缩演进。本案在【SOTA 之后/之外】进一步优化吞吐与隐私。
```

**特征**：

- 输出是「**带数据的成品**」（仅候选专利标题需人工筛选）。
- LLM 自主决定调几次工具、查什么、怎么把数字写进 1.3 段。
- 工具调用顺序由 LLM 推理产生：先 `search_patents` 看赛道热度 → 看到 2458 件命中后，
  推断"红海"再追查 `applicant_ranking` 拿头部玩家。这条决策链在老路径里要写 if/else。

---

## Section C · 多维对比表（11 维）

| # | 维度 | mining.py 老路径 | agent SDK 新路径 |
|---|---|---|---|
| 1 | **控制流** | 串行手写 f-string，每节顺序固定 | LLM 自驱 think→tool→reflect→tool→write loop |
| 2 | **改 prompt 成本** | 改 Python 源码 → 重启服务 → 影响所有项目 | 改 `_SECTION_PROMPTS[section]` 字符串，可 A/B by tag |
| 3 | **加新工具成本** | 改 mining.py 流水线 + 加 chat.py 处理分支 | 加一个 `@tool` 装饰函数，立即被 LLM 看到 |
| 4 | **工具组合策略** | 写死顺序：`build_sections → chat.py 顺序回填 LLM_INJECT` | LLM 看到中间结果决定下一步（命中多 → 查 top 申请人；命中少 → 改检索式） |
| 5 | **错误恢复** | `try/except` 在 zhihuiya.py 写死降级到 fallback | LLM 看到 `tool_result.isError=True` 可自行换检索式或换工具 |
| 6 | **token 成本** | 1 次模板生成 0 token + N 次 LLM_INJECT 替换（每位 1 次小调用） | 1-2 次 multi-turn assistant，每次都带历史；估 2-5× 老路径 |
| 7 | **延迟** | 模板秒出；LLM_INJECT 串行替换 → 用户感知"逐位填空" | 全程流式 SSE，但首字延迟更高（要先调工具再写） |
| 8 | **可调试性** | `print` / 日志看每个 LLM_INJECT 替换前后的字符串 | 标准化事件流（thinking/tool_use/tool_result/delta），前端直接渲染时间线 |
| 9 | **可测试性** | 单测：mock `llm.stream_chat`，断言模板字面量 | 单测：mock `claude_agent_sdk.query`，断言事件序列 + 工具调用次数 |
| 10 | **结构稳定性** | 极强（f-string 强约束，永远 6 个小节 + Examiner） | 弱~中（取决于 system_prompt 约束力，可能漏小节） |
| 11 | **数据真实性** | 占位待人工/二次 LLM 填，容易出"看似数据但其实没查"的情况 | 数字从工具调用结果里来，可追溯到具体 API 命中量 |

补充维度（备选）：

| 维度 | mining.py | agent SDK |
|---|---|---|
| 多模型支持 | 改 `llm.stream_chat` 一处 | `ClaudeAgentOptions(model=...)` 一处，且 SDK 自带 model fallback |
| 离线/降级 | 模板永远能出 | 必须 mock 整套事件流；老路径降级更优雅 |
| 并发安全 | f-string 纯函数，天然并发 | per-section 一个 query loop，多 section 并行需独立 MCP server 实例 |

---

## Section D · 推荐策略

### 适合迁 agent SDK 的章节

1. **背景技术（本次对比章节）**：天然需要查命中量 + 趋势 + 申请人，工具组合是核心价值；
   LLM 看到中间数据动态调整检索式优于写死顺序。
2. **现有技术缺点（02）**：5-Why 钻取本身就是多轮推理，每个 Why 的"答"可以由
   `search_patents("baseline+某根因")` 反查印证。
3. **优点 / 效果矩阵（06）**：要做手段×维度对账，需要交叉调用 `most_cited` /
   `applicant_ranking` 找对标 baseline。
4. **未来：自动 OA 答辩**：审查员引证 D1+D2 → agent 主动跑 `simple_legal_status` 看法律状态、
   跑 `patent_trends` 看 D1 引证后是否被规避，写答辩稿。

### 保留 mining.py 模板的章节

1. **技术问题陈述（03）**：强结构、低自由度，f-string 模板效率最高，LLM 反而可能
   破坏「核心 / 附带 / 不解决什么」的三段式约束。
2. **关键点与三档独权（05）**：CN 实务有铁律（强/中/弱档 + 5/7/9 特征数），写死最稳。
3. **问题清单（07/08/09）**：纯静态文案，不需要任何工具与 LLM。

### 渐进迁移路径（每周 1 章节）

| 周 | 迁移目标 | 切流策略 | 回滚阈值 |
|---|---|---|---|
| W1（本周） | 01-背景技术：上 agent_section_demo.py mock 路径 | 灰度 5% 项目 | 用户投诉 / mock 异常 |
| W2 | 配 ANTHROPIC_API_KEY，01 章节 50% 项目走真 SDK | 监控成本 / 时长 | 成本 > 老路径 5× |
| W3 | 02-缺点 5-Why 章节迁 agent | 50% | 同上 |
| W4 | 06-优点矩阵迁 agent | 50% | 同上 |
| W5+ | 03/05/07-09 评估，原则上保留模板 | — | — |

迁移期间双路径并存（feature flag `PP_USE_AGENT_SECTION=01,02,06`），便于
任何 section 出问题都能秒级回退。

---

## 附：A/B 对比附件

- 老路径完整 markdown：`backend/storage/_compare_v017c/old.md`（43 行）
- agent 路径完整 markdown：`backend/storage/_compare_v017c/agent.md`（30 行）
- agent 事件流原始 JSON：`backend/storage/_compare_v017c/agent_events.json`（14 条事件）
- 复跑命令：`python3 -m backend.test_agent_section`
