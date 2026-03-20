/**
 * Pull real Office Action data from USPTO PEDS API.
 * Targets 5 Technology Centers for PatentBench-Mini.
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = path.join(__dirname, '..', 'data', 'real_oa');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'uspto_peds_sample.jsonl');

const TC_QUERIES = [
  { name: 'TC1600_Biotech', range: [1600, 1699], desc: 'Biotechnology / Organic Chemistry' },
  { name: 'TC2100_Software', range: [2100, 2199], desc: 'Computer Architecture / Software' },
  { name: 'TC2800_Electrical', range: [2800, 2899], desc: 'Semiconductors / Electrical' },
  { name: 'TC3600_Business', range: [3600, 3699], desc: 'Transportation / Construction / eCommerce' },
  { name: 'TC3700_Mechanical', range: [3700, 3799], desc: 'Mechanical Engineering' },
];

function queryPEDS(tc) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      searchText: `appGrpArtNumber:[${tc.range[0]} TO ${tc.range[1]}]`,
      fl: '*',
      mm: '100%',
      sort: 'appFilingDate desc',
      start: 0,
      rows: 20,
    });

    const options = {
      hostname: 'ped.uspto.gov',
      path: '/api/queries',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
      timeout: 30000,
    };

    console.log(`  Querying PEDS for ${tc.name}...`);
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          if (res.statusCode !== 200) {
            console.log(`  -> HTTP ${res.statusCode}: ${data.substring(0, 200)}`);
            resolve([]);
            return;
          }
          const json = JSON.parse(data);
          const docs = json?.queryResults?.searchResponse?.response?.docs || [];
          console.log(`  -> Got ${docs.length} results`);
          resolve(docs);
        } catch (e) {
          console.log(`  -> Parse error: ${e.message}`);
          resolve([]);
        }
      });
    });

    req.on('error', (e) => {
      console.log(`  -> Error: ${e.message}`);
      resolve([]);
    });
    req.on('timeout', () => {
      console.log(`  -> Timeout`);
      req.destroy();
      resolve([]);
    });
    req.write(payload);
    req.end();
  });
}

function extractAppData(doc, tcName, tcDesc) {
  const transactions = doc.transactions || [];
  const oaCodes = new Set(['CTNF', 'CTFR', 'CTFP', 'CTEQ', 'FOJR', 'NOA', 'CTRS', 'ELC', 'REM', 'AMND']);

  const oaEvents = transactions
    .filter(t => oaCodes.has(t.transactionCode))
    .map(t => ({
      code: t.transactionCode,
      description: t.transactionDescription || '',
      date: t.recordDate || '',
    }));

  return {
    application_number: doc.applId || '',
    patent_title: doc.patentTitle || '',
    technology_center: tcName,
    tc_description: tcDesc,
    art_unit: doc.appGrpArtNumber || '',
    examiner_name: `${doc.appExamPrefrdName || ''} ${doc.appExamPrefrdLastName || ''}`.trim(),
    filing_date: doc.appFilingDate || '',
    status: doc.appStatus || '',
    patent_number: doc.patentNumber || '',
    app_type: doc.appType || '',
    entity_status: doc.appEntityStatus || '',
    num_prosecution_events: oaEvents.length,
    prosecution_events: oaEvents,
    has_office_action: oaEvents.some(e => ['CTNF', 'CTFR', 'CTFP', 'CTEQ', 'FOJR'].includes(e.code)),
    has_allowance: oaEvents.some(e => e.code === 'NOA'),
    pulled_at: new Date().toISOString(),
  };
}

async function main() {
  console.log('='.repeat(60));
  console.log('PatentBench - USPTO PEDS Data Pull');
  console.log(`Target: ${TC_QUERIES.length} Technology Centers, 20 apps each`);
  console.log('='.repeat(60));

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const allRecords = [];

  for (const tc of TC_QUERIES) {
    console.log(`\n--- ${tc.name}: ${tc.desc} ---`);
    const docs = await queryPEDS(tc);

    for (const doc of docs) {
      allRecords.push(extractAppData(doc, tc.name, tc.desc));
    }

    // Rate limit: 1 second between queries
    await new Promise(r => setTimeout(r, 1000));
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
  console.log(`Total records: ${allRecords.length}`);
  console.log(`With Office Actions: ${withOA}`);
  console.log(`With Allowance: ${withAllow}`);
  console.log(`Output: ${OUTPUT_FILE}`);

  // Per-TC breakdown
  const tcCounts = {};
  for (const r of allRecords) {
    if (!tcCounts[r.technology_center]) tcCounts[r.technology_center] = { total: 0, withOA: 0 };
    tcCounts[r.technology_center].total++;
    if (r.has_office_action) tcCounts[r.technology_center].withOA++;
  }
  for (const [tc, counts] of Object.entries(tcCounts)) {
    console.log(`  ${tc}: ${counts.total} apps, ${counts.withOA} with OAs`);
  }
}

main().catch(console.error);
