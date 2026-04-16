---
title: "The Transparency Crisis in Patent AI: $100M+ in Funding, Zero Published Accuracy Data"
date: 2026-03-19
author: Roger Hahn
category: insights
meta_description: "Over $100M has been invested in patent AI tools, yet no company publishes reproducible accuracy data. We examine the transparency crisis and what patent attorneys should demand."
tags:
 - patent AI
 - patent prosecution
 - legal AI
 - transparency
 - hallucination
 - AI benchmark
 - due diligence
 - PatentBench
---

# The Transparency Crisis in Patent AI: $100M+ in Funding, Zero Published Accuracy Data

Venture capital has poured over \$100 million into companies promising to transform patent prosecution with artificial intelligence. Solve Intelligence raised \$55 million. IPRally raised \$35 million. Patlytics raised \$21 million. PatSnap has reached IPO-scale valuations. Dozens of smaller companies have raised undisclosed rounds.

Every one of these companies makes bold claims about accuracy, productivity, and quality. Not one of them publishes reproducible benchmark data to substantiate those claims.

This is not a minor omission. It is a transparency crisis that puts patent attorneys, their clients, and entire patent portfolios at risk.

## What Patent AI Vendors Publish vs. What They Don't

The gap between what patent AI companies claim and what they can prove is striking. Here is what publicly available information reveals about the major players:

| Company | Funding | Public Claims | Methodology Published? | Independent Verification? | Hallucination Rate? |
|---------|---------|--------------|----------------------|--------------------------|-------------------|
| Solve Intelligence | \$55M | "AI-powered patent drafting and prosecution" | No | No | Not disclosed |
| Patlytics | \$21M | "AI patent analytics platform" | No | No | Not disclosed |
| IPRally | \$35M | "AI-powered patent search" | No | No | Not disclosed |
| PatSnap | IPO-level | "Connected innovation intelligence" | No | No | Not disclosed |
| DeepIP | Undisclosed | "AI patent prosecution assistant" | No | No | Not disclosed |
| Various others | \$10M+ combined | Various productivity claims | No | No | Not disclosed |

The pattern is uniform. Marketing pages feature testimonials, case studies with unnamed clients, and percentage improvements with no disclosed methodology. The claims follow a familiar template: "X% faster," "Y% more productive," "Z hours saved per matter."

None of them answer the questions that actually matter to a patent attorney deciding whether to trust AI output:

- What is the hallucination rate?
- On what types of Office Actions does the system fail?
- Has any independent party verified the claimed accuracy?
- What happens when the system encounters a technology domain outside its training data?

## The Stanford Precedent

The absence of transparency in patent AI is especially concerning in light of what we already know about legal AI hallucination.

In 2024, researchers at Stanford's Institute for Human-Centered AI conducted a systematic evaluation of AI-assisted legal research tools from the two largest legal information providers. The findings were sobering:

- **LexisNexis AI** hallucinated on **17%** of legal research queries, citing cases that did not exist, mischaracterizing holdings, or fabricating legal principles.
- **Westlaw AI (Thomson Reuters)** hallucinated on **33%** of queries, one in three responses contained material inaccuracies.

These are not startup prototypes. These are tools from billion-dollar companies, deployed to thousands of law firms, built by teams with decades of legal technology experience. And they hallucinate at rates that would be considered a safety hazard in any other professional context.

Now consider the implications for patent prosecution AI. Responding to a 103 obviousness rejection requires the AI to accurately characterize what multiple prior art references teach, identify specific claim limitations that are absent from the prior art, and construct arguments that the examiner's proposed combination would not have been obvious. The factual grounding required is more demanding than a legal research query, not less.

If best-in-class legal research AI hallucinates at 17-33%, what should we expect from patent prosecution AI performing more complex analysis?

We do not know. And that is exactly the problem.

## Why "50% More Productive" Means Nothing

The most common performance claim in patent AI marketing is some variant of productivity improvement: "Our users are 50% more productive." "Save 10 hours per Office Action." "3x faster patent drafting."

These claims share a common deficiency: they measure speed without measuring accuracy.

A system that generates an Office Action response in 30 minutes instead of 10 hours sounds impressive, until you discover that an attorney must spend 4 hours verifying and correcting the output. The net time savings may be real, but the marketed "50% more productive" figure obscures a critical question: how much of the AI's output was wrong?

Productivity claims without accuracy methodology are meaningless for three reasons:

**They conflate speed with quality.** An AI that generates a plausible-sounding but factually incorrect 103 argument in 5 minutes is not "productive", it is dangerous. The attorney must now do the original work plus the additional work of identifying which parts of the AI output are wrong.

**They lack control conditions.** "50% faster" compared to what? Compared to the same attorney without the tool? Compared to a different attorney? Compared to the firm's historical average? Without a disclosed methodology, the number is unfalsifiable.

**They select for favorable cases.** Vendors typically derive productivity numbers from self-selected customer surveys or internal testing on cherry-picked examples. The cases where the AI completely failed, generating unusable output that the attorney had to discard, are unlikely to appear in the sample.

The standard that patent attorneys should demand is simple: show me the accuracy data, not just the speed data.

## What Buyers Should Demand

If you are a patent attorney, law firm partner, or corporate IP counsel evaluating AI tools, you should require the following before making a purchasing decision:

### 1. Reproducible Benchmark Results

Ask the vendor: "What benchmark do you evaluate against, and can I run it independently?"

If the answer is "we have internal benchmarks but they're proprietary," that tells you something important. Internal benchmarks are not benchmarks, they are QA tests designed by the same team that built the system. They are optimized to make the system look good.

A real benchmark is:
- Publicly available
- Runnable by anyone
- Evaluated against an independent gold standard
- Reproducible across different environments

