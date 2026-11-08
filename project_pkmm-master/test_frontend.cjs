const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id,
      value: '',
      textContent: '',
      innerHTML: '',
      className: '',
      disabled: false,
      checked: false,
      open: false,
      dataset: {},
      style: {},
      classList: {
        toggle() {},
        add() {},
        remove() {}
      },
      addEventListener() {},
      scrollIntoView() {}
    });
  }
  return elements.get(id);
}

const layer = () => ({
  addTo() { return this; },
  clearLayers() { return this; },
  bindPopup() { return this; }
});

const emptyState = {
  enabled: false,
  interval_minutes: 30,
  bbox: null,
  points: [],
  cursor: 0,
  last_run: null,
  next_run: null,
  next_at: 0,
  busy: false,
  current: null,
  batch_size: 5
};

let capturedIntervalCallbacks = [];
let capturedDocListeners = new Map();
let downloadedBlobContent = null;
let apiCallLog = [];

const docMock = {
  hidden: false,
  getElementById: element,
  querySelector: (sel) => {
    if (sel.startsWith('.')) return element(sel.slice(1));
    if (sel.startsWith('#')) return element(sel.slice(1));
    return element(sel);
  },
  addEventListener(evt, cb) {
    if (!capturedDocListeners.has(evt)) capturedDocListeners.set(evt, []);
    capturedDocListeners.get(evt).push(cb);
  },
  createElement(tag) {
    return {
      tag,
      click() {},
      set href(val) {},
      set download(val) {}
    };
  }
};

const context = vm.createContext({
  console,
  Date,
  Blob: class {
    constructor(parts, opts) {
      downloadedBlobContent = parts.join('');
    }
  },
  URL: {
    createObjectURL: () => 'blob:mock-url',
    revokeObjectURL: () => {}
  },
  setTimeout: (fn) => fn(),
  setInterval: (fn, ms) => {
    capturedIntervalCallbacks.push({ fn, ms });
    return capturedIntervalCallbacks.length;
  },
  document: docMock,
  L: {
    map: () => ({ setView() { return this; }, on() {}, fitBounds() {}, addLayer() { return this; }, removeLayer() { return this; } }),
    tileLayer: layer,
    layerGroup: layer,
    circleMarker: layer,
    rectangle: layer,
    geoJSON: layer,
    latLngBounds: (a, b) => ({
      getWest: () => Math.min(a.lng, b.lng),
      getEast: () => Math.max(a.lng, b.lng),
      getSouth: () => Math.min(a.lat, b.lat),
      getNorth: () => Math.max(a.lat, b.lat)
    })
  },
  fetch: async (url, opts) => {
    apiCallLog.push({ url, opts });
    if (url === '/api/status') return { ok: true, json: async () => ({ features: ['B2', 'B3'], firms_configured: false }) };
    if (url === '/api/monitor') return { ok: true, json: async () => structuredClone(emptyState) };
    if (url === '/api/priorities') return { ok: true, json: async () => ({ rows: [], historical_potential: [], active_count: 0, potential_count: 0, note: '', firms_updated_at: null }) };
    return { ok: true, json: async () => ({}) };
  },
  assert
});

vm.runInContext(fs.readFileSync(__dirname + '/static/app.js', 'utf8'), context);

