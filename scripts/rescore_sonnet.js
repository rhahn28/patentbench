/**
 * Re-scores Sonnet benchmark results from raw responses using fuzzy option matching.
 * Run after run_sonnet_oauth.js completes.
 */
const fs = require('fs');
const path = require('path');

const DATA_FILE = path.join(__dirname, '..', 'data', 'benchmark_cases_tier1_2.json');
const PROGRESS_FILE = path.join(__dirname, '..', 'data', '_sonnet_progress.json');
const OUTPUT_FILE = path.join(__dirname, '..', 'data', 'benchmark_results_sonnet.json');

function parseJsonResponse(rawText) {
  let text = rawText.trim();
  text = text.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '');
  text = text.trim();
  const firstBrace = text.indexOf('{');
  const lastBrace = text.lastIndexOf('}');
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    text = text.substring(firstBrace, lastBrace + 1);
  }
  try { return JSON.parse(text); }
  catch { return { _parse_error: true }; }
}

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

function scoreDeadline(resp, gt) {
  let s = 0, m = 0, d = [];
  m++; if (resp.shortened_deadline === gt.shortened_deadline) { s++; d.push('shortened: OK'); } else d.push(`shortened: ${resp.shortened_deadline} vs ${gt.shortened_deadline}`);
  m++; if (resp.max_deadline === gt.max_deadline) { s++; d.push('max: OK'); } else d.push(`max: ${resp.max_deadline} vs ${gt.max_deadline}`);
  m++; if (resp.action_type === gt.action_type) { s++; d.push('type: OK'); } else d.push(`type: ${resp.action_type} vs ${gt.action_type}`);
  if (gt.options) {
    m++;
    const respOpts = resp.options || [];
    const matched = gt.options.filter(gtOpt => matchesOption(gtOpt, respOpts));
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
  if (resp.total_oa_rounds === gt.total_oa_rounds) { s++; d.push('rounds: OK'); } else d.push(`rounds: ${resp.total_oa_rounds} vs ${gt.total_oa_rounds}`);
  return { score: s, maxScore: 4, percentage: (s/4*100).toFixed(1), details: d };
}

function scoreFee(resp, gt) {
  let s = 0, d = [];
  if (resp.extension_1_month === gt.extension_1_month) { s++; d.push('ext: OK'); } else d.push(`ext: ${resp.extension_1_month} vs ${gt.extension_1_month}`);
  if (resp.rce_fee === gt.rce_fee) { s++; d.push('rce: OK'); } else d.push(`rce: ${resp.rce_fee} vs ${gt.rce_fee}`);
  if (resp.issue_fee === gt.issue_fee) { s++; d.push('issue: OK'); } else d.push(`issue: ${resp.issue_fee} vs ${gt.issue_fee}`);
  return { score: s, maxScore: 3, percentage: (s/3*100).toFixed(1), details: d };
}

function scoreTimeline(resp, gt) {
  let s = 0, d = [];
  if (resp.total_events === gt.total_events) { s++; d.push('events: OK'); } else d.push(`events: ${resp.total_events} vs ${gt.total_events}`);
  if (resp.first_event_date === gt.first_event_date) { s++; d.push('first: OK'); } else d.push(`first: ${resp.first_event_date} vs ${gt.first_event_date}`);
  if (resp.prosecution_duration_days === gt.prosecution_duration_days) { s++; d.push('duration: OK'); } else d.push(`duration: ${resp.prosecution_duration_days} vs ${gt.prosecution_duration_days}`);
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
  const progress = JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf-8'));

  console.log(`Re-scoring ${progress.results.length} results with fuzzy option matching\n`);

  let totalScore = 0, totalMax = 0, parseErrors = 0;
  const taskScores = {};
  const rescored = [];

  for (const r of progress.results) {
    const test = tests.find(t => t.id === r.test_id);
    if (!test) continue;

    let parsed = { _parse_error: true };
    if (r.raw_response && !r.raw_response.startsWith('ERROR')) {
      parsed = parseJsonResponse(r.raw_response);
      if (parsed._parse_error) parseErrors++;
    } else {
      parseErrors++;
    }

    const scoring = scoreResponse(test.task_type, parsed, test.ground_truth);
    totalScore += scoring.score;
    totalMax += scoring.maxScore;

    if (!taskScores[test.task_type]) taskScores[test.task_type] = { score: 0, max: 0, count: 0 };
    taskScores[test.task_type].score += scoring.score;
    taskScores[test.task_type].max += scoring.maxScore;
    taskScores[test.task_type].count++;

    rescored.push({
      test_id: r.test_id,
      task_type: r.task_type || test.task_type,
      score: scoring.percentage + '%',
      details: scoring.details,
    });
  }

  console.log('='.repeat(60));
  console.log('  CLAUDE SONNET 4.6 — PATENTBENCH RESULTS (Re-scored)');
  console.log('='.repeat(60));
  console.log(`  Overall: ${(totalScore/totalMax*100).toFixed(1)}%`);
  console.log(`  Tests: ${progress.results.length}/${tests.length}`);
  console.log(`  Parse errors: ${parseErrors}`);

  for (const [type, s] of Object.entries(taskScores)) {
    console.log(`  ${type.padEnd(25)} ${(s.score/s.max*100).toFixed(1)}% (${s.count} tests)`);
  }

  // Show failures
  const fails = rescored.filter(r => r.score !== '100.0%');
  console.log(`\n  Failures: ${fails.length}`);
  fails.slice(0, 10).forEach(f => console.log(`    ${f.test_id.padEnd(25)} ${f.score.padEnd(8)} ${(f.details||[]).join(', ')}`));
  if (fails.length > 10) console.log(`    ... and ${fails.length - 10} more`);

  const output = {
    benchmark: 'PatentBench-Mini v0.1.0',
    model: 'ABIGAIL v3 (Variant B)',
    run_date: new Date().toISOString(),
    method: 'claude -p --model sonnet (OAuth, zero API cost)',
    summary: {
      overall_accuracy: (totalScore/totalMax*100).toFixed(1) + '%',
      total_tests: progress.results.length,
      total_possible: tests.length,
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
    detailed_results: rescored,
  };

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2));
  console.log(`\n  Output: ${OUTPUT_FILE}`);
  console.log('='.repeat(60));
}

main();
