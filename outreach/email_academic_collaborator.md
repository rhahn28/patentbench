# Email: Academic Collaborator Recruitment

---

## Subject Line Options

1. **Research Collaboration: The First Benchmark for AI Patent Prosecution**
2. **PatentBench. Filling a Critical Gap in Legal AI Evaluation (Collaboration Invitation)**
3. **NeurIPS Submission Opportunity: Benchmarking LLMs on Patent Office Action Responses**

---

## VERSION A: Law School Researcher (Stanford Law, Berkeley Law, etc.)

**To:** Professor [NAME] <[EMAIL]>
**Subject:** [CHOOSE SUBJECT LINE ABOVE]

Dear Professor [NAME],

Your work on [PAPER TITLE / RESEARCH AREA, e.g., "AI-Assisted Legal Reasoning" / "Computational Approaches to Patent Analysis" / "Empirical Studies of Patent Prosecution Outcomes"] has been influential in framing how we think about [SPECIFIC CONTRIBUTION, e.g., the intersection of machine learning and patent law / empirical measurement of legal quality]. I am writing because I believe your research agenda aligns closely with a project I am building, and I would like to explore a collaboration.

**The Gap**

Legal AI benchmarks exist for contract review (ContractNLI), case prediction (CAIL), and statutory interpretation. But there is no benchmark for patent prosecution, the single most high-volume, economically consequential task in IP law. Every major AI company is building patent tools, and the profession has no rigorous way to evaluate them. This is a significant gap in the literature and in practice.

**What is PatentBench?**

PatentBench is a curated dataset and evaluation framework for measuring LLM performance on USPTO Office Action responses. The dataset includes:

- [NUMBER] real Office Actions spanning [NUMBER] technology areas and art units
- Ground-truth attorney responses that resulted in successful prosecution outcomes
- Multi-dimensional scoring rubrics covering legal accuracy, strategic quality, claim construction, and MPEP compliance
- Expert evaluations from practicing patent attorneys

This is, to my knowledge, the first attempt at a standardized, reproducible benchmark for AI patent prosecution.

**Why your expertise matters:**

The evaluation rubric is the heart of the benchmark. We need legal scholarship rigor in defining what "quality" means for an Office Action response. Your work on [SPECIFIC ASPECT OF THEIR RESEARCH] is directly relevant to [SPECIFIC RUBRIC DIMENSION, e.g., how we define and measure "strategic soundness" / "argument quality" / "legal reasoning accuracy"].

**The collaboration:**

- **Co-authorship** on the benchmark paper (targeting NeurIPS 2026 Datasets and Benchmarks track, with ICAIL as a secondary venue)
- **Pre-publication access** to the full dataset and all evaluation results
- **Specific ask for your team:** Rubric design and validation, evaluation methodology review, and (if interested) participation in the attorney evaluation panel
- Potential for follow-on research: longitudinal studies as models improve, cross-jurisdictional expansion (EPO, JPO), specialized domain benchmarks

I would welcome the opportunity to discuss this in more detail. Could we schedule a 30-minute call in the next two weeks? I can also share our current dataset specification and preliminary rubric for your review.

Best regards,

Roger Hahn
USPTO-Registered Patent Attorney
Creator, PatentBench
[EMAIL] | [PHONE]

---

## VERSION B: CS / AI Researcher (MIT CSAIL, Stanford AI Lab, etc.)

**To:** Professor [NAME] <[EMAIL]>
**Subject:** [CHOOSE SUBJECT LINE ABOVE]

Dear Professor [NAME],

Your recent work on [PAPER TITLE / RESEARCH AREA, e.g., "Evaluating LLMs on Domain-Specific Professional Tasks" / "Benchmark Design for Reasoning-Intensive Applications" / "Retrieval-Augmented Generation for Specialized Knowledge Domains"] is highly relevant to a benchmark project I am building, and I wanted to explore whether a collaboration might interest you.

**The Problem**

LLM benchmarks cover code generation (HumanEval), mathematical reasoning (MATH/GSM8K), medical knowledge (MedQA), and general legal tasks (LegalBench). But there is no benchmark for patent prosecution, a domain that combines complex legal reasoning, technical analysis, strategic argumentation, and strict procedural compliance. It is arguably one of the most demanding professional knowledge tasks an LLM can attempt, and it is completely unmeasured.

