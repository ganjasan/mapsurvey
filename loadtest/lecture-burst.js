// Lecture-hall burst: reproduces the failure a lecturer hit on 2026-07-13, when
// ~45 students opened a one-question point survey at once and the single gunicorn
// sync worker serialized them into 502s.
//
// Each iteration models one student's browser with a cold cache: load the section
// page, pull the same-origin assets it references (Leaflet, Bootstrap, jQuery and
// htmx come from external CDNs and never touch our server), pause to place a pin,
// then submit.
//
// Run against a Render PR preview — never production. See loadtest/README.md.
//
//   k6 run -e BASE_URL=https://<preview>.onrender.com -e SURVEY=<uuid> lecture-burst.js

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = (__ENV.BASE_URL || '').replace(/\/$/, '');
const SURVEY = __ENV.SURVEY || '';
// 25 concurrent, arriving over 30 s. k6 sends everything from ONE source IP,
// which real students never do — push much past this and Render's edge
// anti-abuse starts serving instant 502s (17 ms, fixed ~218 KB body) that the
// app never sees, and the run measures Render's DDoS protection instead of
// gunicorn. Watch for that signature before trusting any run.
const STUDENTS = Number(__ENV.STUDENTS || 25);
const RAMP = __ENV.RAMP || '30s';

if (!BASE_URL || !SURVEY) {
  throw new Error('BASE_URL and SURVEY are required: k6 run -e BASE_URL=... -e SURVEY=... lecture-burst.js');
}

const SECTION_URL = `${BASE_URL}/surveys/${SURVEY}/section_1/`;

const serverErrors = new Counter('server_errors');
const edgeThrottled = new Counter('edge_throttled');
const pageLoad = new Trend('page_load_ms', true);
const submitOk = new Rate('submit_success');
const assetsPerPage = new Trend('assets_per_page');

export const options = {
  scenarios: {
    lecture: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: RAMP, target: STUDENTS },  // the link goes up on the slide
        { duration: '1m', target: STUDENTS },  // everyone works through it
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '20s',
    },
  },
  thresholds: {
    // The whole point of the exercise: nobody should see an error page.
    server_errors: ['count==0'],
    // Non-zero means the single-IP test tripped Render's edge protection and
    // the run is invalid — rerun with lower STUDENTS, don't read the numbers.
    edge_throttled: ['count==0'],
    page_load_ms: ['p(95)<3000'],
    submit_success: ['rate>0.99'],
  },
};

function track(res, label) {
  if (res.status >= 500 || res.status === 0) {
    // Render's per-IP anti-abuse answers instantly with a fixed ~218 KB error
    // page. Those 502s never reached the app — count them separately: if this
    // metric is non-zero the run measured Render's edge, not our gunicorn, and
    // must be redone at lower concurrency.
    if (res.status === 502 && res.body && res.body.length > 100000) {
      edgeThrottled.add(1, { label });
    } else {
      serverErrors.add(1, { label, status: String(res.status) });
    }
  }
  return res;
}

// Asset URLs are read from the rendered page rather than hardcoded: with manifest
// static storage the filenames carry a content hash, so the fixed build and the
// baseline build reference different URLs for the same files. Parsing keeps both
// runs faithful to what a real browser would fetch.
function sameOriginAssets(body) {
  if (!body) return [];
  const found = new Set();
  const matches = body.match(/(?:src|href)="\/staticfiles\/[^"]+"/g) || [];
  matches.forEach((raw) => {
    found.add(raw.slice(raw.indexOf('"') + 1, -1));
  });
  return Array.from(found);
}

export function setup() {
  // Wake the instance so the first measured VU does not absorb container start.
  const warm = http.get(SECTION_URL, { tags: { label: 'warmup' } });
  if (warm.status !== 200) {
    throw new Error(
      `warm-up failed: HTTP ${warm.status} on ${SECTION_URL} — is the survey seeded and published? ` +
      `Run: python manage.py seed_loadtest_survey`,
    );
  }
  const assets = sameOriginAssets(warm.body);
  if (assets.length === 0) {
    throw new Error('warm-up page referenced no /staticfiles/ assets — the page did not render as expected');
  }
  console.log(`warm-up ok — page references ${assets.length} same-origin assets`);
  return { assetCount: assets.length };
}

