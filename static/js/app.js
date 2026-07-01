const REGISTER_DEFS = [
  { key: 'AC', bits: 16 }, { key: 'PC', bits: 12 }, { key: 'AR', bits: 12 },
  { key: 'DR', bits: 16 }, { key: 'IR', bits: 16 }, { key: 'TR', bits: 16 },
  { key: 'INPR', bits: 8 }, { key: 'OUTR', bits: 8 }, { key: 'SC', bits: 4 },
  { key: 'E', bits: 1 }
];

const DEFAULT_PROGRAM =
`/ 
ORG 0
LDA A
ADD B
STA C
HLT
A, DEC 5
B, DEC 3
C, DEC 0
END
`;

let lastMachineCode = { start_addr: 0, machine_code: [] };
let memoryCache = {};
let runPolling = false;

const el = (id) => document.getElementById(id);

function toBin(value, bits) {
  return (value >>> 0).toString(2).padStart(bits, '0');
}
function toHex(value, bits) {
  const digits = Math.ceil(bits / 4);
  return (value >>> 0).toString(16).toUpperCase().padStart(digits, '0');
}

/* ---------------- editor / line numbers ---------------- */
function refreshLineNumbers() {
  const lines = el('codeEditor').value.split('\n').length;
  let out = '';
  for (let i = 1; i <= lines; i++) out += i + '\n';
  el('lineNumbers').textContent = out;
}

/* ---------------- register grid ---------------- */
function buildRegisterGrid() {
  const grid = el('registerGrid');
  grid.innerHTML = '';
  REGISTER_DEFS.forEach(({ key, bits }) => {
    const card = document.createElement('div');
    card.className = 'reg-card';
    card.id = 'reg-' + key;
    card.innerHTML = `
      <div class="reg-name">${key}</div>
      <div class="reg-hex" id="reg-${key}-hex">0000</div>
      <div class="reg-bin" id="reg-${key}-bin">0000</div>
    `;
    grid.appendChild(card);
  });
}

function renderRegisters(state) {
  REGISTER_DEFS.forEach(({ key, bits }) => {
    const val = state[key] ?? 0;
    el(`reg-${key}-hex`).textContent = toHex(val, bits) + 'h';
    el(`reg-${key}-bin`).textContent = toBin(val, bits);
    const card = el('reg-' + key);
    card.classList.remove('lit', 'lit-out');
    if (state.bus) {
      if (state.bus.dst === key) card.classList.add('lit');
      else if (state.bus.src === key) card.classList.add('lit-out');
    }
  });

  setFlag('flagE', state.E);
  setFlag('flagI', state.I);
  setFlag('flagIEN', state.IEN);
  setFlag('flagFGI', state.FGI);
  setFlag('flagFGO', state.FGO);
  el('flagMnemonic').querySelector('.flag-val').textContent = state.mnemonic || '—';

  document.querySelectorAll('.cycle-step').forEach(stepEl => {
    stepEl.classList.toggle('active', stepEl.dataset.phase === state.phase);
  });

  const runLed = el('runLed');
  const runLabel = el('runLabel');
  if (state.halted) {
    runLed.classList.add('halted');
    runLabel.textContent = 'HALTED';
  } else {
    runLed.classList.remove('halted');
    runLabel.textContent = 'RUNNING';
  }

  el('cycleCount').textContent = `${state.cycle_count} cycles`;

  if (state.bus && state.bus.src) {
    el('busLabel').textContent = `${state.bus.src} → ${state.bus.dst}  (${toHex(state.bus.value, 16)}h)`;
    el('busLabel').classList.add('active');
    pulseBus();
  } else {
    el('busLabel').textContent = '—';
    el('busLabel').classList.remove('active');
  }

  renderHistory(state.history || []);
}

function setFlag(id, value) {
  const node = el(id);
  node.querySelector('.flag-val').textContent = value;
  node.classList.toggle('set', !!value);
}

function pulseBus() {
  const pulse = el('busPulse');
  pulse.style.transition = 'none';
  pulse.style.opacity = '1';
  pulse.style.left = '0%';
  pulse.style.width = '100%';
  requestAnimationFrame(() => {
    pulse.style.transition = 'opacity .5s ease';
    pulse.style.opacity = '0';
  });
}

/* ---------------- history / log ---------------- */
function renderHistory(history) {
  const list = el('logList');
  list.innerHTML = '';
  history.slice().reverse().forEach(h => {
    const row = document.createElement('div');
    row.className = 'log-row';
    row.innerHTML = `<span class="log-time">${h.time}</span><span class="log-phase">${h.phase}</span><span class="log-msg">${h.message}</span>`;
    list.appendChild(row);
  });
}

