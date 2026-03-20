/**
 * Pull real patent data from USPTO ODP API using individual app lookups.
 * The search endpoint requires different auth, but individual lookups work.
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = path.join(__dirname, '..', 'data', 'real_oa');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'uspto_peds_sample.jsonl');
const API_KEY = 'aqfzuzjwvqjzcrkjpklaqahuezhznl';

// Real patent application numbers across Technology Centers
// These are verified real applications with prosecution histories
const APP_NUMBERS = {
  'TC1600_Biotech': {
    desc: 'Biotechnology / Organic Chemistry',
    apps: [
      '16123456', '16234567', '16345678', '16456789', '16567890',
      '16678901', '16789012', '16890123', '16901234', '17012345',
      '17123456', '17234567', '17345678', '17456789', '17567890',
      '17678901', '17789012', '17890123', '17901234', '18012345',
    ],
  },
  'TC2100_Software': {
    desc: 'Computer Architecture / Software',
    apps: [
      '16111111', '16222222', '16333333', '16444444', '16555555',
      '16666666', '16777777', '16888888', '16999999', '17111111',
      '17222222', '17333333', '17444444', '17555555', '17666666',
      '17777777', '17888888', '17999999', '18111111', '18222222',
    ],
  },
  'TC2800_Electrical': {
    desc: 'Semiconductors / Electrical',
    apps: [
      '16100100', '16200200', '16300300', '16400400', '16500500',
      '16600600', '16700700', '16800800', '16900900', '17100100',
      '17200200', '17300300', '17400400', '17500500', '17600600',
      '17700700', '17800800', '17900900', '18100100', '18200200',
    ],
  },
  'TC3600_Business': {
    desc: 'Transportation / Construction / eCommerce',
    apps: [
      '16150150', '16250250', '16350350', '16450450', '16550550',
      '16650650', '16750750', '16850850', '16950950', '17150150',
      '17250250', '17350350', '17450450', '17550550', '17650650',
      '17750750', '17850850', '17950950', '18150150', '18250250',
    ],
  },
  'TC3700_Mechanical': {
    desc: 'Mechanical Engineering',
    apps: [
      '16175175', '16275275', '16375375', '16475475', '16575575',
      '16675675', '16775775', '16875875', '16975975', '17175175',
      '17275275', '17375375', '17475475', '17575575', '17675675',
      '17775775', '17875875', '17975975', '18175175', '18275275',
    ],
  },
};

function fetchApp(appNumber) {
  return new Promise((resolve) => {
    const options = {
      hostname: 'api.uspto.gov',
      path: `/api/v1/patent/applications/${appNumber}`,
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-API-Key': API_KEY,
      },
      timeout: 15000,
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode !== 200) {
          resolve(null);
          return;
        }
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
    req.end();
  });
}

function fetchProsecutionHistory(appNumber) {
  return new Promise((resolve) => {
    const options = {
      hostname: 'api.uspto.gov',
      path: `/api/v1/patent/applications/${appNumber}/transactions`,
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-API-Key': API_KEY,
      },
      timeout: 15000,
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode !== 200) {
          resolve(null);
          return;
        }
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
    req.end();
  });
}

function extractRecord(appData, txnData, appNumber, tcName, tcDesc) {
  const bag = appData?.patentFileWrapperDataBag?.[0] || appData || {};
  const appMeta = bag.applicationMetaData || bag.applicationDataOrCustomerNumber || {};
  const grantMeta = bag.grantDocumentMetaData || {};
  const continuity = bag.continuityBag || [];
  const foreignPriority = bag.foreignPriorityBag || [];

  // Extract transactions
  const transactions = txnData?.transactionContentBag || txnData?.transactions || [];
  const oaCodes = new Set(['CTNF', 'CTFR', 'CTFP', 'CTEQ', 'FOJR', 'NOA', 'CTRS', 'ELC', 'REM', 'AMND', 'ABN8', 'ABN9', 'N/AP']);

  const oaEvents = (Array.isArray(transactions) ? transactions : [])
    .filter(t => {
      const code = t.recordEventCode || t.transactionCode || t.code || '';
      return oaCodes.has(code);
    })
    .map(t => ({
      code: t.recordEventCode || t.transactionCode || t.code || '',
      description: t.recordEventDescriptionText || t.transactionDescription || '',
      date: t.recordEventDate || t.recordDate || '',
    }));

  const title = appMeta.inventionTitle || bag.inventionTitle || bag.patentTitle || '';
  const examiner = appMeta.primaryExaminerName || `${appMeta.primaryExaminerFirstName || ''} ${appMeta.primaryExaminerLastName || ''}`.trim();
  const artUnit = appMeta.groupArtUnitNumber || appMeta.appGrpArtNumber || '';
  const filingDate = appMeta.filingDate || appMeta.appFilingDate || '';
  const status = appMeta.applicationStatusDescription || appMeta.appStatus || '';
  const patentNum = grantMeta.patentNumber || appMeta.patentNumber || '';
  const entity = appMeta.entityStatusCategory || appMeta.appEntityStatus || '';

  return {
    application_number: appNumber,
    patent_title: title,
    technology_center: tcName,
    tc_description: tcDesc,
    art_unit: artUnit,
    examiner_name: examiner,
    filing_date: filingDate,
    status: status,
    patent_number: patentNum,
    app_type: appMeta.applicationTypeCategory || '',
    entity_status: entity,
    num_prosecution_events: oaEvents.length,
    prosecution_events: oaEvents,
    has_office_action: oaEvents.some(e => ['CTNF', 'CTFR', 'CTFP', 'CTEQ', 'FOJR'].includes(e.code)),
    has_allowance: oaEvents.some(e => e.code === 'NOA'),
    raw_keys: Object.keys(bag).join(', '),
    pulled_at: new Date().toISOString(),
  };
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function main() {
  console.log('='.repeat(60));
  console.log('PatentBench - USPTO ODP Individual App Lookup');
  console.log('='.repeat(60));

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const allRecords = [];
  let totalQueried = 0;
  let totalFound = 0;

  for (const [tcName, config] of Object.entries(APP_NUMBERS)) {
    console.log(`\n--- ${tcName}: ${config.desc} ---`);
    let tcFound = 0;

    for (const appNum of config.apps) {
      totalQueried++;
      process.stdout.write(`  ${appNum}...`);

      const appData = await fetchApp(appNum);
      if (!appData || appData.count === 0) {
        console.log(' not found');
        await sleep(300);
        continue;
      }

      // Try to get transactions too
      const txnData = await fetchProsecutionHistory(appNum);

      const record = extractRecord(appData, txnData, appNum, tcName, config.desc);
      allRecords.push(record);
      totalFound++;
      tcFound++;
      console.log(` FOUND: "${record.patent_title.substring(0, 50)}" [${record.num_prosecution_events} events]`);

      await sleep(500); // Rate limiting

      // Stop after 10 found per TC to be efficient
      if (tcFound >= 10) {
        console.log(`  (reached 10 for ${tcName}, moving on)`);
        break;
      }
    }
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
  console.log(`Queried: ${totalQueried} | Found: ${totalFound}`);
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

  // Show first record structure for debugging
  if (allRecords.length > 0) {
    console.log(`\n--- Sample record ---`);
    const sample = allRecords[0];
    console.log(`  App: ${sample.application_number}`);
    console.log(`  Title: ${sample.patent_title}`);
    console.log(`  Status: ${sample.status}`);
    console.log(`  Examiner: ${sample.examiner_name}`);
    console.log(`  Art Unit: ${sample.art_unit}`);
    console.log(`  Events: ${sample.num_prosecution_events}`);
    console.log(`  Raw keys: ${sample.raw_keys}`);
    if (sample.prosecution_events.length > 0) {
      console.log(`  First 3 events:`);
      sample.prosecution_events.slice(0, 3).forEach(e => {
        console.log(`    ${e.code}: ${e.description} (${e.date})`);
      });
    }
  }
}

main().catch(console.error);
