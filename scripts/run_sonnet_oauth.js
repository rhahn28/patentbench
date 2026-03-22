/**
 * PatentBench Sonnet Benchmark Runner — Uses Claude CLI OAuth
 *
 * Runs each test case through `claude -p --model sonnet` which uses the
 * user's Pro Max OAuth subscription. Zero API cost.
 *
 * Sequential processing — one request at a time to be safe with rate limits.
 * Saves progress after each test so it can be resumed if interrupted.
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const DATA_FILE = path.join(__dirname, '..', 'data', 'benchmark_cases_tier1_2.json');
const OUTPUT_FILE = path.join(__dirname, '..', 'data', 'benchmark_results_sonnet.json');
const PROGRESS_FILE = path.join(__dirname, '..', 'data', '_sonnet_progress.json');

const SYSTEM_PROMPTS = {
  deadline_calculation: `You are a U.S. patent attorney. Respond ONLY with a JSON object (no markdown, no code fences, no explanation). Fields:
{"shortened_deadline":"YYYY-MM-DD","max_deadline":"YYYY-MM-DD","action_type":"Non-Final" or "Final","legal_basis":"string"}
If Final, add: "options":["array of applicant options after Final Rejection"]
Rules: shortened = 3 months from mail date. maximum = 6 months from mail date. Use end-of-month clamping (e.g. Aug 31 + 3 months = Nov 30). Basis: 37 CFR 1.134 + 35 USC 133.`,

  action_classification: `You are a U.S. patent attorney. Given prosecution events, respond ONLY with JSON (no markdown, no code fences):
{"has_non_final":bool,"has_final":bool,"has_allowance":bool,"total_oa_rounds":number}
Event codes: CTNF/MCTNF=Non-Final, CTFR/MCTFR=Final, NOA/CNOA/MCNOA=Allowance. total_oa_rounds = count of Non-Final + Final actions.`,

  fee_computation: `You are a U.S. patent attorney. Respond ONLY with JSON (no markdown, no code fences):
{"extension_1_month":number,"rce_fee":number,"issue_fee":number}
2025 USPTO fees: large entity(extension_1_month=240, rce=2280, issue=1200), small(120/1140/600), micro(60/570/300). Determine entity size from the question context.`,

  timeline_analysis: `You are a U.S. patent attorney. Given prosecution events, respond ONLY with JSON (no markdown, no code fences):
{"total_events":number,"first_event_date":"YYYY-MM-DD","last_event_date":"YYYY-MM-DD","prosecution_duration_days":number}
total_events = count of ALL events listed. Duration = days between first and last event dates (simple subtraction).`,
};

function parseJsonResponse(rawText) {
  let text = rawText.trim();
  // Strip markdown code fences
  text = text.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '');
  text = text.trim();
  // Extract JSON object
  const firstBrace = text.indexOf('{');
  const lastBrace = text.lastIndexOf('}');
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    text = text.substring(firstBrace, lastBrace + 1);
  }
  try { return JSON.parse(text); }
  catch { return { _parse_error: true, _raw: rawText.substring(0, 300) }; }
}

function callClaude(systemPrompt, question) {
  const fullPrompt = `${systemPrompt}\n\nQuestion: ${question}`;
  // Write prompt to temp file to avoid shell escaping issues
  const tmpFile = path.join(__dirname, '..', 'data', '_tmp_prompt.txt');
  fs.writeFileSync(tmpFile, fullPrompt, 'utf-8');

  try {
    const result = execSync(
      `cat "${tmpFile.replace(/\\/g, '/')}" | claude -p --model sonnet --no-session-persistence`,
      {
        encoding: 'utf-8',
        timeout: 120000, // 2 min timeout
        maxBuffer: 1024 * 1024,
        stdio: ['pipe', 'pipe', 'pipe'],
      }
    );
    return result.trim();
  } finally {
    try { fs.unlinkSync(tmpFile); } catch {}
  }
}

// Fuzzy option matching — each ground truth option has key phrases
const OPTION_KEYWORDS = {
  'File response with amendments under 37 CFR 1.116': ['1.116', 'amendment'],
  'File RCE under 37 CFR 1.114': ['1.114', 'RCE', 'continued examination'],
  'File Notice of Appeal under 37 CFR 41.31': ['appeal', '41.31'],
  'Request interview with examiner': ['interview'],
  'File continuation application': ['continuation'],
};

function matchesOption(gtOption, respOptions) {
  const keywords = OPTION_KEYWORDS[gtOption];
  if (!keywords) return respOptions.some(r => r.toLowerCase().includes(gtOption.toLowerCase()));
  const joined = respOptions.map(r => r.toLowerCase()).join(' ');
  return keywords.some(kw => joined.includes(kw.toLowerCase()));
}

let debuggedOnce = false, debuggedOpts = false;
function scoreDeadline(resp, gt) {
  let s = 0, m = 0, d = [];
  m++; if (resp.shortened_deadline === gt.shortened_deadline) { s++; d.push('shortened: OK'); } else d.push(`shortened: ${resp.shortened_deadline} vs ${gt.shortened_deadline} WRONG`);
  m++; if (resp.max_deadline === gt.max_deadline) { s++; d.push('max: OK'); } else d.push(`max: ${resp.max_deadline} vs ${gt.max_deadline} WRONG`);
  m++; if (resp.action_type === gt.action_type) { s++; d.push('type: OK'); } else d.push(`type: ${resp.action_type} vs ${gt.action_type} WRONG`);
  if (gt.options) {
    m++;
    const respOpts = resp.options || [];
    if (respOpts.length === 0 && !debuggedOnce) {
      debuggedOnce = true;
      console.log('\n  DEBUG: resp.options is empty. Full resp keys:', Object.keys(resp));
      console.log('  DEBUG: resp type:', typeof resp, 'parse_error:', resp._parse_error);
    }
    const matched = gt.options.filter(gtOpt => matchesOption(gtOpt, respOpts));
    if (matched.length < gt.options.length && !debuggedOpts) {
      debuggedOpts = true;
      console.log(`\n  DEBUG options: resp has ${respOpts.length} opts, matched ${matched.length}/${gt.options.length}`);
      respOpts.forEach((o,i) => console.log(`    resp[${i}]: ${o.substring(0,80)}`));
      gt.options.forEach(g => console.log(`    gt: ${g} => ${matchesOption(g, respOpts)}`));
    }
    s += matched.length / gt.options.length;
    d.push(`options: ${matched.length}/${gt.options.length}`);
  }
  return { score: s, maxScore: m, percentage: (s/m*100).toFixed(1), details: d };
}

function scoreClassification(resp, gt) {
  let s = 0, d = [];
  if (resp.has_non_final === gt.has_non_final) { s++; d.push('nf: OK'); } else d.push('nf: WRONG');
  if (resp.has_final === gt.has_final) { s++; d.push('f: OK'); } else d.push('f: WRONG');
  if (resp.has_allowance === gt.has_allowance) { s++; d.push('allow: OK'); } else d.push('allow: WRONG');
  if (resp.total_oa_rounds === gt.total_oa_rounds) { s++; d.push('rounds: OK'); } else d.push(`rounds: ${resp.total_oa_rounds} vs ${gt.total_oa_rounds} WRONG`);
  return { score: s, maxScore: 4, percentage: (s/4*100).toFixed(1), details: d };
}

function scoreFee(resp, gt) {
  let s = 0, d = [];
  if (resp.extension_1_month === gt.extension_1_month) { s++; d.push('ext: OK'); } else d.push(`ext: ${resp.extension_1_month} vs ${gt.extension_1_month} WRONG`);
  if (resp.rce_fee === gt.rce_fee) { s++; d.push('rce: OK'); } else d.push(`rce: ${resp.rce_fee} vs ${gt.rce_fee} WRONG`);
  if (resp.issue_fee === gt.issue_fee) { s++; d.push('issue: OK'); } else d.push(`issue: ${resp.issue_fee} vs ${gt.issue_fee} WRONG`);
  return { score: s, maxScore: 3, percentage: (s/3*100).toFixed(1), details: d };
}

function scoreTimeline(resp, gt) {
  let s = 0, d = [];
  if (resp.total_events === gt.total_events) { s++; d.push('events: OK'); } else d.push(`events: ${resp.total_events} vs ${gt.total_events} WRONG`);
  if (resp.first_event_date === gt.first_event_date) { s++; d.push('first: OK'); } else d.push(`first: ${resp.first_event_date} vs ${gt.first_event_date} WRONG`);
  if (resp.prosecution_duration_days === gt.prosecution_duration_days) { s++; d.push('duration: OK'); } else d.push(`duration: ${resp.prosecution_duration_days} vs ${gt.prosecution_duration_days} WRONG`);
  return { score: s, maxScore: 3, percentage: (s/3*100).toFixed(1), details: d };
}

function scoreResponse(taskType, resp, gt) {
  if (resp._parse_error) return { score: 0, maxScore: 1, percentage: '0.0', details: ['JSON parse error'] };
  switch (taskType) {
    case 'deadline_calculation': return scoreDeadline(resp, gt);
    case 'action_classification': return scoreClassification(resp, gt);
    case 'fee_computation': return scoreFee(resp, gt);
    case 'timeline_analysis': return scoreTimeline(resp, gt);
    default: return { score: 0, maxScore: 1, percentage: '0.0', details: ['unknown task'] };
  }
}

function main() {
  const data = JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
  const tests = data.test_cases;

  // Resume from progress file if exists
  let results = [];
  let startIdx = 0;
  if (fs.existsSync(PROGRESS_FILE)) {
    const progress = JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf-8'));
    results = progress.results || [];
    startIdx = results.length;
    console.log(`Resuming from test ${startIdx + 1}/${tests.length}`);
  }

  console.log(`Claude Sonnet benchmark (OAuth): ${tests.length} tests`);
  console.log('');

  let totalScore = 0, totalMax = 0, parseErrors = 0;
  const taskScores = {};

  // Replay existing scores
  for (const r of results) {
    const test = tests.find(t => t.id === r.test_id);
    if (!test) continue;
    const scoring = { score: parseFloat(r.score) / 100 * (r.maxScore || 1), maxScore: r.maxScore || 1 };
    totalScore += scoring.score;
    totalMax += scoring.maxScore;
    if (!taskScores[r.task_type]) taskScores[r.task_type] = { score: 0, max: 0, count: 0 };
    taskScores[r.task_type].score += scoring.score;
    taskScores[r.task_type].max += scoring.maxScore;
    taskScores[r.task_type].count++;
    if (r.details?.includes('JSON parse error')) parseErrors++;
  }

  const startTime = Date.now();

  for (let i = startIdx; i < tests.length; i++) {
    const test = tests[i];
    const sysPrompt = SYSTEM_PROMPTS[test.task_type];
    if (!sysPrompt) continue;

    let rawResp = '', parsed = { _parse_error: true };
    try {
      rawResp = callClaude(sysPrompt, test.question);
      parsed = parseJsonResponse(rawResp);
      if (parsed._parse_error) parseErrors++;
    } catch (err) {
      parseErrors++;
      rawResp = `ERROR: ${err.message.substring(0, 200)}`;
    }

    const scoring = scoreResponse(test.task_type, parsed, test.ground_truth);
    totalScore += scoring.score;
    totalMax += scoring.maxScore;

    if (!taskScores[test.task_type]) taskScores[test.task_type] = { score: 0, max: 0, count: 0 };
    taskScores[test.task_type].score += scoring.score;
    taskScores[test.task_type].max += scoring.maxScore;
    taskScores[test.task_type].count++;

    results.push({
      test_id: test.id,
      task_type: test.task_type,
      score: scoring.percentage + '%',
      maxScore: scoring.maxScore,
      details: scoring.details,
      raw_response: rawResp,
    });

    // Save progress
    fs.writeFileSync(PROGRESS_FILE, JSON.stringify({ results }, null, 2));

    const pct = (totalScore / totalMax * 100).toFixed(1);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
    process.stdout.write(`  [${i+1}/${tests.length}] ${test.task_type.padEnd(25)} ${scoring.percentage}% | Running: ${pct}% | ${elapsed}s\n`);
  }

  console.log('\n');
  console.log('='.repeat(60));
  console.log('  CLAUDE SONNET — PATENTBENCH RESULTS (OAuth)');
  console.log('='.repeat(60));
  console.log(`  Overall: ${(totalScore/totalMax*100).toFixed(1)}%`);
  console.log(`  Parse errors: ${parseErrors}/${tests.length}`);

  for (const [type, s] of Object.entries(taskScores)) {
    console.log(`  ${type.padEnd(25)} ${(s.score/s.max*100).toFixed(1)}% (${s.count} tests)`);
  }

  // Build by_technology_center from test data
  const tcScores = {};
  for (let i = 0; i < results.length; i++) {
    const test = tests[i];
    if (!test) continue;
    // Find TC from test id or application data
    const tc = test.technology_center || 'unknown';
    if (!tcScores[tc]) tcScores[tc] = { score: 0, max: 0, count: 0 };
    const r = results[i];
    const pct = parseFloat(r.score) / 100;
    tcScores[tc].score += pct * (r.maxScore || 1);
    tcScores[tc].max += r.maxScore || 1;
    tcScores[tc].count++;
  }

  const output = {
    benchmark: 'PatentBench-Mini v0.1.0',
    model: 'ABIGAIL v3 (Variant B)',
    run_date: new Date().toISOString(),
    summary: {
      overall_accuracy: (totalScore/totalMax*100).toFixed(1) + '%',
      total_tests: tests.length,
      total_points: `${totalScore.toFixed(1)}/${totalMax}`,
      parse_errors: parseErrors,
    },
    by_task_type: Object.fromEntries(
      Object.entries(taskScores).map(([k, v]) => [k, {
        accuracy: (v.score/v.max*100).toFixed(1) + '%',
        tests: v.count,
        points: `${v.score.toFixed(1)}/${v.max}`,
      }])
    ),
    detailed_results: results.map(r => ({
      test_id: r.test_id,
      task_type: r.task_type,
      score: r.score,
      details: r.details,
      raw_response: r.raw_response,
    })),
  };

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2));
  console.log(`\n  Output: ${OUTPUT_FILE}`);
  console.log('='.repeat(60));

  // Clean up progress file
  try { fs.unlinkSync(PROGRESS_FILE); } catch {}
}

main();