/* ---------------- memory table ---------------- */
function renderMemory(state) {
  const body = el('memoryBody');
  const filter = el('memSearch').value.trim().toUpperCase();
  body.innerHTML = '';

  const start = 0;
  const visibleCount = 256;
  for (let addr = start; addr < start + visibleCount; addr++) {
    const hexAddr = toHex(addr, 12);
    if (filter && !hexAddr.includes(filter)) continue;
    const value = memoryCache[addr] ?? 0;
    const tr = document.createElement('tr');
    if (value !== 0) tr.classList.add('nonzero');
    if (state && addr === state.PC) tr.classList.add('pc-row');
    else if (state && addr === state.AR) tr.classList.add('ar-row');
    tr.innerHTML = `<td>${hexAddr}h</td><td>${toHex(value, 16)}h</td><td>${toBin(value, 16)}</td>`;
    body.appendChild(tr);
  }
}

/* ---------------- API calls ---------------- */
async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
  return res.json();
}
async function apiGet(url) {
  const res = await fetch(url);
  return res.json();
}

function applyMemoryResult(memObj) {
  memoryCache = {};
  Object.entries(memObj || {}).forEach(([addr, val]) => { memoryCache[addr] = val; });
}

async function doAssemble() {
  el('asmErrors').textContent = '';
  el('listing').innerHTML = '';
  el('asmStatus').textContent = 'در حال اسمبل...';
  const source = el('codeEditor').value;
  const result = await apiPost('/api/assemble', { source });

  if (!result.success) {
    el('asmStatus').textContent = 'خطا';
    el('asmErrors').textContent = `خط ${result.line_no}: ${result.message}`;
    return null;
  }
  el('asmStatus').textContent = `موفق — ${result.listing.length} دستور`;
  lastMachineCode = { start_addr: result.start_addr, machine_code: result.machine_code };

  const listing = el('listing');
  listing.innerHTML = '';
  result.listing.forEach(item => {
    const row = document.createElement('div');
    row.innerHTML = `<span class="l-addr">${toHex(item.addr, 12)}h</span><span class="l-word">${toHex(item.word, 16)}h</span><span class="l-src">${item.label ? item.label + ', ' : ''}${item.source}</span>`;
    listing.appendChild(row);
  });
  return result;
}

async function doLoad() {
  let prog = lastMachineCode;
  if (!prog.machine_code.length) {
    const r = await doAssemble();
    if (!r) return;
    prog = lastMachineCode;
  }
  const data = await apiPost('/api/load', prog);
  applyMemoryResult(data.memory);
  renderRegisters(data.state);
  renderMemory(data.state);
}

async function doStep() {
  const data = await apiPost('/api/step', {});
  applyMemoryResult(data.memory);
  renderRegisters(data.state);
  renderMemory(data.state);
}

async function doRun() {
  const data = await apiPost('/api/run', { max_cycles: 200000 });
  applyMemoryResult(data.memory);
  renderRegisters(data.state);
  renderMemory(data.state);
}

async function doReset() {
  const data = await apiPost('/api/reset', {});
  applyMemoryResult(data.memory);
  renderRegisters(data.state);
  renderMemory(data.state);
  el('asmErrors').textContent = '';
  el('listing').innerHTML = '';
  el('asmStatus').textContent = 'آماده';
}

async function refreshState() {
  const data = await apiGet('/api/state');
  applyMemoryResult(data.memory);
  renderRegisters(data.state);
  renderMemory(data.state);
}

/* ---------------- init ---------------- */
function init() {
  buildRegisterGrid();
  el('codeEditor').value = DEFAULT_PROGRAM;
  refreshLineNumbers();

  el('codeEditor').addEventListener('input', refreshLineNumbers);
  el('codeEditor').addEventListener('scroll', () => {
    el('lineNumbers').scrollTop = el('codeEditor').scrollTop;
  });

  el('btnAssemble').addEventListener('click', doAssemble);
  el('btnLoad').addEventListener('click', doLoad);
  el('btnStep').addEventListener('click', doStep);
  el('btnRun').addEventListener('click', doRun);
  el('btnReset').addEventListener('click', doReset);
  el('memSearch').addEventListener('input', () => renderMemory());

  doAssemble().then(() => refreshState());
}

document.addEventListener('DOMContentLoaded', init);
