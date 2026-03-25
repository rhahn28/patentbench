/**
 * PatentBench Multi-Model Benchmark Runner
 *
 * Runs Tier 1-2 benchmark test cases against multiple models (Sonnet, GPT-4o, Gemini),
 * then scores responses using the same scoring logic as score_benchmark.js.
 *
 * Usage:
 *   node run_multi_model_benchmark.js --model=sonnet
 *   node run_multi_model_benchmark.js --model=gpt4o
 *   node run_multi_model_benchmark.js --model=gemini
 *
 * Environment variables:
 *   ANTHROPIC_API_KEY  - Required for --model=sonnet
 *   OPENAI_API_KEY     - Required for --model=gpt4o
 *   GOOGLE_API_KEY     - Required for --model=gemini
 *
 * Requires Node 18+ (native fetch).
 * No external dependencies.
 */

const fs = require('fs');
const path = require('path');

// ========== CONFIGURATION ==========

const DATA_FILE = path.join(__dirname, '..', 'data', 'benchmark_cases_tier1_2.json');
const MAX_CONCURRENT = 5;
const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

const MODEL_CONFIGS = {
  sonnet: {
    displayName: 'Claude Sonnet (claude-sonnet-4-20250514)',
    modelId: 'claude-sonnet-4-20250514',
    provider: 'anthropic',
    envKey: 'ANTHROPIC_API_KEY',
    endpoint: 'https://api.anthropic.com/v1/messages',
  },
  gpt4o: {
    displayName: 'GPT-4o',
    modelId: 'gpt-4o',
    provider: 'openai',
    envKey: 'OPENAI_API_KEY',
    endpoint: 'https://api.openai.com/v1/chat/completions',
  },
  gemini: {
    displayName: 'Gemini 2.5 Flash',
    modelId: 'gemini-2.5-flash',
    provider: 'google',
    envKey: 'GOOGLE_API_KEY',
    endpointTemplate: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
  },
};

// ========== SYSTEM PROMPTS BY TASK TYPE ==========
// Identical across all models for fair comparison.

const SYSTEM_PROMPTS = {
  deadline_calculation: `You are an expert U.S. patent attorney. You will be given a question about patent prosecution deadlines.

Respond ONLY with a JSON object (no markdown, no explanation, no code fences). The JSON must have exactly these fields:

{
  "shortened_deadline": "YYYY-MM-DD",
  "max_deadline": "YYYY-MM-DD",
  "action_type": "Non-Final" or "Final",
  "legal_basis": "string citing the relevant CFR/USC sections"
}

If the Office Action is a Final Office Action, also include:
{
  "options": ["array of strings describing applicant's options after Final Rejection"]
}

Rules:
- Non-Final Office Action: shortened statutory period = 3 months from mail date; maximum = 6 months from mail date.
- Final Office Action: shortened statutory period = 3 months from mail date; maximum = 6 months from mail date.
- After a Final Rejection, the applicant's options include: filing a response with amendments under 37 CFR 1.116, filing an RCE under 37 CFR 1.114, filing a Notice of Appeal under 37 CFR 41.31, requesting an interview with the examiner, and filing a continuation application.
- Use 37 CFR 1.134 and 35 USC 133 as the legal basis.`,

  action_classification: `You are an expert U.S. patent attorney. You will be given a list of prosecution history events (as a JSON array with "code", "description", and "date" fields) and asked to classify them.

Respond ONLY with a JSON object (no markdown, no explanation, no code fences). The JSON must have exactly these fields:

{
  "has_non_final": true/false,
  "has_final": true/false,
  "has_allowance": true/false,
  "total_oa_rounds": number
}

Rules:
- "has_non_final" is true if any event code is "CTNF" or "MCTNF" (Non-Final Rejection).
- "has_final" is true if any event code is "CTFR" or "MCTFR" (Final Rejection).
- "has_allowance" is true if any event code is "NOA", "CNOA", or "MCNOA" (Notice of Allowance).
- "total_oa_rounds" = count of distinct OA types present (1 if only non-final OR only final, 2 if both non-final AND final, 0 if neither).`,

  fee_computation: `You are an expert U.S. patent attorney. You will be asked to compute USPTO fees for a given entity status.

Respond ONLY with a JSON object (no markdown, no explanation, no code fences). The JSON must have exactly these fields:

{
  "extension_1_month": number,
  "rce_fee": number,
  "issue_fee": number
}

Use the current USPTO fee schedule (effective January 18, 2025):

Large entity:
  - 1-month extension of time: $240
  - RCE filing fee: $2,280
  - Issue fee: $1,200

Small entity (50% of large):
  - 1-month extension of time: $120
  - RCE filing fee: $1,140
  - Issue fee: $600

Micro entity (25% of large):
  - 1-month extension of time: $60
  - RCE filing fee: $570
  - Issue fee: $300`,

  timeline_analysis: `You are an expert U.S. patent attorney. You will be given a list of prosecution history events (as a JSON array with "code", "description", and "date" fields) and asked to analyze the timeline.

Respond ONLY with a JSON object (no markdown, no explanation, no code fences). The JSON must have exactly these fields:

{
  "total_events": number,
  "first_event_date": "YYYY-MM-DD",
  "last_event_date": "YYYY-MM-DD",
  "prosecution_duration_days": number
}

Rules:
- "total_events" is the count of events in the array.
- "first_event_date" is the earliest date among all events.
- "last_event_date" is the latest date among all events.
- "prosecution_duration_days" is the number of days between the first and last event dates (last - first, as a whole number).`,
};

