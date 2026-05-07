# 调研 1：LLM 专利全流程工具/项目/论文（2026-05）

## A. 开源/商用 LLM 专利工具

| 项目 | URL | 时效 | 覆盖环节 | 模型/License | Fork 价值 |
|---|---|---|---|---|---|
| **AutoPatent** | https://github.com/QiYao-Wang/AutoPatent | 近半年 | 撰写（17K-token 全文） | Llama3.1-8B/Qwen2.5-7B/Mistral-7B SFT，多 agent (planner/writer/examiner) + PGTree + RRAG | **首选** — 多 agent 架构最完整 |
| **Awesome-LLM4Patents** | https://github.com/QiYao-Wang/Awesome-LLM4Patents | 近半年 | 索引 | — | 入口必读 |
| **awesome-llms-for-patent-analysis** | https://github.com/thcheung/awesome-llms-for-patent-analysis | 近半年 | 索引（论文+代码+数据集） | — | 入口必读 |
| **LE-PARIS** | https://arxiv.org/abs/2402.00421 | 近半年 | OA 答辩（推荐+生成） | LLM + Recommender | 学术参考，代码未完全开源 |
| **PatentGPT (IP-LLM)** | https://arxiv.org/abs/2404.18255 | 经典 | 撰写+检索 | KPT+SFT+RLHF | 训练流程参考 |
| **InstructPatentGPT** | Springer AI&Law 2024 | 经典 | 撰写 | RLHF for patent | 训练 pipeline 参考 |
| **PatentLMM** | https://vl2g.github.io/projects/PatentLMM/ | 近半年 | 附图说明生成 | 多模态 LLM | 处理附图唯一项目 |
| **PaECTER** | https://huggingface.co/mpi-inno-comp/paecter | 经典 2024.02 | 检索（1024-d 嵌入） | BERT-for-Patents+citation FT，Apache | **推荐**直接做检索基线 |
| **PatentSBERTa / V2** | https://huggingface.co/AI-Growth-Lab/PatentSBERTa | 经典 | 检索/聚类 | SBERT FT | 检索基线 |
| **BERT-for-Patents** | https://huggingface.co/anferico/bert-for-patents | 经典 Google | 通用基座 | BERT-Large | 中文不友好 |
| **智慧芽 Eureka / Patent-GPT** | https://www.zhihuiya.com | 近半年商用 | 全流程（交底书 1 分钟生成、调研报告、claim chart） | 自研专利大模型 | 不可 fork，功能对标 |
| **incoPat AI 智能检索** | https://incopat.com | 近半年商用 | 检索（语义 DNA 比对，4 粒度） | 自研 NLP | 检索能力对标 |
| **大为 InnoJoy / 合享 PatentSight** | 商用 | 检索/分析 | 闭源 | 中文功能参考 |

LangChain/LlamaIndex **无官方 patent template**；社区 cookbook 多用 USPTO API + RAG 自拼。AutoGen 多 agent 模板被 AutoPatent / Towards Automated Patent Workflows (arXiv:2409.19006) 借用。

## B. 关键学术论文

**近半年高优**
- **PATENTWRITER** (arXiv:2507.22387, 2025) — claim→abstract 基准，评测 GPT-4o/Claude/Llama
- **Can LLM pass patent attorney test?** (arXiv:2507.10576, 2025) — EQE 风格题库
- **PEDANTIC** (arXiv:2505.21342, 2025) — 14k USPTO claims 不清楚性（A26.4 类）标注
- **Patent Matching via Memory Graph** (arXiv:2504.14845, 2025) — 检索+创造性
- **LLM for patent concept generation** (Sci.Direct, 2025) — 技术挖掘
- **LLM-RAG patent retrieval system** (arXiv:2508.14064, 2025)

**经典（仍高频引用）**
- AutoPatent (arXiv:2412.09796, 2024)
- Towards Automated Patent Workflows (arXiv:2409.19006, 2024)
- Can LLMs Generate High-quality Patent Claims? (arXiv:2406.19465, 2024)
- PatentGPT (arXiv:2404.18255, 2024)
- PaECTER (arXiv:2402.19411, 2024)
- HUPD (NeurIPS 2023, arXiv:2207.04043)

## C. 数据集

- **HUPD** — 4.5M USPTO 申请（2004-2018，含 inventor 原稿），支持 acceptance/IPC/summarization。https://huggingface.co/datasets/HUPD/hupd
- **BigPatent** — 1.3M USPTO + 摘要。https://huggingface.co/datasets/NortheasternUniversity/big_patent
- **PEDANTIC** — 14k 不清楚性标注，OA 训练/评测
- **D2P (AutoPatent)** — 1.5k draft-patent pairs
- **CNIPA 公开** — https://english.cnipa.gov.cn/ ，中文数据集业界自建为主
- **USPTO bulk** — bulkdata.uspto.gov

## D. 最值得 clone 到 refs/3rd_repos/

1. **QiYao-Wang/AutoPatent** — 唯一开源多 agent 全文撰写框架，PGTree+RRAG 可迁到 CNIPA 中文撰写（替换底座为 Qwen3/GLM-5）。**首选**。
2. **QiYao-Wang/Awesome-LLM4Patents** + **thcheung/awesome-llms-for-patent-analysis** — 作为 refs/专利专家知识库/ 导航。
3. **suzgunmirac/hupd** — 数据加载+基线任务代码。

补充：HF 拉 `mpi-inno-comp/paecter` 与 `AI-Growth-Lab/PatentSBERTa` 作检索冷启动；中文需自建——可用 Qwen3-Embedding 在 CNIPA 公开摘要+引用对上微调"PaECTER-zh"。
