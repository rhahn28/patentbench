# Integrating New Systems with PatentBench

This guide explains how to evaluate any patent AI system on PatentBench, whether it's:

- **A direct-API LLM** (OpenAI, Anthropic, Google), already supported
- **A commercial patent tool** (SOLV, PatSnap, LexisNexis PatentAdvisor, Clarivate Derwent, etc.), supported via custom adapters
- **A web-only tool with no API**, supported via CSV round-trip or browser automation
- **A proprietary internal system**, supported via any of the above

Every evaluation path produces the same `results/<run_id>.json` file format, so results are directly comparable regardless of how the system was accessed.

---

## Contents

1. [Core Architecture: The Adapter Pattern](#core-architecture-the-adapter-pattern)
2. [What the Evaluator Actually Checks](#what-the-evaluator-actually-checks)
3. [Pattern 1: Direct API Integration](#pattern-1-direct-api-integration)
4. [Pattern 2: CSV Round-Trip (No-Code Option)](#pattern-2-csv-round-trip-no-code-option)
5. [Pattern 3: Browser Automation (UI-Only Tools)](#pattern-3-browser-automation-ui-only-tools)
6. [Schema Translation Reference](#schema-translation-reference)
7. [Submitting Results to the Leaderboard](#submitting-results-to-the-leaderboard)
8. [FAQ](#faq)

---

## Core Architecture: The Adapter Pattern

PatentBench's benchmark runner doesn't care how a response is produced, it only cares about the text that comes back. Every "model" conforms to one interface:

```python
class BaseModelAdapter:
    def generate(self, prompt: str) -> str:
        """Take a text prompt. Return a text response."""

    def is_available(self) -> bool:
        """Return True if the system is reachable/authenticated."""
```

That's the entire contract. The `generate()` method can:

- Call a REST API
- Query a SOAP endpoint
- Drive a browser with Playwright
- Look up a cached response from a CSV
- Shell out to a CLI tool
- Do it by hand (return a human-entered string)

As long as it returns text containing the answer, the evaluator can score it.

---

## What the Evaluator Actually Checks

The evaluator reads the model's text output and looks for specific substrings or patterns that match the reference answer. **This is crucial for adapter design**, your adapter's job is to produce text containing these signals, not to match any particular format.

| Task Type | Evaluator Looks For |
|-----------|---------------------|
| `deadline_calculation` | ISO dates (`2024-06-15`), US dates (`6/15/2024`), or written dates (`June 15, 2024`) |
| `fee_computation` | Dollar amounts as integers or decimals (`320`, `320.00`, `$320`) |
| `entity_status` | Words `micro`, `small`, `large` |
| `action_classification` | Strings `Final`, `Non-Final`, `true`, `false` |
| `examiner_extraction` | Examiner name as substring |
| `timeline_analysis` | Event counts and date values as substrings |
| `oa_parsing` | USPTO rejection codes (`103`, `112(b)`) and claim numbers (`claim 5`) |
| `prosecution_history_parsing` | Event dates and status strings |
| `prosecution_strategy` | Strategy keywords (`appeal`, `rce`, `amend`, `respond`) |
| `technology_center_classification` | TC identifier substring |
| `103_argument` / `101/102/112_argument` | LLM-judge scoring (rubric-based, not substring matching) |
| Fallback (`_check_generic`) | Any string value from the reference that's 2+ characters |

Since the evaluator does **substring containment**, your adapter has enormous flexibility. If a commercial tool returns a PDF report, extract the key facts and concatenate them into a sentence. The evaluator will find them.

---

## Pattern 1: Direct API Integration

Use this when the system has any kind of network-accessible API. REST, GraphQL, gRPC, SOAP, whatever.

### 1.1 Built-in Adapters

Already supported:

```bash
patentbench --model openai:gpt-4o --subset mini
patentbench --model anthropic:claude-sonnet-4-5 --subset mini
patentbench --model google:gemini-2.5-pro --subset mini
patentbench --model abigail --api-key YOUR_KEY --subset mini
```

### 1.2 Writing a Custom Adapter

Create `patentbench/models/your_adapter.py`:

```python
"""Adapter for <your system name>."""

from __future__ import annotations

import os
import re
import httpx

from patentbench.models.base import BaseModelAdapter


class YourSystemAdapter(BaseModelAdapter):
    """Adapter for <Your System>.

    Translates PatentBench text prompts into the system's native
    API schema and converts structured responses back to text.
    """

    model_name = "your-system-v1"

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        self.api_key = api_key or os.environ.get("YOUR_API_KEY", "")
        self.endpoint = endpoint or "https://api.yoursystem.com"

    def generate(self, prompt: str) -> str:
        """Translate prompt -> API call -> text response."""

        # Step 1: Parse the prompt to extract structured inputs
        params = self._parse_prompt(prompt)

        # Step 2: Call the system's actual API
        response = httpx.post(
            f"{self.endpoint}/v1/analyze",
            json=params,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        # Step 3: Render the structured response as text for the evaluator
        return self._render(data)

    def is_available(self) -> bool:
        return bool(self.api_key)

    # ---- helpers ----

    def _parse_prompt(self, prompt: str) -> dict:
        """Extract structured fields from the prompt text."""
        params = {"query": prompt}

        app_match = re.search(r"application (\d+)", prompt)
        if app_match:
            params["application_number"] = app_match.group(1)

        date_match = re.search(r"mailed on (\d{4}-\d{2}-\d{2})", prompt)
        if date_match:
            params["mail_date"] = date_match.group(1)

        if "Non-Final" in prompt:
            params["oa_type"] = "non_final"
        elif "Final" in prompt:
            params["oa_type"] = "final"

        return params

    def _render(self, data: dict) -> str:
        """Convert structured API response to prose the evaluator can score.

        Include every fact from the response that might match reference
        fields. Extra text is harmless; missing facts cost points.
        """
        parts = []

        if "statutory_deadline" in data:
            parts.append(f"The statutory response deadline is {data['statutory_deadline']}.")
        if "max_deadline" in data:
            parts.append(f"The maximum statutory deadline is {data['max_deadline']}.")
        if "entity_status" in data:
            parts.append(f"Entity status: {data['entity_status']}.")
        if "fee" in data:
            parts.append(f"Fee: ${data['fee']}.")
        if "examiner" in data:
            parts.append(f"Examiner: {data['examiner']}.")
        if "technology_center" in data:
            parts.append(f"Technology Center: {data['technology_center']}.")

        return "\n".join(parts)
```

### 1.3 Register and Use

Add to `patentbench/models/__init__.py`:

```python
from patentbench.models.your_adapter import YourSystemAdapter
```

Run programmatically:

```python
from patentbench.models.your_adapter import YourSystemAdapter
from patentbench import BenchmarkRunner
from patentbench.harness import BenchmarkConfig

model = YourSystemAdapter(api_key="sk-...")
config = BenchmarkConfig(subset="mini", max_cases=10, run_llm_judge=False)
runner = BenchmarkRunner(model=model, data_dir="data", config=config)
results = runner.run()
print(results.summary())
results.save("results/your_system_mini.json")
```

Or add a dispatcher entry in `scripts/run_benchmark.py` so the CLI recognizes it:

```bash
patentbench --model yoursystem --subset mini
```

### 1.4 Real-World Examples

**Commercial tool with REST API** (e.g., PatSnap Insights, Derwent):

```python
params = self._parse_prompt(prompt)
r = httpx.post(f"{self.endpoint}/insights/deadline",
               json={"application": params["application_number"]},
               headers={"X-API-Key": self.api_key})
return self._render(r.json())
```

**Tool with GraphQL** (some LegalTech platforms):

```python
query = '''query($app: String!) {
    application(number: $app) {
        nextDeadline { date maxDate }
        entityStatus
    }
}'''
r = httpx.post(self.endpoint, json={"query": query, "variables": {"app": app_num}})
data = r.json()["data"]["application"]
```

**Tool with per-task endpoints** (some SaaS patent tools):

```python
task_type = self._classify_prompt(prompt)  # "deadline" | "fee" | "classify"
endpoint_map = {
    "deadline": "/api/v2/deadlines/calculate",
    "fee":      "/api/v2/fees/lookup",
    "classify": "/api/v2/actions/classify",
}
r = httpx.post(self.endpoint + endpoint_map[task_type], json=params, ...)
```

---

## Pattern 2: CSV Round-Trip (No-Code Option)

Use this when:

- The tool has no API at all
- You need manual human-in-the-loop evaluation
- You want to evaluate a system you have limited access to
- You're running a pilot before investing in automation

### 2.1 Export Prompts

Run this script to generate a CSV of prompts:

```python
# scripts/export_prompts.py
import csv
from patentbench.data_loader import DataLoader

cases = DataLoader("data/mini").load_all()

with open("prompts_to_run.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "domain", "tier", "task_type", "prompt", "response"])
    for c in cases:
        w.writerow([c.id, c.domain.value, c.tier.value, c.task_type, c.prompt, ""])

print(f"Exported {len(cases)} prompts to prompts_to_run.csv")
```

### 2.2 Fill the CSV

A human operator (or team) runs each prompt through the target tool's UI and pastes the response into the `response` column. This can be parallelized across multiple operators.

### 2.3 Score the Filled CSV

```python
# scripts/score_from_csv.py
import csv, json
from pathlib import Path
from datetime import datetime
from patentbench.data_loader import DataLoader
from patentbench.evaluator import DeterministicEvaluator
from patentbench.harness import BenchmarkResults
from patentbench.config import EvaluationLayer

ev = DeterministicEvaluator()
cases_by_id = {c.id: c for c in DataLoader("data/mini").load_all()}

results = []
with open("responses_from_tool.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if not row["response"].strip():
            continue
        case = cases_by_id.get(row["id"])
        if not case:
            continue
        r = ev.evaluate(case, row["response"])
        results.append((case, r))

# Aggregate and build a standard results file
passed = sum(1 for _, r in results if r.passed)
n = len(results)
print(f"Pass rate: {passed}/{n} = {passed/n:.1%}")

# Produce a standard BenchmarkResults JSON so it matches API-based runs
by_domain: dict[str, list[float]] = {}
by_tier: dict[int, list[float]] = {}
for c, r in results:
    by_domain.setdefault(c.domain.value, []).append(r.layer_scores.get("deterministic", 0))
    by_tier.setdefault(c.tier.value, []).append(r.layer_scores.get("deterministic", 0))

out = BenchmarkResults(
    model_name="your-tool-name-manual-csv",
    run_id=f"csv_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
    timestamp=datetime.utcnow().isoformat(),
    overall_score=(passed / n) * 100 if n else 0,
    pass_rate=passed / n if n else 0,
    total_cases=n,
    domain_scores={d: (sum(s) / len(s)) * 100 for d, s in by_domain.items()},
    tier_scores={t: (sum(s) / len(s)) * 100 for t, s in by_tier.items()},
    case_results=[{"case_id": c.id, "composite_score": r.composite_score,
                    "passed": r.passed} for c, r in results],
)
out.save(Path("results") / f"{out.run_id}_csv.json")
print(out.summary())
```

Output goes to `results/csv_<timestamp>_csv.json`, same format as API-based runs, so it's directly comparable on the leaderboard.

---

## Pattern 3: Browser Automation (UI-Only Tools)

Use this when the tool has no API but you want full automation instead of manual CSV work.

Requires Playwright: `pip install playwright && playwright install chromium`

```python
# patentbench/models/ui_adapter.py
from playwright.sync_api import sync_playwright
from patentbench.models.base import BaseModelAdapter


class BrowserDrivenAdapter(BaseModelAdapter):
    """Drive a web UI to get responses.

    This is the most fragile integration. It depends on the target
    site's HTML structure. Expect to update selectors periodically.
    """

    model_name = "browser-driven-tool"

    def __init__(self, url: str, username: str, password: str, headless: bool = True):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless)
        self._page = self._browser.new_page()

        # Login flow
        self._page.goto(f"{url}/login")
        self._page.fill("input[name='email']", username)
        self._page.fill("input[name='password']", password)
        self._page.click("button[type='submit']")
        self._page.wait_for_url("**/dashboard", timeout=30000)

        self._query_url = f"{url}/query"

    def generate(self, prompt: str) -> str:
        self._page.goto(self._query_url)
        self._page.fill("textarea[name='query']", prompt)
        self._page.click("button#submit")
        # Wait for response to render
        self._page.wait_for_selector(".response-text", timeout=120000)
        return self._page.inner_text(".response-text")

    def is_available(self) -> bool:
        try:
            self._page.goto(self._query_url, timeout=10000)
            return True
        except Exception:
            return False

    def __del__(self):
        try:
            self._browser.close()
            self._pw.stop()
        except Exception:
            pass
```

Use it like any other adapter:

```python
from patentbench.models.ui_adapter import BrowserDrivenAdapter
model = BrowserDrivenAdapter(url="https://tool.example.com",
                              username="me@firm.com",
                              password="...")
```

### Tips for Browser Automation

- **Rate-limit yourself**: Add `time.sleep(1-3)` between queries to avoid tripping anti-bot protections
- **Handle captchas**: If the tool shows captchas, you'll need manual intervention
- **Respect Terms of Service**: Check that benchmarking via automation is permitted
- **Session expiry**: Add logic to re-login when sessions expire
- **Screenshot on failure**: `self._page.screenshot(path="error.png")` helps debugging

---

## Schema Translation Reference

### How the Prompts Are Structured

Every PatentBench prompt is a self-contained question containing all the context the system needs. Example prompts:

```
A Non-Final Office Action was mailed on 2020-08-27 for application 16100000.
What is the shortened statutory response deadline and the maximum statutory deadline?
```

```
For USPTO application 17500017 (Art Unit 2433), who is the assigned examiner?
```

```
Analyze the prosecution timeline for application 16100000. How many total
prosecution events are recorded, what were the first and last event dates,
and how many Office Actions were issued?
```

Your adapter's `_parse_prompt()` needs to extract structured fields (application number, dates, task intent) from this text.

### How Reference Answers Are Structured

Most reference answers are JSON strings wrapping structured data:

```json
{
  "shortened_deadline": "2020-11-27",
  "max_deadline": "2021-02-27",
  "action_type": "Non-Final",
  "explanation": "Non-Final OA: 3 months shortened period..."
}
```

The evaluator parses this JSON, then looks for each value as a substring in your adapter's output text.

### Minimum Output Format

For a deadline task, this is sufficient:

```
2020-11-27 2021-02-27
```

Two dates on the page. The evaluator extracts both and matches them. But more readable output is fine:

```
For application 16100000, the shortened statutory response deadline is
2020-11-27 (three months from the 2020-08-27 mail date), and the maximum
statutory deadline with extensions is 2021-02-27 (six months).
```

Both score identically. Prefer readable output, it makes debugging easier.

### Key Rule: Include Dates in Multiple Formats if Unsure

If your system returns a date in a non-standard format, include both:

```python
# System returned "27 November 2020" which the evaluator won't parse
text = f"The deadline is 27 November 2020, i.e. 2020-11-27."
#                                              ^^^^^^^^^^^ evaluator catches this
```

---

## Submitting Results to the Leaderboard

Once you have a `results/run_*.json` file:

1. **Verify the result file is complete**: it should contain `overall_score`, `domain_scores`, `tier_scores`, `layer_scores`, and `case_results`.

2. **Run the full `mini` subset** (300 cases) at minimum. Partial runs won't be comparable.

3. **Document your methodology**:
 - What system version was tested?
 - Which adapter pattern (API / CSV / browser)?
 - Any special configuration (temperature, model size, etc.)?
 - Date range of the evaluation?

4. **Open a pull request** adding your results:
 - Your results file: `results/your-system-name_YYYY-MM-DD.json`
 - An entry in the leaderboard table in `README.md`
 - A methodology note in the PR description

5. **For reproducibility**:
 - If it's API-based: share your adapter source code (minus the API key)
 - If it's CSV-based: share the CSV files so scores can be recomputed
 - If it's browser-based: share the selector config and a note about site version tested

---

## FAQ

### Q: My tool only handles one task type (e.g., only deadline calculation). Can I still benchmark?

Yes. Filter the benchmark to just that task:

```bash
patentbench --model yourtool --subset mini \
    --domain administration --tier 1
```

Or in Python:

```python
cases = DataLoader("data/mini").load(task_type="deadline_calculation")
```

Your score will only cover that slice, and you should document the scope in your leaderboard submission.

### Q: My tool returns a PDF report, not text. How do I score that?

Your adapter's `generate()` should extract text from the PDF. Use `pypdf` or `pdfplumber`:

```python
def generate(self, prompt: str) -> str:
    pdf_bytes = self._call_tool(prompt)  # returns PDF
    import pypdf, io
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)
```

The evaluator only cares about the text.

### Q: My tool returns structured JSON with different field names. Do I rename?

Don't rename. In your `_render()` method, just format the values into text:

```python
def _render(self, data: dict) -> str:
    # data might be {"dueDate": "2024-06-15", "maxDueDate": "2024-09-15"}
    # The evaluator looks for date SUBSTRINGS, not field names
    return f"Response due: {data['dueDate']}. Max: {data['maxDueDate']}."
```

### Q: What if the tool refuses to answer certain questions?

Return the refusal as-is. The evaluator will score 0 for that case. This is legitimate behavior to measure.

```python
def generate(self, prompt: str) -> str:
    try:
        return self._call_api(prompt)
    except ToolRefusedError as e:
        return f"System declined to respond: {e}"
```

### Q: Does PatentBench prevent my tool from cheating (memorizing test cases)?

Partially. The benchmark includes poison-pill MPEP citations and fabricated case law that only appear in test data, a system that's memorized the benchmark will leak these signals. See [METHODOLOGY.md](METHODOLOGY.md) for the full anti-contamination protocol.

### Q: Can I run the benchmark against a local/offline LLM?

Yes. Use the base adapter pattern with any inference library:

```python
from transformers import AutoTokenizer, AutoModelForCausalLM

class LocalLLMAdapter(BaseModelAdapter):
    model_name = "local-llama3"

    def __init__(self, model_path: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(model_path)

    def generate(self, prompt: str) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(**inputs, max_new_tokens=1024)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def is_available(self) -> bool:
        return True
```

### Q: How long does a full benchmark run take?

- **Mini (300 cases)**: 10-30 minutes depending on API latency
- **Full (7,200 cases)**: 4-12 hours for a direct API, days for browser-driven

You can parallelize by running different domain/tier slices concurrently.

### Q: Can I evaluate on cached/pre-computed responses?

Yes. Write an adapter that reads from a local cache:

```python
class CachedResponseAdapter(BaseModelAdapter):
    model_name = "cached"

    def __init__(self, cache_file: str):
        import json
        with open(cache_file) as f:
            self.cache = {r["id"]: r["response"] for r in json.load(f)}

    def generate(self, prompt: str) -> str:
        # Fallback: match by prompt hash
        import hashlib
        key = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return self.cache.get(key, "")

    def is_available(self) -> bool:
        return bool(self.cache)
```

This is useful for re-scoring runs with updated evaluation code without re-calling expensive APIs.

---

## Need Help?

- **Adapter not working?** File an issue at https://github.com/rhahn28/patentbench/issues with your adapter code and the error.
- **Schema questions?** Check [METHODOLOGY.md](METHODOLOGY.md) for detailed evaluator logic.
- **Leaderboard submission?** See the submission guide in [CONTRIBUTING.md](CONTRIBUTING.md).