// ========== API CALLERS ==========

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function callWithRetry(fn, retries = MAX_RETRIES) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const isLast = attempt === retries;
      const isRetryable = err.status === 429 || err.status === 500 || err.status === 503 || err.code === 'ECONNRESET' || err.code === 'ETIMEDOUT';

      if (isLast || !isRetryable) {
        throw err;
      }

      const delay = BASE_DELAY_MS * Math.pow(2, attempt) + Math.random() * 500;
      console.error(`  Retry ${attempt + 1}/${retries} after ${Math.round(delay)}ms (${err.status || err.code || err.message})`);
      await sleep(delay);
    }
  }
}

async function callAnthropic(apiKey, systemPrompt, userPrompt) {
  const config = MODEL_CONFIGS.sonnet;
  const res = await fetch(config.endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: config.modelId,
      max_tokens: 4096,
      temperature: 0,
      system: systemPrompt,
      messages: [{ role: 'user', content: userPrompt }],
    }),
  });

  if (!res.ok) {
    const err = new Error(`Anthropic API error: ${res.status}`);
    err.status = res.status;
    err.body = await res.text().catch(() => '');
    throw err;
  }

  const data = await res.json();
  return data.content.map(b => b.text).join('\n');
}

async function callOpenAI(apiKey, systemPrompt, userPrompt) {
  const config = MODEL_CONFIGS.gpt4o;
  const res = await fetch(config.endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: config.modelId,
      max_tokens: 4096,
      temperature: 0,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt },
      ],
    }),
  });

  if (!res.ok) {
    const err = new Error(`OpenAI API error: ${res.status}`);
    err.status = res.status;
    err.body = await res.text().catch(() => '');
    throw err;
  }

  const data = await res.json();
  return data.choices[0].message.content || '';
}

async function callGemini(apiKey, systemPrompt, userPrompt) {
  const config = MODEL_CONFIGS.gemini;
  const url = `${config.endpointTemplate}?key=${apiKey}`;

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      system_instruction: {
        parts: [{ text: systemPrompt }],
      },
      contents: [{
        parts: [{ text: userPrompt }],
      }],
      generationConfig: {
        temperature: 0,
        maxOutputTokens: 4096,
      },
    }),
  });

  if (!res.ok) {
    const err = new Error(`Gemini API error: ${res.status}`);
    err.status = res.status;
    err.body = await res.text().catch(() => '');
    throw err;
  }

  const data = await res.json();
  return data.candidates?.[0]?.content?.parts?.map(p => p.text).join('\n') || '';
}

// ========== RESPONSE PARSER ==========

function parseJsonResponse(rawText) {
  // Strip markdown code fences if present
  let text = rawText.trim();
  text = text.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '');
  text = text.trim();

  // Try to find a JSON object in the text
  const firstBrace = text.indexOf('{');
  const lastBrace = text.lastIndexOf('}');
  if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
    text = text.substring(firstBrace, lastBrace + 1);
  }

  try {
    return JSON.parse(text);
  } catch (e) {
    return { _parse_error: true, _raw: rawText.substring(0, 500) };
  }
}

// ========== SCORING FUNCTIONS (from score_benchmark.js) ==========

