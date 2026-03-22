/**
 * PatentBench Tier 1-2 Benchmark Runner
 * Tests deterministic patent prosecution knowledge against real USPTO data.
 * Model under test: Claude (responding directly in conversation)
 *
 * Generates benchmark test cases from real prosecution histories,
 * with ground truth answers derived from USPTO event codes and dates.
 */
const fs = require('fs');
const path = require('path');

const DATA_FILE = path.join(__dirname, '..', 'data', 'real_oa', 'uspto_peds_sample.jsonl');
const OUTPUT_FILE = path.join(__dirname, '..', 'data', 'benchmark_cases_tier1_2.json');

const records = fs.readFileSync(DATA_FILE, 'utf-8').trim().split('\n').map(l => JSON.parse(l));
const withOA = records.filter(r => r.has_office_action && r.prosecution_events.length > 0);

// ========== TIER 1: DETERMINISTIC TESTS ==========

function generateDeadlineTests(records) {
  const tests = [];
  for (const r of records) {
    // Find the first non-final OA mail date
    const nfMail = r.prosecution_events.find(e => e.code === 'MCTNF');
    const frMail = r.prosecution_events.find(e => e.code === 'MCTFR');

    if (nfMail) {
      const mailDate = new Date(nfMail.date);
      // Non-final: 3 months from mail date (shortened) or 6 months (statutory max)
      const shortDeadline = new Date(mailDate);
      shortDeadline.setMonth(shortDeadline.getMonth() + 3);
      const maxDeadline = new Date(mailDate);
      maxDeadline.setMonth(maxDeadline.getMonth() + 6);

      tests.push({
        id: `deadline_nf_${r.application_number}`,
        tier: 1,
        task_type: 'deadline_calculation',
        application_number: r.application_number,
        title: r.patent_title,
        question: `A Non-Final Office Action was mailed on ${nfMail.date} for application ${r.application_number}. What is the shortened statutory response deadline and the maximum statutory deadline?`,
        ground_truth: {
          shortened_deadline: shortDeadline.toISOString().split('T')[0],
          max_deadline: maxDeadline.toISOString().split('T')[0],
          action_type: 'Non-Final',
          explanation: 'Non-Final OA: 3 months shortened period, 6 months statutory max under 37 CFR 1.134'
        }
      });
    }

    if (frMail) {
      const mailDate = new Date(frMail.date);
      const shortDeadline = new Date(mailDate);
      shortDeadline.setMonth(shortDeadline.getMonth() + 3);
      const maxDeadline = new Date(mailDate);
      maxDeadline.setMonth(maxDeadline.getMonth() + 6);

      tests.push({
        id: `deadline_fr_${r.application_number}`,
        tier: 1,
        task_type: 'deadline_calculation',
        application_number: r.application_number,
        title: r.patent_title,
        question: `A Final Office Action was mailed on ${frMail.date} for application ${r.application_number}. What is the shortened statutory response deadline? What are the applicant's options after a Final Rejection?`,
        ground_truth: {
          shortened_deadline: shortDeadline.toISOString().split('T')[0],
          max_deadline: maxDeadline.toISOString().split('T')[0],
          action_type: 'Final',
          options: ['File response with amendments under 37 CFR 1.116', 'File RCE under 37 CFR 1.114', 'File Notice of Appeal under 37 CFR 41.31', 'Request interview with examiner', 'File continuation application'],
          explanation: 'Final OA: 3 months shortened, 6 months max. After Final, applicant may amend (limited), file RCE, appeal, or continue.'
        }
      });
    }
  }
  return tests;
}

function generateActionClassificationTests(records) {
  const tests = [];
  for (const r of records) {
    const events = r.prosecution_events;
    const hasNonFinal = events.some(e => e.code === 'CTNF' || e.code === 'MCTNF');
    const hasFinal = events.some(e => e.code === 'CTFR' || e.code === 'MCTFR');
    const hasAllowance = events.some(e => ['NOA', 'CNOA', 'MCNOA'].includes(e.code));

    tests.push({
      id: `classify_${r.application_number}`,
      tier: 1,
      task_type: 'action_classification',
      application_number: r.application_number,
      title: r.patent_title,
      question: `Given the following prosecution events for application ${r.application_number} ("${r.patent_title}"), classify the prosecution history: ${JSON.stringify(events.map(e => ({code: e.code, desc: e.description, date: e.date})))}`,
      ground_truth: {
        has_non_final: hasNonFinal,
        has_final: hasFinal,
        has_allowance: hasAllowance,
        total_oa_rounds: (hasNonFinal ? 1 : 0) + (hasFinal ? 1 : 0),
        final_outcome: hasAllowance ? 'Allowed' : (r.status.includes('Patent') ? 'Patented' : r.status),
        technology_center: r.technology_center,
        art_unit: r.art_unit,
        examiner: r.examiner_name
      }
    });
  }
  return tests;
}

