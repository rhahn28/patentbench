# The PatentBench Manifesto

### Why Patent Prosecution AI Has a Credibility Crisis, and How We Fix It

---

*"In God we trust. All others must bring data."*
W. Edwards Deming

---

## I. The $7 Billion Black Box

Patent prosecution is a **$7 billion annual market** in the United States alone. Every year, hundreds of thousands of patent applications move through the USPTO, each one a high-stakes negotiation between applicants and examiners that determines whether an invention receives legal protection. A single claim amendment can mean the difference between a patent worth millions and an abandoned application worth nothing.

Into this market, a new generation of AI companies has arrived. They have raised **hundreds of millions of dollars**. They promise to revolutionize how patents are prosecuted. And they ask you to trust them.

But here is the uncomfortable truth:

> **Not one of them can show you a reproducible benchmark proving their AI actually works for patent prosecution.**

Not one.

---

## II. The Transparency Vacuum

Let us be specific, because specificity is what this industry lacks.

**Solve Intelligence** has raised over **$55 million** in venture funding. Their marketing claims their platform makes patent professionals "50% more productive." Where is the data? Where is the methodology? Where is the reproducible evaluation? There is none. Fifty-five million dollars, and the public evidence is a marketing claim on a website.

**Patlytics** raised **$21 million**. Their proof of efficacy? "18x customer growth." Customer growth is a business metric. It tells you nothing about whether the AI drafts accurate claims, identifies relevant prior art, or produces arguments that survive examiner scrutiny. Eighteen-times-more customers buying a product you cannot independently verify is not evidence. It is salesmanship.

**DeepIP** publishes zero benchmarks. What they offer instead is self-authored feature comparison charts, the vendor grading its own homework. No independent evaluation. No reproducible methodology. No public test set.

**PatSnap** comes closest with a single reported metric: an **81% "X Hit Rate"** for prior art search. One metric. For one task. With no public methodology, no reproducible test set, and no coverage of the other four-fifths of patent prosecution. And even that number cannot be independently verified.

This is not a criticism of any individual company. This is an indictment of an entire market that has decided **trust us** is an acceptable substitute for **here are the numbers.**

---

## III. The Hallucination Problem Is Not Hypothetical

In 2024, researchers at Stanford published a landmark study evaluating AI-powered legal research tools. The findings should alarm anyone relying on AI for patent prosecution:

> **LexisNexis CoCounsel (built on Casetext, acquired for $650 million): 17% hallucination rate.**
>
> **Thomson Reuters Westlaw AI: 33% hallucination rate.**

One in three responses from Westlaw's AI contained fabricated legal citations, invented case holdings, or hallucinated reasoning. One in six from a tool that cost $650 million to acquire.

These are not patent prosecution tools specifically. But they are the **same underlying technology**, large language models applied to legal text, and they demonstrate a fundamental problem: without rigorous, domain-specific benchmarks, you cannot distinguish a tool that works from a tool that confidently fabricates.

In patent prosecution, hallucination is not an academic concern. A fabricated prior art reference in an Information Disclosure Statement is a potential fraud on the USPTO. An invented claim construction in an office action response can estop future claim scope. A hallucinated examiner citation in a pre-appeal brief is malpractice.

The consequences are not embarrassment. They are **inequitable conduct findings, malpractice liability, and invalidated patents.**

---

## IV. The Benchmark Desert

Perhaps the benchmarks exist elsewhere? Perhaps academia has filled the gap?

No.

**LegalBench** (2023) is the most comprehensive legal AI benchmark to date. It covers 162 tasks across six categories of legal reasoning. The number of those tasks that address patent prosecution: **zero.**

**legalbenchmarks.ai** focuses on contract drafting and review. Patent prosecution is entirely absent.

**Patent-CE** (NAACL 2025) evaluates claim construction and claim evaluation, one narrow slice of prosecution. It does not cover office action response, claim amendment strategy, prior art analysis, argument construction, or any of the other skills that constitute actual patent prosecution practice.