function scoreDeadline(response, groundTruth) {
  let score = 0;
  let maxScore = 0;
  const details = [];

  maxScore += 1;
  if (response.shortened_deadline === groundTruth.shortened_deadline) {
    score += 1;
    details.push('shortened_deadline: CORRECT');
  } else {
    details.push(`shortened_deadline: WRONG (got ${response.shortened_deadline}, expected ${groundTruth.shortened_deadline})`);
  }

  maxScore += 1;
  if (response.max_deadline === groundTruth.max_deadline) {
    score += 1;
    details.push('max_deadline: CORRECT');
  } else {
    details.push(`max_deadline: WRONG (got ${response.max_deadline}, expected ${groundTruth.max_deadline})`);
  }

  maxScore += 1;
  if (response.action_type === groundTruth.action_type) {
    score += 1;
    details.push('action_type: CORRECT');
  } else {
    details.push(`action_type: WRONG (got ${response.action_type}, expected ${groundTruth.action_type})`);
  }

  if (groundTruth.options) {
    maxScore += 1;
    const gtOpts = new Set(groundTruth.options);
    const respOpts = new Set(response.options || []);
    const overlap = [...gtOpts].filter(o => respOpts.has(o)).length;
    const optScore = overlap / gtOpts.size;
    score += optScore;
    details.push(`options: ${(optScore * 100).toFixed(0)}% coverage (${overlap}/${gtOpts.size})`);
  }

  return { score, maxScore, percentage: (score / maxScore * 100).toFixed(1), details };
}

function scoreClassification(response, groundTruth) {
  let score = 0;
  const maxScore = 4;
  const details = [];

  if (response.has_non_final === groundTruth.has_non_final) { score++; details.push('has_non_final: CORRECT'); }
  else details.push(`has_non_final: WRONG (got ${response.has_non_final}, expected ${groundTruth.has_non_final})`);

  if (response.has_final === groundTruth.has_final) { score++; details.push('has_final: CORRECT'); }
  else details.push(`has_final: WRONG (got ${response.has_final}, expected ${groundTruth.has_final})`);

  if (response.has_allowance === groundTruth.has_allowance) { score++; details.push('has_allowance: CORRECT'); }
  else details.push(`has_allowance: WRONG (got ${response.has_allowance}, expected ${groundTruth.has_allowance})`);

  if (response.total_oa_rounds === groundTruth.total_oa_rounds) { score++; details.push('total_oa_rounds: CORRECT'); }
  else details.push(`total_oa_rounds: WRONG (got ${response.total_oa_rounds}, expected ${groundTruth.total_oa_rounds})`);

  return { score, maxScore, percentage: (score / maxScore * 100).toFixed(1), details };
}

function scoreFee(response, groundTruth) {
  let score = 0;
  const maxScore = 3;
  const details = [];

  if (response.extension_1_month === groundTruth.extension_1_month) { score++; details.push('extension_fee: CORRECT'); }
  else details.push(`extension_fee: WRONG (got ${response.extension_1_month}, expected ${groundTruth.extension_1_month})`);

  if (response.rce_fee === groundTruth.rce_fee) { score++; details.push('rce_fee: CORRECT'); }
  else details.push(`rce_fee: WRONG (got ${response.rce_fee}, expected ${groundTruth.rce_fee})`);

  if (response.issue_fee === groundTruth.issue_fee) { score++; details.push('issue_fee: CORRECT'); }
  else details.push(`issue_fee: WRONG (got ${response.issue_fee}, expected ${groundTruth.issue_fee})`);

  return { score, maxScore, percentage: (score / maxScore * 100).toFixed(1), details };
}

function scoreTimeline(response, groundTruth) {
  let score = 0;
  const maxScore = 3;
  const details = [];

  if (response.total_events === groundTruth.total_events) { score++; details.push('total_events: CORRECT'); }
  else details.push(`total_events: WRONG (got ${response.total_events}, expected ${groundTruth.total_events})`);

  if (response.first_event_date === groundTruth.first_event_date) { score++; details.push('first_event: CORRECT'); }
  else details.push(`first_event: WRONG (got ${response.first_event_date}, expected ${groundTruth.first_event_date})`);

  if (response.prosecution_duration_days === groundTruth.prosecution_duration_days) { score++; details.push('duration: CORRECT'); }
  else details.push(`duration: WRONG (got ${response.prosecution_duration_days}, expected ${groundTruth.prosecution_duration_days})`);

  return { score, maxScore, percentage: (score / maxScore * 100).toFixed(1), details };
}