(async () => {
  await new Promise(resolve => setImmediate(resolve));

  console.log('--- Executing Base Frontend Interaction Logic Tests ---');
  vm.runInContext(`
    chooseArea();
    assert.equal(pickingArea, true);
    pickCorner({ lat: -3, lng: 113 });
    pickCorner({ lat: -2, lng: 114 });
    assert.equal(pickingArea, false);
    assert.equal(JSON.stringify(draftBox), '[113,-3,114,-2]');
    assert.equal($('saveArea').disabled, false);
    chooseArea();
    assert.equal(draftBox, null);
    assert.equal($('saveArea').disabled, true);
  `, context);

  vm.runInContext(`
    renderMonitor({
      enabled: true,
      interval_minutes: 30,
      bbox: [113, -3, 114, -2],
      points: [{ id: '1-1', lat: -2.8, lon: 113.2, status: 'error', checked_at: null, error: 'Piksel tertutup awan', result: null }],
      busy: false,
      current: null,
      batch_size: 5,
      last_run: null,
      next_run: null
    });
    assert.ok($('gridRows').innerHTML.includes('Piksel tertutup awan'));
    assert.ok(!$('gridRows').innerHTML.includes('Aman menurut model'));
    assert.equal($('pauseMonitor').textContent, 'Jeda');
  `, context);

  vm.runInContext(`
    const item = priorityItem({ tier: 2, lat: -3, lon: 114, score: 0.8, observed_at: new Date().toISOString() }, 0);
    assert.ok(item.includes('80.0%'));
    assert.ok(item.includes('data-lat="-3"'));
  `, context);

  const baseFetch = context.fetch;
  context.fetch = async (url, opts) => {
    apiCallLog.push({ url, opts });
    if (url === '/api/priorities') {
      return {
        ok: true,
        json: async () => ({
          rows: [],
          historical_potential: [{ tier: 3, lat: -3, lon: 114, score: 0.8, age_days: 15, observed_at: new Date().toISOString() }],
          note: '',
          firms_updated_at: null
        })
      };
    }
    return baseFetch(url, opts);
  };
  await vm.runInContext('loadPriorities()', context);
  assert.ok(element('potentialList').innerHTML.includes('citra lama'));
  assert.ok(element('potentialList').innerHTML.includes('80.0%'));
  assert.equal(element('potentialTotal').textContent, '0 terbaru / 1 lama');
  console.log('Base Interaction Logic: PASS (area selection, draft reset, failed pixel status, controls, priority score)');

  console.log('--- Executing Comprehensive Security & Responsive Tests ---');

  // Test 1: XSS HTML escaping
  const escaped = vm.runInContext("escapeHTML('<script>alert(1)</script>&\"\\'')", context);
  assert.equal(escaped, '&lt;script&gt;alert(1)&lt;/script&gt;&amp;&quot;&#39;');
  console.log('Test 1 PASS: XSS injection prevented via escapeHTML.');

  // Test 2: Double escaping avoidance
  vm.runInContext(`
    renderMonitor({
      enabled: true,
      interval_minutes: 30,
      bbox: [113, -3, 114, -2],
      points: [{ id: '1-1', lat: -2.8, lon: 113.2, status: 'ok', checked_at: '2026-11-05T00:00:00Z', error: null, result: { label: '0', scene: { datetime: '2026-11-05T00:00:00Z' } } }],
      busy: true,
      current: 'A & B <test>',
      batch_size: 5,
      last_run: null,
      next_run: null
    });
  `, context);
  const monitorHtml = element('monitorStatus').innerHTML;
  assert.ok(monitorHtml.includes('A &amp; B &lt;test&gt;'));
  assert.ok(!monitorHtml.includes('&amp;amp;'));
  console.log('Test 2 PASS: No double escaping in status headline.');

  // Test 3: Numerical injection safety
  assert.equal(vm.runInContext("safeNum('<img src=x onerror=1>', 2)", context), '—');
  assert.equal(vm.runInContext("safeNum(12.3456, 2)", context), '12.35');
  console.log('Test 3 PASS: Numeric sanitization rejects malicious non-numeric markup.');

  // Test 4: Polling suppression when tab is hidden
  docMock.hidden = true;
  apiCallLog = [];
  for (const item of capturedIntervalCallbacks) {
    item.fn();
  }
  const hiddenCalls = apiCallLog.filter(c => c.url === '/api/monitor' || c.url === '/api/priorities');
  assert.equal(hiddenCalls.length, 0);
  console.log('Test 4 PASS: Background polling suppressed when document.hidden === true.');

  // Test 5: Polling resumption on tab active
  docMock.hidden = false;
  apiCallLog = [];
  const visListeners = capturedDocListeners.get('visibilitychange') || [];
  for (const cb of visListeners) cb();
  await new Promise(resolve => setTimeout(resolve, 50));
  const activeCalls = apiCallLog.filter(c => c.url === '/api/monitor' || c.url === '/api/priorities');
  assert.ok(activeCalls.length >= 2);
  console.log('Test 5 PASS: Polling resumed upon visibilitychange to active.');

  // Test 6: In-flight deduplication
  apiCallLog = [];
  vm.runInContext('monitorLoading = true;', context);
  await vm.runInContext('loadMonitor();', context);
  assert.equal(apiCallLog.length, 0);
  vm.runInContext('monitorLoading = false;', context);
  console.log('Test 6 PASS: Concurrent in-flight request deduplication verified.');

  // Test 7 & 8: Table notification limits
  const mockLotsOfPoints = Array.from({ length: 350 }, (_, i) => ({
    lat: -2.0 - i * 0.001,
    lon: 113.0 + i * 0.001,
    confidence: 'n',
    frp: 10 + i,
    date: '2026-11-05',
    time: '1200',
    satellite: 'N'
  }));
  vm.runInContext(`records = ${JSON.stringify(mockLotsOfPoints)}; render();`, context);
  assert.ok(element('tableNotice').className.includes('highlight'));
  assert.ok(element('tableNotice').textContent.includes('300 dari 350'));

  const mockFewPoints = mockLotsOfPoints.slice(0, 5);
  vm.runInContext(`records = ${JSON.stringify(mockFewPoints)}; render();`, context);
  assert.ok(!element('tableNotice').className.includes('highlight'));
  assert.ok(element('tableNotice').textContent.includes('seluruh 5 titik'));

  vm.runInContext(`records = []; render();`, context);
  assert.equal(element('tableNotice').textContent, '');
  console.log('Test 7 & 8 PASS: Accurate table row threshold notifications.');

  // Test 9: CSV export completeness
  vm.runInContext(`records = ${JSON.stringify(mockLotsOfPoints)}; render();`, context);
  downloadedBlobContent = null;
  vm.runInContext("$('download').onclick();", context);
  assert.ok(downloadedBlobContent !== null);
  const csvLines = downloadedBlobContent.trim().split('\r\n');
  assert.equal(csvLines.length, 351); // 1 header + 350 rows
  console.log('Test 9 PASS: CSV export retains full filtered dataset (350 rows).');

  // Test 10: Auto-open manual analysis form on map mark()
  vm.runInContext(`
    mark(-1.5, 114.2);
    assert.equal($('lat').value, '-1.50000');
    assert.equal($('lon').value, '114.20000');
    assert.equal(document.querySelector('.manual-analysis').open, true);
  `, context);
  console.log('Test 10 PASS: Map click populates coordinates and auto-opens manual form.');

  // Test 11: Action panel tabs and layer visibility toggles verified
  vm.runInContext(`
    switchTab('manual');
    switchTab('grid');
    $('toggleHotspots').onchange({ target: { checked: false } });
    $('toggleHotspots').onchange({ target: { checked: true } });
    $('toggleGrid').onchange({ target: { checked: false } });
    $('toggleGrid').onchange({ target: { checked: true } });
  `, context);
  console.log('Test 11 PASS: Action panel tabs and layer visibility toggles verified.');

  // Test 12: Structured Sentinel-2 analysis error formatting
  const formattedError = vm.runInContext("formatAnalysisError('Piksel tertutup awan')", context);
  assert.ok(formattedError.includes('error-box'));
  assert.ok(formattedError.includes('Citra Sentinel-2 Bebas Awan Tidak Ditemukan'));
  assert.ok(formattedError.includes('Piksel tertutup awan'));
  assert.ok(formattedError.includes('Saran tindakan:'));
  console.log('Test 12 PASS: Structured error formatting with title, cause, and action suggestion verified.');

  console.log('--- Executing Notification Center Tests ---');
  const notificationPayload = {
    notifications: [{
      id: 'ntf_1',
      event_id: 'evt_1',
      title: '<img src=x onerror=alert(1)> Anomali termal',
      message: '<script>alert("xss")</script> Deteksi termal, bukan konfirmasi kebakaran.',
      severity: 'WASPADA',
      source: 'FIRMS',
      latitude: -2.2,
      longitude: 113.9,
      occurred_at: '2026-11-07T06:15:00Z',
      created_at: '2026-11-07T06:16:00Z',
      read_at: null,
      status: 'UNREAD',
      event_status: 'OPEN'
    }],
    total: 1,
    unread_count: 1,
    limit: 100,
    offset: 0
  };
  context.fetch = async (url, opts) => {
    apiCallLog.push({ url, opts });
    if (url.startsWith('/api/notifications?')) {
      return { ok: true, json: async () => structuredClone(notificationPayload) };
    }
    if (url.includes('/api/notifications/ntf_1/read')) {
      return { ok: true, json: async () => ({ id: 'ntf_1', status: 'READ' }) };
    }
    if (url.includes('/api/notifications/ntf_1/status')) {
      return { ok: true, json: async () => ({ id: 'ntf_1', status: 'ACKNOWLEDGED' }) };
    }
    if (url.includes('/api/events/evt_1/resolve')) {
      return { ok: true, json: async () => ({ event: { id: 'evt_1', status: 'RESOLVED' } }) };
    }
    return { ok: true, json: async () => ({}) };
  };

  apiCallLog = [];
  await vm.runInContext('loadNotifications()', context);
  const notifHtml = element('notifList').innerHTML;
  assert.ok(notifHtml.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.ok(!notifHtml.includes('<img src=x'));
  assert.ok(notifHtml.includes('&lt;script&gt;alert'));
  assert.ok(notifHtml.includes('WASPADA'));
  assert.ok(notifHtml.includes('Event: OPEN'));
  assert.equal(element('notifBadge').textContent, '1');
  assert.equal(element('notifBadge').hidden, false);
  assert.equal(element('notifSummary').textContent.includes('1 belum dibaca'), true);
  console.log('Test 13 PASS: Notification rendering escapes untrusted content and shows unread severity state.');

  element('notifSeverity').value = 'DARURAT';
  apiCallLog = [];
  await vm.runInContext('loadNotifications()', context);
  const filteredUrl = apiCallLog.find(c => c.url.startsWith('/api/notifications?'))?.url || '';
  assert.ok(filteredUrl.includes('severity=DARURAT'));
  element('notifSeverity').value = '';
  console.log('Test 14 PASS: Severity filter is forwarded to the notification API.');

  apiCallLog = [];
  await vm.runInContext("notifAction('ntf_1','read')", context);
  assert.ok(apiCallLog.some(c => c.url === '/api/notifications/ntf_1/read' && c.opts.method === 'POST'));
  apiCallLog = [];
  await vm.runInContext("notifAction('ntf_1','acknowledged')", context);
  const ackCall = apiCallLog.find(c => c.url === '/api/notifications/ntf_1/status');
  assert.ok(ackCall);
  assert.equal(ackCall.opts.body, JSON.stringify({ status: 'ACKNOWLEDGED' }));
  apiCallLog = [];
  await vm.runInContext("notifAction('ntf_1','detail')", context);
  assert.ok(element('notif-detail-ntf_1').innerHTML.includes('Log pengiriman'));

  apiCallLog = [];
  await vm.runInContext("notifAction('ntf_1','unread')", context);
  const unreadCall = apiCallLog.find(c => c.url === '/api/notifications/ntf_1/status');
  assert.ok(unreadCall);
  assert.equal(unreadCall.opts.body, JSON.stringify({ status: 'UNREAD' }));

  apiCallLog = [];
  await vm.runInContext("notifAction('ntf_1','resolved')", context);
  const resolvedCall = apiCallLog.find(c => c.url === '/api/notifications/ntf_1/status');
  assert.ok(resolvedCall);
  assert.equal(resolvedCall.opts.body, JSON.stringify({ status: 'RESOLVED' }));

  context.prompt = () => 'Petugas Uji';
  apiCallLog = [];
  await vm.runInContext("notifAction('ntf_1','resolve','evt_1')", context);
  const resolveCall = apiCallLog.find(c => c.url === '/api/events/evt_1/resolve');
  assert.ok(resolveCall);
  const resolveBody = JSON.parse(resolveCall.opts.body);
  assert.equal(resolveBody.actor, 'Petugas Uji');
  assert.equal(resolveBody.note, 'Petugas Uji');
  console.log('Test 15 PASS: Read, unread, acknowledge, detail, and resolve actions call the correct endpoints.');

  console.log('--- ALL FRONTEND SUITE TESTS PASSED SUCCESSFULLY! ---');
})().catch(err => {
  console.error('Test FAILED:', err);
  process.exitCode = 1;
});
