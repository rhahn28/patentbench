---
title: "Why No Patent AI Tool Publishes Benchmarks. And Why We're About to Change That"
date: 2026-03-19
author: Roger Hahn
category: insights
meta_description: "Patent prosecution is a $7B+ market with zero published AI benchmarks. We examine why no vendor shares accuracy data, and announce PatentBench, the first open benchmark for patent AI."
tags:
 - patent AI
 - patent prosecution
 - AI benchmark
 - legal AI
 - hallucination
 - transparency
 - PatentBench
---

# Why No Patent AI Tool Publishes Benchmarks. And Why We're About to Change That

Patent prosecution is a \$7 billion market undergoing rapid AI transformation. Dozens of startups have raised hundreds of millions of dollars promising to revolutionize how patents are drafted, prosecuted, and analyzed. There is just one problem: not a single one of them publishes reproducible accuracy data.

Think about that for a moment. In a field where a single missed prior art reference can invalidate a patent worth millions, where a poorly drafted claim limitation can sink an entire portfolio, the tools being sold to practitioners come with less verifiable performance data than a consumer dishwasher.

This is not an oversight. It is a strategy. And it is about to end.

## The $7B Market With Zero Benchmarks

Patent prosecution, the practice of preparing, filing, and negotiating patent applications with the USPTO, generates over \$7 billion in annual legal fees in the United States alone. The work is complex, technical, and consequential. A single patent application can take 20-40 hours of attorney time. An Office Action response can take 5-15 hours. The economics make it an obvious target for AI automation.

The venture capital market has noticed. In the past three years, patent AI companies have collectively raised well over \$100 million:

| Company | Funding | What They Claim | Published Benchmarks |
|---------|---------|-----------------|---------------------|
| Solve Intelligence | \$55M | "AI patent drafting" | None |
| Patlytics | \$21M | "AI patent analytics" | None |
| IPRally | \$35M | "AI patent search" | None |
| PatSnap | IPO-level | "Connected innovation intelligence" | None |
| DeepIP | Undisclosed | "AI patent prosecution" | None |

Every single one of these companies makes performance claims on their websites. "50% faster drafting." "3x more productive." "Unprecedented accuracy." Not one of them publishes the methodology behind these claims. Not one of them subjects their system to independent, reproducible evaluation.

In every other domain of AI that matters, computer vision, natural language processing, code generation, medical imaging, published benchmarks are table stakes. ImageNet transformed computer vision. SQuAD transformed question answering. SWE-bench transformed code generation. These benchmarks did not just measure progress; they drove it.

Patent prosecution has nothing.

## The Hallucination Problem Nobody Wants to Talk About

In 2024, Stanford's Institute for Human-Centered Artificial Intelligence published a study that sent shockwaves through the legal industry. Researchers found that AI tools from two of the largest legal research platforms, systems already deployed to thousands of law firms, were hallucinating at alarming rates.

**LexisNexis AI:** 17% hallucination rate on legal research queries.

**Westlaw AI (Thomson Reuters):** 33% hallucination rate on legal research queries.

These are not obscure research prototypes. These are production systems used by attorneys who rely on them to find binding case law. A 17-33% hallucination rate means that roughly one in four to one in three AI-generated legal citations pointed to cases that did not exist, held differently than described, or were materially mischaracterized.

Now consider patent prosecution. When an attorney responds to a 35 U.S.C. 103 obviousness rejection, they must accurately characterize prior art references, distinguish specific claim limitations, and construct arguments grounded in factual accuracy. A hallucinated teaching in a prior art reference does not just waste time, it can constitute inequitable conduct before the USPTO if it materially misrepresents the record.

If Westlaw's AI hallucinates at 33% on straightforward legal research, what is the hallucination rate for patent AI tools performing the far more complex task of prior art analysis and argument generation?

Nobody knows. Because nobody measures it.

## Why Vendors Don't Publish (And Why Their Excuses Don't Hold Up)

When pressed on the absence of benchmarks, patent AI vendors typically offer one of three responses:

**"Our technology is proprietary."** Publishing benchmark results does not require revealing model architecture, training data, or proprietary methods. SWE-bench evaluates closed-source models like GPT-4 and Claude without accessing their weights. A benchmark measures outputs, not internals.

**"Patent work is too subjective to benchmark."** This is the most common excuse, and the most revealing. Yes, evaluating the quality of a patent argument involves judgment. But patent prosecution also involves objectively measurable components: Did the system correctly parse the Office Action? Did it accurately identify which claims were rejected? Did it cite real passages from real prior art references? Did it address every rejection ground? These are not subjective questions.

**"Our customers validate our quality."** Customer satisfaction is not a benchmark. Customers lack the ability to systematically test edge cases, measure hallucination rates across hundreds of Office Actions, or compare performance across difficulty levels. A customer who saves time using an AI tool may not realize that 15% of the generated arguments contain fabricated prior art characterizations, especially if the output reads fluently.

The real reason vendors do not publish benchmarks is simpler: they are afraid of what the numbers would show.

## The Existing Benchmark Landscape (And Its Gaps)

The legal AI community has made some progress on benchmarking, but the gaps are enormous.