function scoreResponse(taskType, response, groundTruth) {
  if (response._parse_error) {
    // Couldn't parse JSON — score 0
    const maxScores = { deadline_calculation: 3, action_classification: 4, fee_computation: 3, timeline_analysis: 3 };
    const ms = maxScores[taskType] || 3;
    return { score: 0, maxScore: ms, percentage: '0.0', details: [`PARSE_ERROR: could not extract JSON from model response`] };
  }

  switch (taskType) {
    case 'deadline_calculation': return scoreDeadline(response, groundTruth);
    case 'action_classification': return scoreClassification(response, groundTruth);
    case 'fee_computation': return scoreFee(response, groundTruth);
    case 'timeline_analysis': return scoreTimeline(response, groundTruth);
    default: return { score: 0, maxScore: 0, percentage: '0.0', details: [`Unknown task type: ${taskType}`] };
  }
}

// ========== CONCURRENCY LIMITER ==========

class ConcurrencyLimiter {
  constructor(limit) {
    this.limit = limit;
    this.running = 0;
    this.queue = [];
  }

  async run(fn) {
    while (this.running >= this.limit) {
      await new Promise(resolve => this.queue.push(resolve));
    }
    this.running++;
    try {
      return await fn();
    } finally {
      this.running--;
      if (this.queue.length > 0) {
        this.queue.shift()();
      }
    }
  }
}

// ========== MAIN ==========