export default function () {
  // Every iteration is a different student, so start from a clean session.
  http.cookieJar().clear(BASE_URL);

  let csrf = null;
  let assets = [];

  group('open survey page', () => {
    const res = track(http.get(SECTION_URL, { tags: { label: 'section_page' } }), 'section_page');
    pageLoad.add(res.timings.duration);
    check(res, {
      'page 200': (r) => r.status === 200,
      'page has map': (r) => !!r.body && r.body.includes('leaflet'),
    });

    const m = res.body && res.body.match(/name="csrfmiddlewaretoken"\s+value="([^"]+)"/);
    csrf = m ? m[1] : null;
    assets = sameOriginAssets(res.body);
    assetsPerPage.add(assets.length);
  });

  group('page assets', () => {
    // Sequential, not http.batch: a browser opens ~6 parallel connections, but
    // 25 VUs x 6 from a single IP trips Render's edge anti-abuse (see STUDENTS
    // comment). Sequential keeps concurrency at one connection per VU — the
    // trade-off is that per-student page time is understated slightly.
    assets.forEach((path) => {
      const res = track(http.get(`${BASE_URL}${path}`, { tags: { label: 'asset' } }), 'asset');
      check(res, { 'asset served': (r) => r.status === 200 || r.status === 304 });
    });
  });

  // A student reading the question and placing a pin.
  sleep(Math.random() * 5 + 3);

  group('submit answer', () => {
    if (!csrf) {
      submitOk.add(false);
      return;
    }
    // The view splits this field on '|' and reads gj['geometry'] / gj['properties'],
    // so each entry must be a GeoJSON *Feature*, not a bare geometry.
    const feature = JSON.stringify({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [13.405 + Math.random() * 0.2, 52.52 + Math.random() * 0.2],
      },
      properties: {},
    });
    const res = track(
      http.post(
        SECTION_URL,
        { csrfmiddlewaretoken: csrf, Q001: feature },
        { headers: { Referer: SECTION_URL, 'HX-Request': 'true' }, tags: { label: 'submit' } },
      ),
      'submit',
    );
    // A completed survey answers with 200 + HX-Redirect to the thanks page. Status
    // alone is not enough — a re-rendered form also returns 200.
    const ok = res.status === 302 || (res.status === 200 && !!res.headers['Hx-Redirect']);
    submitOk.add(ok);
    check(res, { 'submit accepted': () => ok });
  });
}

export function handleSummary(data) {
  const m = data.metrics;
  const errs = m.server_errors ? m.server_errors.values.count : 0;
  const throttled = m.edge_throttled ? m.edge_throttled.values.count : 0;
  const p95 = m.page_load_ms ? Math.round(m.page_load_ms.values['p(95)']) : 0;
  const submit = m.submit_success ? (m.submit_success.values.rate * 100).toFixed(1) : 'n/a';
  const reqs = m.http_reqs ? m.http_reqs.values.count : 0;
  const lines = [
    '',
    `  students (peak VUs):  ${STUDENTS}`,
    `  total requests:       ${reqs}`,
    `  5xx / dropped:        ${errs}`,
    `  page load p95:        ${p95} ms`,
    `  submits accepted:     ${submit}%`,
    '',
  ];
  if (throttled > 0) {
    lines.push(`  !! RUN INVALID: ${throttled} responses came from Render's per-IP edge`);
    lines.push('     protection, not the app. Rerun with lower -e STUDENTS.');
    lines.push('');
  }
  return {
    stdout: lines.join('\n'),
    'summary.json': JSON.stringify(data, null, 2),
  };
}