This is the state of the field: a **$7 billion market** with **zero published, reproducible benchmarks** covering the core work of patent prosecution.

The coding AI community has SWE-bench. The math AI community has GSM8K and MATH. The general reasoning community has MMLU and ARC. Patent prosecution AI has nothing.

> **You cannot improve what you cannot measure. And right now, the patent AI industry refuses to measure.**

---

## V. What PatentBench Is

PatentBench is the benchmark this industry should have built years ago, and didn't.

### The Numbers

- **7,200 test cases** across 5 prosecution domains
- **Built from real USPTO prosecution histories**, not synthetic examples, not hand-crafted toy problems, but actual office actions, actual responses, and actual outcomes from the public patent record
- **5 difficulty tiers** calibrated to attorney experience levels, from junior associate tasks to partner-level strategic decisions
- **4-layer evaluation architecture** that measures not just whether an AI produces plausible-sounding text, but whether it produces *correct, strategically sound, and legally defensible* work product

### The Five Domains

1. **Office Action Analysis**. Can the AI correctly identify every rejection, its legal basis, and the specific claims affected?
2. **Claim Amendment**. Can the AI propose amendments that overcome rejections without unnecessarily narrowing scope?
3. **Argument Construction**. Can the AI build persuasive legal arguments grounded in actual MPEP authority and case law?
4. **Prior Art Analysis**. Can the AI distinguish material prior art from noise and assess anticipation vs. obviousness?
5. **Prosecution Strategy**. Can the AI recommend optimal prosecution paths considering the full landscape of options?

### What Makes It Different

**Outcome-Based Evaluation.** Because PatentBench is built from real prosecution histories, we know what actually happened. Did the examiner allow the claims? Was the patent granted? Did the response succeed? We do not merely ask whether the AI's output looks reasonable. We test whether it would have worked.

**Anti-Hallucination Testing.** PatentBench includes poison pill detection, fabricated citations, invented MPEP sections, and hallucinated case law are planted in test scenarios. If your AI cites them, we catch it. If your AI invents its own, we catch that too. Every factual assertion is verified against ground truth.

**Economic Validity.** Performance on PatentBench maps to real economic outcomes. We connect accuracy scores to prosecution cost, time-to-allowance, and claim scope preservation. A benchmark that cannot tell you what a 10-point score improvement is worth in dollars is a benchmark that cannot guide investment decisions.

**Difficulty Calibration.** Tier 1 tasks are things a well-trained junior associate handles routinely. Tier 5 tasks are the ones that keep senior partners up at night. Knowing that an AI scores 90% overall means nothing if all 90% is on easy cases. PatentBench tells you exactly where an AI's competence ends.

---

## VI. The Glass Box Standard

PatentBench is built on five pillars of transparency we call the **Glass Box Standard**:

> **1. Open Methodology.** Every scoring rubric, every evaluation criterion, every weighting decision is published and explained. There are no proprietary secret sauces in how we grade.
>
> **2. Reproducible Results.** Any team with access to the test set can run the benchmark independently and verify our numbers. If you disagree with a score, you can prove it.
>
> **3. Real Data Provenance.** Every test case traces back to a specific, publicly available USPTO prosecution history. You can pull the file wrapper and verify every ground truth answer yourself.
>
> **4. Version-Controlled Evolution.** As patent law evolves, so does PatentBench. Every change is versioned, documented, and justified. Historical results remain comparable.
>
> **5. Conflict-Free Evaluation.** No vendor grades itself. The benchmark exists independently of any commercial product, including our own.

We call it Glass Box because that is exactly what the patent AI industry needs: not a black box that asks for trust, but a transparent system that earns it.

---

## VII. Why ABIGAIL Is Doing This

A reasonable question: why would a patent AI company build a benchmark that could expose its own weaknesses?

The answer is straightforward.