async function main() {
  // Parse CLI args
  const args = process.argv.slice(2);
  const modelArg = args.find(a => a.startsWith('--model='));
  if (!modelArg) {
    console.error('Usage: node run_multi_model_benchmark.js --model=sonnet|gpt4o|gemini');
    process.exit(1);
  }
  const modelName = modelArg.split('=')[1];
  if (!MODEL_CONFIGS[modelName]) {
    console.error(`Unknown model: "${modelName}". Valid options: sonnet, gpt4o, gemini`);
    process.exit(1);
  }

  const modelConfig = MODEL_CONFIGS[modelName];
  const apiKey = process.env[modelConfig.envKey];
  if (!apiKey) {
    console.error(`Missing environment variable: ${modelConfig.envKey}`);
    process.exit(1);
  }

  // Select the API caller
  const callers = {
    anthropic: (sys, user) => callAnthropic(apiKey, sys, user),
    openai: (sys, user) => callOpenAI(apiKey, sys, user),
    google: (sys, user) => callGemini(apiKey, sys, user),
  };
  const callModel = callers[modelConfig.provider];

  // Load test cases
  const data = JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
  const testCases = data.test_cases;

  console.log('='.repeat(70));
  console.log(`  PATENTBENCH MULTI-MODEL BENCHMARK`);
  console.log(`  Model: ${modelConfig.displayName}`);
  console.log(`  Test cases: ${testCases.length}`);
  console.log(`  Concurrency: ${MAX_CONCURRENT} | Retries: ${MAX_RETRIES}`);
  console.log('='.repeat(70));
  console.log('');

  const limiter = new ConcurrencyLimiter(MAX_CONCURRENT);
  const startTime = Date.now();

  let completed = 0;
  let parseErrors = 0;

  // Process all test cases concurrently (bounded)
  const resultPromises = testCases.map((test, idx) => {
    return limiter.run(async () => {
      const systemPrompt = SYSTEM_PROMPTS[test.task_type];
      if (!systemPrompt) {
        return {
          test_id: test.id,
          task_type: test.task_type,
          tier: test.tier,
          score: '0.0%',
          details: [`Unsupported task type: ${test.task_type}`],
          raw_response: '',
          parsed_response: null,
        };
      }

      let rawResponse = '';
      let parsed = { _parse_error: true };

      try {
        rawResponse = await callWithRetry(() => callModel(systemPrompt, test.question));
        parsed = parseJsonResponse(rawResponse);
        if (parsed._parse_error) parseErrors++;
      } catch (err) {
        parseErrors++;
        rawResponse = `ERROR: ${err.message}`;
        parsed = { _parse_error: true, _raw: err.message };
      }

      const scoring = scoreResponse(test.task_type, parsed, test.ground_truth);

      completed++;
      if (completed % 25 === 0 || completed === testCases.length) {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        console.log(`  Progress: ${completed}/${testCases.length} (${elapsed}s elapsed)`);
      }

      return {
        test_id: test.id,
        task_type: test.task_type,
        tier: test.tier,
        application_number: test.application_number,
        score: scoring.percentage + '%',
        score_numeric: scoring.score,
        max_score: scoring.maxScore,
        details: scoring.details,
        raw_response: rawResponse.substring(0, 2000),
        parsed_response: parsed._parse_error ? null : parsed,
      };
    });
  });

  const detailedResults = await Promise.all(resultPromises);

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  // ========== AGGREGATE RESULTS ==========

  const taskScores = {};
  const tcScores = {};

  for (const r of detailedResults) {
    // By task type
    if (!taskScores[r.task_type]) taskScores[r.task_type] = { total: 0, maxPossible: 0, count: 0 };
    taskScores[r.task_type].total += r.score_numeric;
    taskScores[r.task_type].maxPossible += r.max_score;
    taskScores[r.task_type].count++;

    // By technology center (from ground truth in original data)
    const test = testCases.find(t => t.id === r.test_id);
    const tc = test?.ground_truth?.technology_center || 'N/A';
    if (tc !== 'N/A') {
      if (!tcScores[tc]) tcScores[tc] = { total: 0, maxPossible: 0, count: 0 };
      tcScores[tc].total += r.score_numeric;
      tcScores[tc].maxPossible += r.max_score;
      tcScores[tc].count++;
    }
  }

  let totalScore = 0, totalMax = 0;
  const byTaskType = {};
  for (const [type, s] of Object.entries(taskScores)) {
    const pct = (s.total / s.maxPossible * 100).toFixed(1);
    byTaskType[type] = {
      accuracy: pct + '%',
      tests: s.count,
      points: `${s.total}/${s.maxPossible}`,
    };
    totalScore += s.total;
    totalMax += s.maxPossible;
  }

  const byTC = {};
  for (const [tc, s] of Object.entries(tcScores)) {
    byTC[tc] = {
      accuracy: (s.total / s.maxPossible * 100).toFixed(1) + '%',
      tests: s.count,
    };
  }

  const errorTests = detailedResults.filter(r => r.details.some(d => d.includes('WRONG') || d.includes('PARSE_ERROR')));
  const perfectTests = detailedResults.filter(r => r.details.every(d => d.includes('CORRECT') || d.includes('100%')));

  const results = {
    benchmark: 'PatentBench-Mini v0.1.0',
    model: modelConfig.displayName,
    model_id: modelConfig.modelId,
    provider: modelConfig.provider,
    run_date: new Date().toISOString(),
    elapsed_seconds: parseFloat(elapsed),
    summary: {
      overall_accuracy: (totalScore / totalMax * 100).toFixed(1) + '%',
      total_tests: testCases.length,
      total_points: `${totalScore}/${totalMax}`,
      tests_with_errors: errorTests.length,
      tests_perfect: perfectTests.length,
      parse_errors: parseErrors,
    },
    by_task_type: byTaskType,
    by_technology_center: byTC,
    detailed_results: detailedResults,
  };

  // Write results
  const outputFile = path.join(__dirname, '..', 'data', `benchmark_results_${modelName}.json`);
  fs.writeFileSync(outputFile, JSON.stringify(results, null, 2), 'utf-8');

  // ========== PRINT SUMMARY ==========

  console.log('');
  console.log('='.repeat(70));
  console.log(`  PATENTBENCH-MINI RESULTS - ${modelConfig.displayName}`);
  console.log('='.repeat(70));
  console.log(`\n  Overall Accuracy: ${results.summary.overall_accuracy}`);
  console.log(`  Total Tests: ${results.summary.total_tests}`);
  console.log(`  Perfect Scores: ${results.summary.tests_perfect}/${results.summary.total_tests}`);
  console.log(`  Tests with Errors: ${results.summary.tests_with_errors}/${results.summary.total_tests}`);
  console.log(`  Parse Errors: ${results.summary.parse_errors}`);
  console.log(`  Elapsed: ${elapsed}s`);

  console.log('\n  BY TASK TYPE:');
  for (const [type, s] of Object.entries(results.by_task_type)) {
    console.log(`    ${type.padEnd(25)} ${s.accuracy.padStart(6)}  (${s.tests} tests, ${s.points})`);
  }

  console.log('\n  BY TECHNOLOGY CENTER:');
  for (const [tc, s] of Object.entries(results.by_technology_center)) {
    console.log(`    ${tc.padEnd(25)} ${s.accuracy.padStart(6)}  (${s.tests} tests)`);
  }

  // Show errors
  if (errorTests.length > 0) {
    console.log(`\n  ERRORS (${errorTests.length} tests):`);
    for (const e of errorTests.slice(0, 10)) {
      const wrongDetails = e.details.filter(d => d.includes('WRONG') || d.includes('PARSE_ERROR'));
      console.log(`    ${e.test_id}: ${wrongDetails.join(', ')}`);
    }
    if (errorTests.length > 10) console.log(`    ... and ${errorTests.length - 10} more`);
  }

  console.log(`\n  Output: ${outputFile}`);
  console.log('='.repeat(70));
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