// ========== TIER 2: PROSECUTION TIMELINE ANALYSIS ==========

function generateTimelineTests(records) {
  const tests = [];
  for (const r of records) {
    if (r.prosecution_events.length < 2) continue;

    const events = [...r.prosecution_events].sort((a, b) => new Date(a.date) - new Date(b.date));
    const firstEvent = events[0];
    const lastEvent = events[events.length - 1];
    const daysBetween = Math.round((new Date(lastEvent.date) - new Date(firstEvent.date)) / (1000 * 60 * 60 * 24));

    tests.push({
      id: `timeline_${r.application_number}`,
      tier: 2,
      task_type: 'timeline_analysis',
      application_number: r.application_number,
      title: r.patent_title,
      question: `Analyze the prosecution timeline for application ${r.application_number} ("${r.patent_title}") filed ${r.filing_date} in art unit ${r.art_unit}. Events: ${JSON.stringify(events)}. How many OA rounds? What was the total prosecution duration? What was the outcome?`,
      ground_truth: {
        total_events: events.length,
        first_event_date: firstEvent.date,
        last_event_date: lastEvent.date,
        prosecution_duration_days: daysBetween,
        outcome: r.has_allowance ? 'Allowed' : r.status,
        art_unit: r.art_unit,
        examiner: r.examiner_name
      }
    });
  }
  return tests;
}

// ========== TIER 2: FEE COMPUTATION ==========

function generateFeeTests(records) {
  const tests = [];
  const entityTypes = ['large', 'small', 'micro'];

  // Use first 10 records for fee tests
  for (const r of records.slice(0, 10)) {
    const entityType = r.entity_status ? r.entity_status.toLowerCase() : 'large';

    tests.push({
      id: `fee_${r.application_number}`,
      tier: 1,
      task_type: 'fee_computation',
      application_number: r.application_number,
      title: r.patent_title,
      entity_status: entityType,
      question: `For application ${r.application_number}, entity status "${entityType}", compute: (1) Extension of time fee for 1-month extension, (2) RCE filing fee, (3) Issue fee. Use current USPTO fee schedule (effective Jan 2025).`,
      ground_truth: {
        // Current USPTO fees (Jan 2025)
        extension_1_month: entityType === 'micro' ? 60 : entityType === 'small' ? 120 : 240,
        rce_fee: entityType === 'micro' ? 570 : entityType === 'small' ? 1140 : 2280,
        issue_fee: entityType === 'micro' ? 300 : entityType === 'small' ? 600 : 1200,
        entity_status: entityType,
        note: 'Fees per 37 CFR 1.16, 1.17, and 1.18 (effective Jan 18, 2025)'
      }
    });
  }
  return tests;
}

// ========== GENERATE ALL ==========

const deadlineTests = generateDeadlineTests(withOA);
const classifyTests = generateActionClassificationTests(withOA);
const timelineTests = generateTimelineTests(withOA);
const feeTests = generateFeeTests(withOA);

const allTests = [...deadlineTests, ...classifyTests, ...timelineTests, ...feeTests];

const output = {
  benchmark: 'PatentBench-Mini',
  version: '0.1.0',
  generated_at: new Date().toISOString(),
  model_under_test: 'ABIGAIL v3 (direct)',
  summary: {
    total_test_cases: allTests.length,
    tier_1_deadline: deadlineTests.length,
    tier_1_classification: classifyTests.length,
    tier_1_fees: feeTests.length,
    tier_2_timeline: timelineTests.length,
    source_applications: withOA.length,
    technology_centers: [...new Set(withOA.map(r => r.technology_center))].sort()
  },
  test_cases: allTests
};

fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2), 'utf-8');

console.log('='.repeat(60));
console.log('PatentBench-Mini Test Cases Generated');
console.log('='.repeat(60));
console.log(`Total test cases: ${allTests.length}`);
console.log(`  Tier 1 - Deadline: ${deadlineTests.length}`);
console.log(`  Tier 1 - Classification: ${classifyTests.length}`);
console.log(`  Tier 1 - Fees: ${feeTests.length}`);
console.log(`  Tier 2 - Timeline: ${timelineTests.length}`);
console.log(`Technology Centers: ${output.summary.technology_centers.join(', ')}`);
console.log(`Output: ${OUTPUT_FILE}`);