**LegalBench** is the most comprehensive legal reasoning benchmark to date. Developed by a consortium of researchers, it contains 162 tasks spanning contract interpretation, statutory reasoning, and legal knowledge. It is an impressive achievement. It contains exactly zero tasks related to patent prosecution.

**legalbenchmarks.ai** is a newer effort focused on practical legal AI evaluation. It covers contract review, due diligence, and document analysis. Patent prosecution is absent from its roadmap.

**CUAD** (Contract Understanding Attainment Dataset) revolutionized contract analysis benchmarking. Nothing comparable exists for patent work.

The pattern is clear. The legal AI benchmarking community has focused almost exclusively on contracts and litigation, areas where large labeled datasets are more readily available. Patent prosecution, with its unique combination of technical complexity, legal reasoning, and USPTO-specific procedural requirements, has been left entirely unaddressed.

This is not because patent prosecution is less important. It is because building a patent prosecution benchmark is genuinely hard. You need real Office Actions. You need to understand the technical domains. You need practicing patent attorneys to evaluate outputs. You need to design evaluation criteria that capture the multi-dimensional nature of prosecution quality.

Hard is not the same as impossible. It just means nobody has been willing to do the work.

Until now.

## Introducing PatentBench

ABIGAIL is building PatentBench, the first reproducible, open benchmark for patent prosecution AI.

PatentBench is not a marketing exercise. It is a rigorous evaluation framework built on three principles that we believe any serious AI benchmark must satisfy:

**Real data.** PatentBench uses 300 real USPTO Office Actions spanning multiple technology domains, rejection types, and complexity levels. No synthetic examples. No cherry-picked easy cases. Real prosecution scenarios that practicing attorneys encounter every day.

**Expert evaluation.** Every test case is evaluated by practicing patent attorneys, not crowdsourced annotators, not automated metrics alone. Attorney evaluators assess argument quality, technical accuracy, claim amendment appropriateness, and strategic soundness using calibrated rubrics.

**Reproducibility.** The benchmark, evaluation methodology, and baseline results will be fully open source. Any vendor, researcher, or practitioner can run PatentBench against any system and verify the results independently.

We are designing PatentBench with five difficulty tiers, from administrative tasks (Office Action parsing, deadline extraction) through associate-level work (argument drafting, amendment preparation) up to partner-level strategic decisions (prosecution strategy, continuation planning). This tiered approach lets us measure not just whether a system works, but where it breaks down.

## The Glass Box Standard

PatentBench is the first implementation of what we call the Glass Box Standard, five pillars of transparency that we believe every patent AI vendor should meet:

1. **Published accuracy metrics.** Not marketing claims. Reproducible numbers on standardized test cases.

2. **Hallucination rate disclosure.** What percentage of generated content contains fabricated citations, invented prior art characterizations, or factually incorrect legal assertions?

3. **Failure mode analysis.** Where does the system break? What types of Office Actions, technology domains, or rejection grounds cause degraded performance?

4. **Difficulty-stratified results.** How does performance vary across easy, moderate, and hard cases? A system that scores 95% on straightforward 102 rejections but 30% on complex 103 combinations is not "95% accurate."

5. **Independent reproducibility.** Can a third party run the same evaluation and get the same results?

These are not radical requirements. They are the minimum standard that any field claiming scientific rigor should demand. Medical AI requires FDA-cleared benchmarks. Autonomous vehicles require NHTSA testing. Patent AI requires nothing, and that needs to change.

## What This Means for Practitioners

If you are a patent attorney evaluating AI tools, you should be asking every vendor three questions:

1. What is your hallucination rate on patent prosecution tasks?
2. Can I run an independent benchmark against your system?
3. Will you publish your PatentBench results?

The answers, or more likely, the evasions, will tell you everything you need to know.

If a vendor claims "95% accuracy" but cannot tell you what dataset they measured against, what evaluation criteria they used, or whether an independent party has verified the claim, you are not looking at a performance metric. You are looking at a marketing number.

## What Comes Next

PatentBench-Mini, our initial release of 300 test cases, ships in Q2 2026. The full benchmark, evaluation toolkit, and baseline results will be open-sourced on GitHub and the dataset published on HuggingFace.

We will publish ABIGAIL's own PatentBench results, including our failure modes and hallucination rates. We expect the numbers to be imperfect. That is the point. Transparency means showing where you fall short, not just where you excel.

And we will publicly invite every patent AI vendor to do the same.

## A Challenge to the Industry

We challenge every patent AI vendor. Solve Intelligence, Patlytics, IPRally, DeepIP, PatSnap, and every other company selling AI-powered patent tools, to publish their PatentBench results.

If your system works as well as your marketing claims suggest, you have nothing to fear and everything to gain. Published benchmark results are a competitive advantage for any system that actually performs.

If you refuse to participate, the market will draw its own conclusions.

The era of unverifiable claims in patent AI is ending. The question is whether vendors will lead the transition to transparency or be dragged into it.

We know which side we are on.

---

*PatentBench is an open-source project from [ABIGAIL](https://abigail.app). Explore the benchmark at [abigail.app/patentbench](https://abigail.app/patentbench) or contribute on [GitHub](https://github.com/abigail-ai/patentbench).*
