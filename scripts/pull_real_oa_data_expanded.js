/**
 * Pull expanded real patent prosecution data from USPTO ODP API.
 * Targets specific technology centers and application number ranges
 * to build a more representative dataset (250+ additional apps).
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = path.join(__dirname, '..', 'data', 'real_oa');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'uspto_peds_expanded.jsonl');
const API_KEY = 'aqfzuzjwvqjzcrkjpklaqahuezhznl';
const DELAY_MS = 350;

// Ranges targeting specific TC areas and filing series
const APP_RANGES = [
  // TC2100 Software , need 50+ (art units 2100-2199)
  // 18M series (2022-2023 filings) likely to land in software TCs
  { tc: 'TC2100_Target', desc: 'Software target (18.1M)', start: 18100000, count: 35 },
  { tc: 'TC2100_Target', desc: 'Software target (18.1M+50)', start: 18100050, count: 35 },

  // TC1600 Biotech , need 30+ (art units 1600-1699)
  { tc: 'TC1600_Target', desc: 'Biotech target (17.2M)', start: 17200000, count: 30 },
  { tc: 'TC1600_Target', desc: 'Biotech target (17.2M+30)', start: 17200030, count: 20 },

  // TC2800 Electrical , add 30 more
  { tc: 'TC2800_Target', desc: 'Electrical target (17.7M)', start: 17700000, count: 30 },
  { tc: 'TC2800_Target', desc: 'Electrical target (17.7M+30)', start: 17700030, count: 20 },

  // TC3700 Mechanical , add 30 more
  { tc: 'TC3700_Target', desc: 'Mechanical target (17.8M)', start: 17800000, count: 30 },
  { tc: 'TC3700_Target', desc: 'Mechanical target (17.8M+30)', start: 17800030, count: 20 },

  // TC1700 Chemical , add 20 more
  { tc: 'TC1700_Target', desc: 'Chemical target (18.5M)', start: 18500000, count: 30 },

  // General mix from 18M and 19M series , 50+ more
  { tc: 'General_Mix', desc: 'General mix (18.5M+50)', start: 18500050, count: 30 },
  { tc: 'General_Mix', desc: 'General mix (18.1M+100)', start: 18100100, count: 30 },
  { tc: 'General_Mix', desc: 'General mix (17.5M)', start: 17500000, count: 25 },
];

const OA_CODES = new Set(['CTNF', 'CTFR', 'CTFP', 'CTEQ', 'FOJR', 'MCTNF', 'MCTFR']);
const ALLOW_CODES = new Set(['NOA', 'CNOA', 'MCNOA']);
const ALL_RELEVANT = new Set([...OA_CODES, ...ALLOW_CODES, 'ELC', 'AMND', 'REM', 'ABN8', 'ABN9', 'N/AP', 'CTRS']);

function fetchApp(appNumber) {
  return new Promise((resolve) => {
    const req = https.request({
      hostname: 'api.uspto.gov',
      path: `/api/v1/patent/applications/${appNumber}`,
      method: 'GET',
      headers: { 'Accept': 'application/json', 'X-API-Key': API_KEY },
      timeout: 15000,
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode !== 200) { resolve(null); return; }
        try { resolve(JSON.parse(data)); } catch { resolve(null); }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
    req.end();
  });
}

function extractRecord(data, appNumber) {
  const bag = data?.patentFileWrapperDataBag?.[0];
  if (!bag) return null;

  const meta = bag.applicationMetaData || {};
  const events = bag.eventDataBag || [];

  const oaEvents = events
    .filter(e => ALL_RELEVANT.has(e.eventCode))
    .map(e => ({
      code: e.eventCode,
      description: e.eventDescriptionText || '',
      date: e.eventDate || '',
    }));

  const artUnit = meta.groupArtUnitNumber || '';
  let tc = 'Unknown';
  const auNum = parseInt(artUnit);
  if (auNum >= 1600 && auNum < 1700) tc = 'TC1600_Biotech';
  else if (auNum >= 1700 && auNum < 1800) tc = 'TC1700_Chemical';
  else if (auNum >= 2100 && auNum < 2200) tc = 'TC2100_Software';
  else if (auNum >= 2400 && auNum < 2500) tc = 'TC2400_Networking';
  else if (auNum >= 2600 && auNum < 2700) tc = 'TC2600_Communications';
  else if (auNum >= 2800 && auNum < 2900) tc = 'TC2800_Electrical';
  else if (auNum >= 3600 && auNum < 3700) tc = 'TC3600_Business';
  else if (auNum >= 3700 && auNum < 3800) tc = 'TC3700_Mechanical';
  else tc = `TC${Math.floor(auNum / 100) * 100}`;

  const tcDescs = {
    'TC1600_Biotech': 'Biotechnology / Organic Chemistry',
    'TC1700_Chemical': 'Chemical / Materials Engineering',
    'TC2100_Software': 'Computer Architecture / Software',
    'TC2400_Networking': 'Networking / Cryptography / Security',
    'TC2600_Communications': 'Communications',
    'TC2800_Electrical': 'Semiconductors / Electrical',
    'TC3600_Business': 'Transportation / Construction / eCommerce',
    'TC3700_Mechanical': 'Mechanical Engineering',
  };

  return {
    application_number: appNumber.toString(),
    patent_title: meta.inventionTitle || '',
    technology_center: tc,
    tc_description: tcDescs[tc] || tc,
    art_unit: artUnit,
    examiner_name: meta.examinerNameText || '',
    filing_date: meta.filingDate || '',
    status: meta.applicationStatusDescriptionText || meta.applicationStatusCode || '',
    patent_number: meta.patentNumber || '',
    app_type: meta.applicationTypeCategory || '',
    entity_status: meta.entityStatusData?.entityStatusCategory || '',
    num_prosecution_events: oaEvents.length,
    prosecution_events: oaEvents,
    has_office_action: oaEvents.some(e => OA_CODES.has(e.code)),
    has_allowance: oaEvents.some(e => ALLOW_CODES.has(e.code)),
    total_events_in_file: events.length,
    pulled_at: new Date().toISOString(),
  };
}

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  console.log('='.repeat(60));
  console.log('PatentBench - USPTO ODP Expanded Data Pull');
  console.log(`Target: 250+ additional applications`);
  console.log(`Total app numbers to query: ${APP_RANGES.reduce((s, r) => s + r.count, 0)}`);
  console.log('='.repeat(60));

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const allRecords = [];
  let queried = 0, found = 0, skipped = 0;

  for (const range of APP_RANGES) {
    console.log(`\n--- ${range.desc} (${range.start} - ${range.start + range.count - 1}) ---`);

    for (let i = 0; i < range.count; i++) {
      const appNum = range.start + i;
      queried++;
      process.stdout.write(`  ${appNum}...`);

      const data = await fetchApp(appNum);
      if (!data || data.count === 0) {
        process.stdout.write(' skip\n');
        skipped++;
        await sleep(250);
        continue;
      }

      const record = extractRecord(data, appNum);
      if (record) {
        allRecords.push(record);
        found++;
        const oaFlag = record.has_office_action ? ' [HAS OA]' : '';
        const allowFlag = record.has_allowance ? ' [ALLOWED]' : '';
        console.log(` ${record.art_unit} "${record.patent_title.substring(0, 40)}" ${record.num_prosecution_events}ev${oaFlag}${allowFlag}`);
      } else {
        console.log(' no data');
        skipped++;
      }

      await sleep(DELAY_MS);
    }

    // Progress update after each range
    console.log(`  >> Progress: ${found} found / ${queried} queried (${skipped} skipped)`);
  }

  // Write JSONL
  const lines = allRecords.map(r => JSON.stringify(r)).join('\n') + '\n';
  fs.writeFileSync(OUTPUT_FILE, lines, 'utf-8');

  // Summary
  const withOA = allRecords.filter(r => r.has_office_action).length;
  const withAllow = allRecords.filter(r => r.has_allowance).length;

  console.log(`\n${'='.repeat(60)}`);
  console.log('RESULTS SUMMARY');
  console.log('='.repeat(60));
  console.log(`Queried: ${queried} | Found: ${found} | Skipped: ${skipped}`);
  console.log(`With Office Actions: ${withOA} (${found > 0 ? (withOA/found*100).toFixed(0) : 0}%)`);
  console.log(`With Allowance: ${withAllow} (${found > 0 ? (withAllow/found*100).toFixed(0) : 0}%)`);
  console.log(`Output: ${OUTPUT_FILE}`);

  // TC breakdown
  const tcCounts = {};
  for (const r of allRecords) {
    if (!tcCounts[r.technology_center]) tcCounts[r.technology_center] = { total: 0, withOA: 0, withAllow: 0 };
    tcCounts[r.technology_center].total++;
    if (r.has_office_action) tcCounts[r.technology_center].withOA++;
    if (r.has_allowance) tcCounts[r.technology_center].withAllow++;
  }
  console.log('\nBy Technology Center:');
  for (const [tc, c] of Object.entries(tcCounts).sort((a,b) => b[1].total - a[1].total)) {
    console.log(`  ${tc}: ${c.total} apps, ${c.withOA} with OAs, ${c.withAllow} allowed`);
  }
}

main().catch(console.error);
