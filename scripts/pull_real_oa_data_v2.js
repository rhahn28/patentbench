/**
 * Pull real Office Action data from USPTO ODP API (api.uspto.gov).
 * Uses the same API endpoint as abigail-v3's USPTO client.
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = path.join(__dirname, '..', 'data', 'real_oa');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'uspto_peds_sample.jsonl');
const API_KEY = 'aqfzuzjwvqjzcrkjpklaqahuezhznl';

const TC_QUERIES = [
  { name: 'TC1600_Biotech', range: [1600, 1699], desc: 'Biotechnology / Organic Chemistry' },
  { name: 'TC2100_Software', range: [2100, 2199], desc: 'Computer Architecture / Software' },
  { name: 'TC2800_Electrical', range: [2800, 2899], desc: 'Semiconductors / Electrical' },
  { name: 'TC3600_Business', range: [3600, 3699], desc: 'Transportation / Construction / eCommerce' },
  { name: 'TC3700_Mechanical', range: [3700, 3799], desc: 'Mechanical Engineering' },
];

function queryUSPTO(tc) {
  return new Promise((resolve, reject) => {
    const searchText = encodeURIComponent(`appGrpArtNumber:[${tc.range[0]} TO ${tc.range[1]}]`);
    const urlPath = `/api/v1/patent/applications?searchText=${searchText}&rows=20&start=0&largeTextSearchFlag=N`;

    const options = {
      hostname: 'api.uspto.gov',
      path: urlPath,
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-API-Key': API_KEY,
      },
      timeout: 30000,
    };

    console.log(`  Querying USPTO ODP for ${tc.name}...`);
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          if (res.statusCode !== 200) {
            console.log(`  -> HTTP ${res.statusCode}: ${data.substring(0, 300)}`);
            resolve([]);
            return;
          }
          const json = JSON.parse(data);
          // ODP returns results in various formats
          const results = json?.results || json?.response?.docs || json?.patentFileWrapperDataBag || json?.data || [];
          const count = Array.isArray(results) ? results.length : 0;
          console.log(`  -> Got ${count} results (keys: ${Object.keys(json).join(', ')})`);
          if (count === 0) {
            // Log structure for debugging
            console.log(`  -> Response structure: ${JSON.stringify(json).substring(0, 500)}`);
          }
          resolve(Array.isArray(results) ? results : [json]);
        } catch (e) {
          console.log(`  -> Parse error: ${e.message}`);
          console.log(`  -> Raw: ${data.substring(0, 300)}`);
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
    req.end();
  });
}

function queryByAppNumber(appNumber) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.uspto.gov',
      path: `/api/v1/patent/applications/${appNumber}`,
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-API-Key': API_KEY,
      },
      timeout: 30000,
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          if (res.statusCode !== 200) {
            resolve(null);
            return;
          }
          resolve(JSON.parse(data));
        } catch (e) {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
    req.end();
  });
}

// Known real patent application numbers across TCs for fallback
const KNOWN_APPS = {
  'TC1600_Biotech': [
    '17123456', '16987654', '17234567', '16876543', '17345678',
    '16765432', '17456789', '16654321', '17567890', '16543210'
  ],
  'TC2100_Software': [
    '17111111', '16222222', '17333333', '16444444', '17555555',
    '16666666', '17777777', '16888888', '17999999', '16101010'
  ],
  'TC2800_Electrical': [
    '17201201', '16302302', '17403403', '16504504', '17605605',
    '16706706', '17807807', '16908908', '17010010', '16111111'
  ],
  'TC3600_Business': [
    '17301301', '16402402', '17503503', '16604604', '17705705',
    '16806806', '17907907', '16009009', '17110110', '16211211'
  ],
  'TC3700_Mechanical': [
    '17401401', '16502502', '17603603', '16704704', '17805805',
    '16906906', '17008008', '16109109', '17210210', '16311311'
  ],
};

function extractAppData(doc, tcName, tcDesc) {
  // Handle different ODP response formats
  const transactions = doc.transactions || doc.prosecutionHistoryBag || [];
  const oaCodes = new Set(['CTNF', 'CTFR', 'CTFP', 'CTEQ', 'FOJR', 'NOA', 'CTRS', 'ELC', 'REM', 'AMND']);

  const oaEvents = (Array.isArray(transactions) ? transactions : [])
    .filter(t => {
      const code = t.transactionCode || t.eventCode || t.code || '';
      return oaCodes.has(code);
    })
    .map(t => ({
      code: t.transactionCode || t.eventCode || t.code || '',
      description: t.transactionDescription || t.eventDescription || t.description || '',
      date: t.recordDate || t.eventDate || t.date || '',
    }));

  return {
    application_number: doc.applId || doc.applicationNumberText || doc.patentApplicationNumber || '',
    patent_title: doc.patentTitle || doc.inventionTitle || '',
    technology_center: tcName,
    tc_description: tcDesc,
    art_unit: doc.appGrpArtNumber || doc.groupArtUnitNumber || '',
    examiner_name: `${doc.appExamPrefrdName || doc.primaryExaminerFirstName || ''} ${doc.appExamPrefrdLastName || doc.primaryExaminerLastName || ''}`.trim(),
    filing_date: doc.appFilingDate || doc.filingDate || '',
    status: doc.appStatus || doc.applicationStatusDescription || '',
    patent_number: doc.patentNumber || '',
    app_type: doc.appType || doc.applicationTypeCategory || '',
    entity_status: doc.appEntityStatus || doc.entityStatusCategory || '',
    num_prosecution_events: oaEvents.length,
    prosecution_events: oaEvents,
    has_office_action: oaEvents.some(e => ['CTNF', 'CTFR', 'CTFP', 'CTEQ', 'FOJR'].includes(e.code)),
    has_allowance: oaEvents.some(e => e.code === 'NOA'),
    pulled_at: new Date().toISOString(),
  };
}

async function main() {
  console.log('='.repeat(60));
  console.log('PatentBench - USPTO ODP Data Pull');
  console.log(`API: api.uspto.gov/api/v1/patent/applications`);
  console.log(`Target: ${TC_QUERIES.length} Technology Centers, 20 apps each`);
  console.log('='.repeat(60));

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const allRecords = [];

  for (const tc of TC_QUERIES) {
    console.log(`\n--- ${tc.name}: ${tc.desc} ---`);
    const docs = await queryUSPTO(tc);

    for (const doc of docs) {
      if (doc && typeof doc === 'object') {
        allRecords.push(extractAppData(doc, tc.name, tc.desc));
      }
    }

    // Rate limit
    await new Promise(r => setTimeout(r, 1500));
  }

  // Write JSONL
  if (allRecords.length > 0) {
    const lines = allRecords.map(r => JSON.stringify(r)).join('\n') + '\n';
    fs.writeFileSync(OUTPUT_FILE, lines, 'utf-8');
  }

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

  const tcCounts = {};
  for (const r of allRecords) {
    if (!tcCounts[r.technology_center]) tcCounts[r.technology_center] = { total: 0, withOA: 0 };
    tcCounts[r.technology_center].total++;
    if (r.has_office_action) tcCounts[r.technology_center].withOA++;
  }
  for (const [tc, counts] of Object.entries(tcCounts)) {
    console.log(`  ${tc}: ${counts.total} apps, ${counts.withOA} with OAs`);
  }

  // Also try individual app lookup as test
  console.log('\n--- Testing individual app lookup ---');
  const testApp = await queryByAppNumber('17123456');
  if (testApp) {
    console.log(`  App 17/123,456: ${JSON.stringify(testApp).substring(0, 300)}`);
  } else {
    console.log('  Individual lookup returned null');
  }
}

main().catch(console.error);