**Roger Hahn is a USPTO-registered patent attorney.** PatentBench was not designed by machine learning researchers who read a patent textbook. It was designed by someone who has prosecuted patents, responded to office actions, and argued before examiners. Domain expertise is not optional when you are building a domain-specific benchmark. It is the prerequisite.

**ABIGAIL has nothing to hide.** We are building Glass Box architecture because we believe the best way to prove your product works is to let the world verify it. If our AI has weaknesses, and every AI does, we would rather find them in a benchmark than in a client's abandoned patent application.

**Defining the standard is the highest-leverage contribution we can make.** SWE-bench did not just measure coding agents. It defined what it *means* to be good at automated software engineering. Every coding AI company now reports SWE-bench scores. PatentBench will do the same for patent prosecution. The company that defines how the world evaluates patent AI shapes the entire market's direction.

We are not doing this despite being a competitor. We are doing this *because* we are a competitor, one that believes the market is better when customers can make informed decisions based on real data.

---

## VIII. The Challenge

This section is addressed directly to every company building AI for patent prosecution.

To **Solve Intelligence**: You have raised $55 million. You claim 50% productivity gains. Prove it. Submit your tool for PatentBench evaluation. If your product delivers what you promise, the numbers will speak for themselves. If you decline, your silence will speak louder.

To **Patlytics**: You have $21 million in funding and 18x customer growth. Your customers deserve to know how your AI performs on standardized, independently verified test cases. Submit your tool. Let the data do the talking.

To **DeepIP**: You publish feature comparison charts authored by your own team. Replace them with something the market can trust. Submit your tool for independent evaluation.

To **PatSnap**: You have one metric for one task. Let us give you metrics for all five domains of patent prosecution. Submit your tool.

To **every patent AI startup, every legal tech platform, every LLM wrapper with a patent feature**: the era of "trust us" is ending. The era of "show us" begins now.

> **If your product is better, show the numbers.**
>
> **If your AI is accurate, prove it.**
>
> **If you will not submit to independent evaluation, ask yourself why, and know that your customers will ask the same question.**

---

## IX. A Note on What We Owe

Patent attorneys are fiduciaries. They owe a duty of candor to the USPTO and a duty of competence to their clients. When an attorney relies on an AI tool to draft claim amendments or construct arguments, that tool becomes part of the attorney's professional obligation. The attorney is staking their license on the AI's output.

Those attorneys deserve to know, with data, not marketing, how reliable that output is. They deserve benchmarks built by practitioners who understand what competent prosecution looks like. They deserve transparency.

The Stanford hallucination study proved that even $650 million acquisitions can produce tools that fabricate one in six responses. In a profession where a single fabrication can constitute fraud on the patent office, "pretty good most of the time" is not a standard. It is a liability.

PatentBench exists because the patent prosecution profession deserves better than trust. It deserves proof.

---

## X. Join Us

PatentBench is not a product. It is an open standard for an industry that has operated without one.

If you are a **patent attorney** frustrated by vendor claims you cannot verify, advocate for benchmark-based evaluation in your firm's procurement process. Ask every vendor the same question: *What is your PatentBench score?*

If you are a **patent AI company** confident in your product, submit it for evaluation. The best marketing in the world is an independently verified top score.

If you are a **researcher** working on legal AI, build on PatentBench. Extend it. Challenge it. Make it better. That is what open standards are for.

If you are an **investor** evaluating patent AI companies, demand benchmark data before writing checks. The industry has consumed hundreds of millions of dollars in venture capital without producing a single reproducible performance metric. That should concern you.

The benchmark exists. The methodology is published. The test cases are real.

**The only question left is who is willing to be measured.**

---

<p align="center"><em>PatentBench is a project of ABIGAIL. Artificial Benchmarking & Intelligence for Grading AI in Law</em></p>

<p align="center"><strong>patentbench.org</strong> | <strong>github.com/abigail-ai/patentbench</strong></p>

<p align="center"><em>"You cannot improve what you cannot measure."</em></p>