PatentBench is designed to provide exactly this. But even if a vendor uses a different benchmark, the key criterion is independent reproducibility.

### 2. Hallucination Rate Disclosure

Ask the vendor: "What percentage of your outputs contain factual errors, fabricated citations, or mischaracterized prior art?"

If the vendor cannot answer this question with a specific number and a described methodology, they have not measured it. And if they have not measured it, they do not know.

The hallucination rate is arguably the single most important metric for patent prosecution AI. A hallucinated prior art characterization can lead to:
- Arguments based on distinctions that do not exist
- Amendments that do not actually overcome the rejection
- Potential inequitable conduct issues if misrepresentations reach the USPTO

### 3. Failure Mode Analysis

Ask the vendor: "On what types of Office Actions or technology domains does your system perform worst?"

Every AI system has failure modes. A vendor that claims uniform performance across all domains is either lying or has not tested broadly enough to find the failures.

Honest failure mode disclosure looks like: "Our system performs well on software and electrical 103 rejections (82% quality score) but degrades significantly on biotech 103 rejections (54% quality score) and struggles with multi-reference combinations of more than three references (47% quality score)."

This kind of disclosure is not a weakness. It is evidence that the vendor actually understands their own system.

### 4. Independent Third-Party Evaluation

Ask the vendor: "Has any independent party evaluated your system's accuracy?"

Peer-reviewed publications, independent benchmark results, or third-party audits carry weight. Self-reported accuracy numbers do not.

## The Revealed Preference Test

There is a simple thought experiment that cuts through the noise around patent AI transparency.

If a vendor's system truly performs as well as they claim, publishing benchmark results is an obvious competitive advantage. Imagine being the only patent AI tool that can point to independently verified accuracy data. Every rational buyer would prefer a tool with proven performance over a tool with unverifiable claims.

The fact that no major patent AI vendor publishes benchmark results tells you something important about what they expect those results would show. This is a revealed preference: their behavior reveals their beliefs more honestly than their marketing.

A vendor that refuses to run an open benchmark is making a calculation. They have concluded that the risk of unfavorable results outweighs the benefit of transparency. That calculation only makes sense if they expect the results to be unfavorable.

This does not necessarily mean the tools are useless. It means the vendors believe that disclosed performance data would be less impressive than their marketing suggests. For a buyer making a six-figure purchasing decision, that inference should matter.

## How PatentBench Creates Accountability

We built PatentBench to provide the accountability mechanism that the patent AI market currently lacks.

PatentBench is open source, freely available, and designed so that any vendor can run it against their system. The benchmark uses real USPTO Office Actions, evaluates across multiple difficulty levels, and includes dedicated anti-hallucination testing.

When PatentBench results are published, patent attorneys will be able to make informed comparisons for the first time:

- Which system has the lowest hallucination rate?
- Which system handles complex multi-reference 103 rejections best?
- Which system degrades least across unfamiliar technology domains?
- Which system correctly identifies all rejection grounds in a complex Office Action?

These are the questions that matter for purchasing decisions. Today, buyers have no data. After PatentBench, they will.

We will publish ABIGAIL's own results, including areas where we underperform. We expect our numbers to be imperfect. Every system's numbers will be imperfect. The point is not perfection, it is transparency.

## The Cost of Opacity

The transparency crisis in patent AI has real costs that are borne by practitioners and their clients.

**Wasted attorney time.** When attorneys cannot evaluate AI accuracy before adoption, they learn the system's failure modes through experience, which means spending hours correcting AI-generated errors that a benchmark would have predicted.

**Client risk.** A hallucinated prior art characterization that makes it into a USPTO filing can create prosecution history estoppel based on a distinction that does not exist. This is not a theoretical risk, it is the natural consequence of using tools with unknown hallucination rates on consequential legal documents.

**Market inefficiency.** Without benchmark data, buyers cannot distinguish between genuinely superior tools and tools with superior marketing. Capital flows to companies with the best sales teams, not the best technology. This is bad for buyers, bad for innovation, and ultimately bad for the vendors who actually do have superior technology but cannot prove it.

**Erosion of professional trust.** Patent attorneys are officers of the USPTO. They have a duty of candor and good faith. Relying on AI tools with unknown accuracy characteristics creates tension with that obligation. Transparent benchmark data would allow attorneys to make informed decisions about where AI can be trusted and where human review is essential.

## A Call to Action

If you are a **patent attorney**: demand benchmark data from every AI vendor you evaluate. Ask for hallucination rates. Ask for failure mode analysis. Ask whether they will run PatentBench. The answers will tell you more than any product demo.

If you are a **law firm partner** making purchasing decisions: include benchmark performance in your evaluation criteria alongside pricing, integration, and user experience. A tool that is 20% cheaper but hallucinates at 3x the rate of the alternative is not a bargain.

If you are an **investor** in patent AI: ask your portfolio companies why they have not published benchmark data. If they give you a reason other than "the numbers aren't where we want them to be," they are giving you a reason that is less honest than the real one.

If you are a **patent AI vendor**: run PatentBench and publish the results. If your system is as good as you claim, the data will speak for itself. If it is not, the data will show you where to improve. Either way, the market moves toward transparency, and the vendors who get there first gain an enduring advantage.

The era of selling patent AI on marketing claims alone is ending. The buyers are getting smarter. The benchmarks are arriving. The question for every company in this space is whether they will lead the transparency transition or be overtaken by it.

PatentBench is available now. We are publishing our numbers. Who else will?

---

*PatentBench is an open-source project from [ABIGAIL](https://abigail.app). Explore the benchmark at [abigail.app/patentbench](https://abigail.app/patentbench) or view the source on [GitHub](https://github.com/abigail-ai/patentbench).*