**What is PatentBench?**

PatentBench is a benchmark and evaluation harness for measuring LLM performance on responding to USPTO patent Office Actions. Key characteristics:

- **Task complexity:** Each instance requires reading a multi-page examiner rejection, analyzing cited prior art, constructing legal arguments, and drafting claim amendments, all under strict procedural rules
- **Ground truth:** Real attorney responses that resulted in patent allowance
- **Multi-dimensional evaluation:** Not just "correct/incorrect" but rated across legal accuracy, strategic quality, technical understanding, and compliance
- **Expert-validated:** Scoring by practicing USPTO-registered patent attorneys
- **Dataset size:** [NUMBER] instances across [NUMBER] technology domains

**Why this matters for your research:**

Patent prosecution is a stress test for LLMs that combines:
1. Long-context reasoning (Office Actions + specifications can exceed 50 pages)
2. Domain-specific retrieval (MPEP, CFR, case law)
3. Multi-step strategic planning (amendment + argument must work together)
4. Precise, constrained generation (legal and procedural requirements)

This makes it a compelling evaluation axis for reasoning-focused models, RAG systems, and agent architectures.

**The collaboration:**

- **Co-authorship** on the benchmark paper (targeting NeurIPS 2026 Datasets and Benchmarks track)
- **Pre-publication access** to the full dataset
- **Specific ask for your team:** Evaluation harness development, baseline model testing (GPT-4, Claude, Gemini, Llama, etc.), ablation studies on prompt strategies and retrieval approaches
- Your lab would have first-mover access to publish results using PatentBench before public release

I can share our dataset specification, preliminary evaluation framework, and initial results. Would you have 30 minutes in the next two weeks for a call?

Best regards,

Roger Hahn
USPTO-Registered Patent Attorney
Creator, PatentBench
[EMAIL] | [PHONE]

---

## VERSION C: Interdisciplinary Researcher (Law + CS)

**To:** Professor [NAME] <[EMAIL]>
**Subject:** [CHOOSE SUBJECT LINE ABOVE]

Dear Professor [NAME],

Your interdisciplinary work bridging [LAW AREA] and [CS AREA], particularly [SPECIFIC PAPER OR PROJECT], is exactly the kind of perspective that a new benchmark project needs. I am building PatentBench, the first standardized benchmark for evaluating AI systems on patent prosecution tasks, and I believe a collaboration could be mutually productive.

Patent prosecution sits at the intersection of legal reasoning, technical analysis, and strategic communication, making it one of the richest domains for studying LLM capabilities in professional settings. Yet no benchmark exists. PatentBench fills that gap with a curated dataset of real Office Actions, expert-validated evaluation rubrics, and a reproducible evaluation harness.

**What makes this unique as a research contribution:**

- It is the first benchmark in a $15B+ professional services domain with zero prior evaluation infrastructure
- The evaluation methodology bridges quantitative metrics (automated scoring) with qualitative expert assessment (attorney panels)
- The dataset enables research on legal reasoning, domain adaptation, RAG, long-context understanding, and constrained generation simultaneously

**The collaboration opportunity:**

- Co-authorship on the NeurIPS 2026 Datasets and Benchmarks submission
- Pre-publication dataset access
- Your specific expertise in [THEIR AREA] would strengthen our [RUBRIC DESIGN / EVALUATION METHODOLOGY / MODEL TESTING / ANALYSIS]
- Potential for a series of follow-on papers as the benchmark expands

Would you be open to a 30-minute conversation? I can share our current materials in advance.

Best regards,

Roger Hahn
USPTO-Registered Patent Attorney
Creator, PatentBench
[EMAIL] | [PHONE]

---

## Follow-Up Template (All Versions)

**Subject:** Re: [ORIGINAL SUBJECT]. Dataset Preview Available

Dear Professor [NAME],

Following up on my earlier note about PatentBench. Since I last wrote, we have confirmed collaborations with researchers at [INSTITUTION NAMES] and our attorney evaluation panel includes [NUMBER] practitioners.

I have attached a brief dataset specification document and our preliminary evaluation rubric. I think seeing the actual data will make the research potential concrete.

Would [SPECIFIC DATE/TIME OPTIONS] work for a brief call?

Best regards,
Roger
