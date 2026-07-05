/* ═══════════════════════════════════════════════════════════════════
   EduMind — front-end app logic
   ═══════════════════════════════════════════════════════════════════ */
let API = localStorage.getItem('EDUMIND_API_URL');
if (!API) {
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    API = 'http://localhost:8000';
  } else {
    API = window.location.origin;
  }
}

function setApiUrl(val) {
  const cleanVal = val.trim();
  if (cleanVal) {
    localStorage.setItem('EDUMIND_API_URL', cleanVal);
    API = cleanVal;
  } else {
    localStorage.removeItem('EDUMIND_API_URL');
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      API = 'http://localhost:8000';
    } else {
      API = window.location.origin;
    }
  }
  if (document.getElementById('landingApiUrl')) document.getElementById('landingApiUrl').value = API;
  if (document.getElementById('apiUrl')) document.getElementById('apiUrl').value = API;
}

const S = {
  user: null, role: null, token: null, isPublic: false,
  sessionId: null, view: 'home', messages: [], history: [], busy: false,
};

/* ── SVG icon set (stroke = currentColor) ──────────────────────────── */
const I = {
  logo: '<svg class="mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v6l9 4 9-4V7"/><path d="M7 9v5"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>',
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.3 7.3L4 21l1.7-5.7A8 8 0 1 1 21 12z"/></svg>',
  chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  grade: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10L12 4 2 10l10 6 10-6z"/><path d="M6 12v5c0 1 2.7 3 6 3s6-2 6-3v-5"/></svg>',
  calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14z"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/></svg>',
  doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/></svg>',
  flask: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/><path d="M7 14h10"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.9 21l1.2-6.8-5-4.9 6.9-1L12 2z"/></svg>',
  pulse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5M12 3v12"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>',
  eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8"/></svg>',
  bolt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/></svg>',
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
  logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>',
  chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>',
  history: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/></svg>',
};

/* big decorative orb svg for the landing */
const ORB = `<svg class="orb" viewBox="0 0 520 520" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs><radialGradient id="g" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="0.08"/>
    <stop offset="60%" stop-color="#ffffff" stop-opacity="0.02"/>
    <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/></radialGradient></defs>
  <circle cx="260" cy="260" r="258" stroke="#ffffff" stroke-opacity="0.05"/>
  <circle cx="260" cy="260" r="200" stroke="#ffffff" stroke-opacity="0.06"/>
  <circle cx="260" cy="260" r="140" stroke="#ffffff" stroke-opacity="0.08"/>
  <circle cx="260" cy="260" r="80" stroke="#ffffff" stroke-opacity="0.18"/>
  <circle cx="260" cy="260" r="258" fill="url(#g)"/>
  <circle cx="260" cy="2" r="4" fill="#ffffff"/>
  <circle cx="460" cy="260" r="3" fill="#ffffff" fill-opacity="0.5"/>
  <circle cx="120" cy="120" r="2.5" fill="#ffffff" fill-opacity="0.4"/>
</svg>`;

const $ = (id) => document.getElementById(id);
const esc = (t) => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };
const now = () => new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
const initials = (n) => n.replace(/_/g, ' ').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();

/* ═══════════════════════════════════════════════════════════════════ LANDING */
function renderLanding() {
  $('app').innerHTML = `
  <div class="landing">
    <div class="landing-bg"><div class="dots"></div></div>
    ${ORB}
    <nav class="nav">
      <div class="brand">${I.logo}<span><b>EduMind</b><span class="dot-accent">.</span></span></div>
      <div class="nav-links">
        <button class="btn btn-ghost" onclick="openLogin()">Sign in</button>
        <button class="btn btn-accent" onclick="enterGuest()">Get started ${I.bolt}</button>
      </div>
    </nav>

    <section class="hero">
      <div class="eyebrow"><span class="pulse"></span> AI knowledge engine · live</div>
      <h1>Every institutional<br>answer, <em>instantly</em>.</h1>
      <p>Search policies, procedures, academics and operations through one intelligent assistant. Role-aware. Source-cited. No friction.</p>
      <div class="hero-cta">
        <button class="btn btn-accent btn-lg" onclick="enterGuest()">Explore as guest ${I.send}</button>
        <button class="btn btn-outline btn-lg" onclick="openLogin()">Sign in for more</button>
        <span class="hero-note">${I.lock} No account needed to browse</span>
      </div>
      <div class="api-config-strip" style="margin-top: 1.5rem; display: flex; align-items: center; justify-content: center; gap: 0.5rem; font-size: 0.8rem; color: var(--text-3); z-index: 10; position: relative;">
        <span>API Endpoint:</span>
        <input id="landingApiUrl" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; padding: 0.25rem 0.5rem; color: var(--text-2); font-family: monospace; font-size: 0.75rem; width: 220px;" placeholder="http://localhost:8000" value="${API || ''}" onchange="setApiUrl(this.value)">
      </div>
    </section>

    <div class="feature-strip">
      <div class="feature"><span class="ic">${I.bolt}</span><h4>Instant answers</h4><span>Sub-second responses across the entire knowledge base.</span></div>
      <div class="feature"><span class="ic">${I.shield}</span><h4>Role-aware access</h4><span>Public, student, faculty and admin each see the right depth.</span></div>
      <div class="feature"><span class="ic">${I.doc}</span><h4>Source-cited</h4><span>Every answer references the documents it came from.</span></div>
    </div>
  </div>

  <div id="loginModal" class="modal">
    <div class="modal-card">
      <button class="x" onclick="closeLogin()">${I.x}</button>
      ${I.logo.replace('class="mark"', 'class="mark-lg"')}
      <h2>Welcome back</h2>
      <p class="sub">Sign in to unlock your personalised workspace.</p>
      <div class="modal-err" id="loginErr"></div>
      <form onsubmit="doLogin(event)">
        <div class="field"><label>Username</label><input id="u" placeholder="e.g. student_test" autocomplete="off" required></div>
        <div class="field"><label>Password</label><input id="p" type="password" placeholder="••••••••" required></div>
        <div class="field"><label>API Endpoint</label><input id="apiUrl" placeholder="http://localhost:8000" value="${API || ''}" autocomplete="off" onchange="setApiUrl(this.value)"></div>
        <button type="submit" class="modal-submit">Continue</button>
      </form>
      <div class="demo-box">
        <div class="lbl">Demo accounts · click to fill</div>
        <div class="demo-row" onclick="fill('student_test','Student@123')"><span class="who">${I.grade} student_test</span><span class="pw">Student@123</span></div>
        <div class="demo-row" onclick="fill('faculty_test','Faculty@123')"><span class="who">${I.flask} faculty_test</span><span class="pw">Faculty@123</span></div>
        <div class="demo-row" onclick="fill('admin_test','Admin@123')"><span class="who">${I.shield} admin_test</span><span class="pw">Admin@123</span></div>
      </div>
    </div>
  </div>`;
}

const openLogin = () => {
  $('loginModal').classList.add('active');
  $('apiUrl').value = API;
};
const closeLogin = () => $('loginModal').classList.remove('active');
const fill = (u, p) => { $('u').value = u; $('p').value = p; };

async function doLogin(e) {
  e.preventDefault();
  const err = $('loginErr');
  const endpoint = $('apiUrl').value.trim();
  setApiUrl(endpoint);
  try {
    const r = await fetch(`${API}/api/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: $('u').value, password: $('p').value }),
    });
    if (r.ok) {
      const d = await r.json();
      S.token = d.access_token; S.user = d.username; S.role = d.role; S.isPublic = false;
      await loadHistory();
      renderApp();
    } else { err.textContent = 'Invalid username or password.'; err.classList.add('show'); }
  } catch { err.textContent = 'Cannot reach server. Is the backend running?'; err.classList.add('show'); }
}

function enterGuest() {
  S.isPublic = true; S.user = 'Guest'; S.role = 'Public'; S.token = null;
  S.messages = []; S.sessionId = null;
  renderApp();
}

/* ═══════════════════════════════════════════════════════════════════ NAV CONFIG */
const NAV = {
  Public:  [['home', 'Home', I.home], ['chat', 'Assistant', I.chat]],
  Student: [['home', 'Dashboard', I.home], ['grades', 'Grades', I.grade], ['attendance', 'Attendance', I.calendar], ['chat', 'Assistant', I.chat]],
  Faculty: [['home', 'Dashboard', I.home], ['analytics', 'Analytics', I.chart], ['research', 'Research', I.flask], ['chat', 'Assistant', I.chat]],
  Admin:   [['home', 'Dashboard', I.home], ['users', 'Users', I.users], ['documents', 'Documents', I.doc], ['chat', 'Assistant', I.chat]],
};
const ROLE_ICON = { Public: I.eye, Student: I.grade, Faculty: I.flask, Admin: I.shield };

const SUGGEST = {
  Public:  ['What programmes are offered?', 'How do I apply for admission?', 'Where is the campus located?'],
  Student: ['What are the exam guidelines?', 'How do I apply for a scholarship?', 'When does the semester start?'],
  Faculty: ['Summarise the examination SOP', 'Research grant deadlines?', 'Faculty leave policy?'],
  Admin:   ['Admin circulars for Q1', 'Document ingestion status', 'Summarise research grant SOP'],
};

/* ═══════════════════════════════════════════════════════════════════ APP SHELL */
function renderApp() {
  const nav = NAV[S.role] || NAV.Public;
  $('app').innerHTML = `
  <div class="shell">
    <aside class="side">
      <div class="side-brand">${I.logo}<span>EduMind</span></div>
      ${S.isPublic ? '' : `<div class="usr"><div class="av">${initials(S.user)}</div><div class="meta"><div class="nm">${esc(S.user)}</div><div class="rl">${S.role}</div></div></div>`}
      <div class="nav-group">
        <div class="t">Menu</div>
        ${nav.map(([id, label, ic]) => `<div class="nav-item ${id === S.view ? 'active' : ''}" onclick="go('${id}')"><span class="ic">${ic}</span>${label}</div>`).join('')}
      </div>
      ${S.isPublic ? '' : `
      <div class="nav-group hist-group">
        <div class="t hist-head"><span>History</span><button class="newchat" title="New chat" onclick="newChat()">${I.plus}</button></div>
        <div class="histlist" id="histList"></div>
      </div>`}
      <div class="side-foot">
        <button class="logout" onclick="logout()">${I.logout} ${S.isPublic ? 'Exit' : 'Sign out'}</button>
      </div>
    </aside>
    <main class="main">
      <div class="topbar">
        <div class="title" id="topTitle"></div>
        <div class="right">
          <span class="chip"><span class="live"></span> ${S.isPublic ? 'Guest session' : S.role + ' access'}</span>
        </div>
      </div>
      <div class="scroll" id="scroll"></div>
    </main>
  </div>`;
  go(S.view === 'home' || NAV[S.role].some(n => n[0] === S.view) ? S.view : 'home');
  renderHistory();
}

function go(view) {
  S.view = view;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const idx = (NAV[S.role] || NAV.Public).findIndex(n => n[0] === view);
  const items = document.querySelectorAll('.nav-item');
  if (items[idx]) items[idx].classList.add('active');

  const titles = {
    home: `Welcome back<span class="greet"> · ${S.user}</span>`,
    chat: 'Assistant', grades: 'My grades', attendance: 'Attendance',
    analytics: 'Analytics', research: 'Research', users: 'User directory', documents: 'Documents',
  };
  $('topTitle').innerHTML = titles[view] || 'EduMind';

  const scroll = $('scroll');
  if (view === 'chat') { scroll.innerHTML = `<div class="view">${chatHTML()}</div>`; mountChat(); }
  else if (view === 'documents') { scroll.innerHTML = `<div class="view">${documentsHTML()}</div>`; }
  else if (view === 'users') { scroll.innerHTML = `<div class="view">${usersHTML()}</div>`; }
  else { scroll.innerHTML = `<div class="view">${dashboardHTML(view)}</div>`; }
}

/* ═══════════════════════════════════════════════════════════════════ DASHBOARDS */
function spark(vals, hotIdx) {
  return `<div class="spark">${vals.map((v, i) => `<i class="${i === hotIdx ? 'on' : ''}" style="height:${v}%"></i>`).join('')}</div>`;
}
function ring(pct, color = 'var(--accent)') {
  const r = 26, c = 2 * Math.PI * r, off = c * (1 - pct / 100);
  return `<svg width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="${r}" fill="none" stroke="var(--surface-3)" stroke-width="6"/><circle cx="32" cy="32" r="${r}" fill="none" stroke="${color}" stroke-width="6" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 32 32)"/></svg>`;
}

function dashboardHTML(view) {
  if (S.role === 'Public') {
    return `
    <div class="bento">
      <div class="tile span-2"><div class="ic-box hot">${I.spark}</div><div class="val">EduMind AI</div><div class="lbl">Ask anything about the institution — admissions, programmes, campus and more.</div></div>
      <div class="tile"><div class="ic-box">${I.book}</div><div class="val">120+</div><div class="lbl">Public documents</div></div>
      <div class="tile"><div class="ic-box">${I.users}</div><div class="val">8.4k</div><div class="lbl">Students enrolled</div></div>
    </div>
    <div class="sec-head"><h3>Try the assistant</h3><span class="more" onclick="go('chat')">Open ${I.chevron}</span></div>
    ${chatHTML()}` + afterMount();
  }
  if (S.role === 'Student') {
    return `
    <div class="bento">
      <div class="tile"><span class="trend up">+0.12</span><div class="ic-box hot">${I.grade}</div><div class="val">3.85</div><div class="lbl">Current GPA</div></div>
      <div class="tile span-2"><div class="ic-box">${I.calendar}</div><div class="ring-wrap">${ring(92)}<div class="ring-meta"><div class="big">92%</div><div class="small">Attendance this semester · 8 absences allowed</div></div></div></div>
      <div class="tile"><span class="trend up">2 due</span><div class="ic-box">${I.book}</div><div class="val">6</div><div class="lbl">Active courses</div></div>
      <div class="tile span-2"><div class="ic-box">${I.chart}</div><div class="lbl" style="margin-bottom:.2rem">Performance trend</div><div class="val" style="font-size:1.3rem">Steady ↗</div>${spark([40, 55, 48, 62, 70, 66, 82], 6)}</div>
      <div class="tile"><div class="ic-box">${I.pulse}</div><div class="val">8</div><div class="lbl">Assignments</div></div>
    </div>
    <div class="sec-head"><h3>Knowledge assistant</h3><span class="more" onclick="go('chat')">Full screen ${I.chevron}</span></div>
    ${chatHTML()}` + afterMount();
  }
  if (S.role === 'Faculty') {
    return `
    <div class="bento">
      <div class="tile"><span class="trend up">+14</span><div class="ic-box hot">${I.users}</div><div class="val">124</div><div class="lbl">Students taught</div></div>
      <div class="tile"><div class="ic-box">${I.book}</div><div class="val">4</div><div class="lbl">Active courses</div></div>
      <div class="tile"><span class="trend up">+2</span><div class="ic-box">${I.flask}</div><div class="val">7</div><div class="lbl">Papers published</div></div>
      <div class="tile span-2"><div class="ic-box">${I.chart}</div><div class="lbl" style="margin-bottom:.2rem">Student engagement</div><div class="val" style="font-size:1.3rem">High</div>${spark([50, 62, 58, 70, 65, 80, 88], 6)}</div>
      <div class="tile"><div class="ring-wrap">${ring(92, 'var(--accent)')}<div class="ring-meta"><div class="big">4.6</div><div class="small">Avg rating</div></div></div></div>
    </div>
    <div class="sec-head"><h3>Knowledge assistant</h3><span class="more" onclick="go('chat')">Full screen ${I.chevron}</span></div>
    ${chatHTML()}` + afterMount();
  }
  /* Admin */
  return `
  <div class="bento">
    <div class="tile"><span class="trend up">+128</span><div class="ic-box hot">${I.users}</div><div class="val">2,547</div><div class="lbl">Total users</div></div>
    <div class="tile"><span class="trend up">+12</span><div class="ic-box">${I.doc}</div><div class="val">342</div><div class="lbl">Documents indexed</div></div>
    <div class="tile span-2"><div class="ic-box">${I.chart}</div><div class="lbl" style="margin-bottom:.2rem">AI queries · 30 days</div><div class="val" style="font-size:1.3rem">12,540</div>${spark([30, 45, 40, 58, 52, 72, 90], 6)}</div>
    <div class="tile span-2"><div class="ring-wrap">${ring(99.8)}<div class="ring-meta"><div class="big">99.8%</div><div class="small">System uptime · all services healthy</div></div></div></div>
    <div class="tile"><div class="ic-box">${I.pulse}</div><div class="val">4</div><div class="lbl">User roles</div></div>
  </div>
  <div class="sec-head"><h3>Knowledge assistant</h3><span class="more" onclick="go('chat')">Full screen ${I.chevron}</span></div>
  ${chatHTML()}` + afterMount();
}

/* dashboards embed the chat, so mount it after render */
function afterMount() { setTimeout(mountChat, 0); return ''; }

/* ═══════════════════════════════════════════════════════════════════ CHAT */
function chatHTML() {
  return `
  <div class="chat" ${S.view === 'chat' ? 'style="min-height:calc(100vh - 160px)"' : ''}>
    <div class="chat-head">
      <div class="bot-av">${I.spark}</div>
      <div><div class="ht">EduMind Assistant</div><div class="hs">${S.role} knowledge base${S.isPublic ? '' : ' · history saved'}</div></div>
    </div>
    <div class="msgs" id="msgs"></div>
    <div class="composer">
      <div class="inwrap"><input id="q" placeholder="Ask about policies, academics, procedures…" onkeydown="if(event.key==='Enter')sendMsg()"></div>
      <button class="send" id="sendBtn" onclick="sendMsg()">${I.send}</button>
    </div>
  </div>`;
}

function mountChat() {
  const m = $('msgs'); if (!m) return;
  if (S.messages.length === 0) {
    m.innerHTML = `
    <div class="empty">
      <div class="glyph">${I.chat.replace('viewBox="0 0 24 24"', 'viewBox="0 0 24 24" width="38" height="38"')}</div>
      <div><div class="et">Ask me anything</div><div class="es">Policies, exams, scholarships, schedules, facilities and more.</div></div>
      <div class="suggest">${(SUGGEST[S.role] || SUGGEST.Public).map(s => `<button onclick="quick('${s.replace(/'/g, "\\'")}')">${s}</button>`).join('')}</div>
    </div>`;
  } else {
    m.innerHTML = S.messages.map(msgHTML).join('');
    m.scrollTop = m.scrollHeight;
  }
}

function msgHTML(msg) {
  // Authenticated (non-public) users can open the original source document with
  // the answer's chunk highlighted. Guests see the same list, non-clickable.
  const cites = msg.citations || [];
  const canOpen = !!S.token && !S.isPublic;
  let items = '', count = 0;
  if (cites.length) {
    count = cites.length;
    items = cites.map(c => {
      const label = esc(c.display_name || 'Document');
      const ver = c.version ? ` · v${esc(String(c.version))}` : '';
      if (canOpen && c.doc_id) {
        const ci = (c.chunk_index != null ? c.chunk_index : '');
        return `<div class="si si-link" onclick="openDoc('${esc(c.doc_id)}','${ci}')" title="Open source document">
          <span class="ic">${I.doc}</span><span class="si-name">${label}${ver}</span>
          <span class="si-open">Open ${I.eye}</span></div>`;
      }
      return `<div class="si"><span class="ic">${I.doc}</span>${label}${ver}</div>`;
    }).join('');
  } else if (msg.sources && msg.sources.length) {
    count = msg.sources.length;
    items = msg.sources.map(s => `<div class="si"><span class="ic">${I.doc}</span>${esc(s)}</div>`).join('');
  }
  const srcs = count ? `
    <div class="sources">
      <div class="sh" onclick="this.nextElementSibling.classList.toggle('open')">${I.doc} ${count} source${count > 1 ? 's' : ''} ${I.chevron}</div>
      <div class="sl">${items}</div>
    </div>` : '';
  return `
  <div class="msg ${msg.isUser ? 'me' : 'bot'}">
    <div class="av ${msg.isUser ? 'me' : 'bot'}">${msg.isUser ? (S.isPublic ? 'G' : initials(S.user)) : I.spark}</div>
    <div class="body"><div class="bubble">${esc(msg.content)}</div><div class="time">${msg.time || now()}</div>${srcs}</div>
  </div>`;
}

const quick = (t) => { const i = $('q'); if (i) { i.value = t; sendMsg(); } };

async function sendMsg() {
  const input = $('q'); if (!input || !input.value.trim() || S.busy) return;
  const text = input.value.trim(); input.value = '';
  S.messages.push({ content: text, isUser: true, time: now(), sources: [] });
  mountChat();
  S.busy = true; $('sendBtn').disabled = true;

  // typing indicator
  const m = $('msgs');
  const typing = document.createElement('div');
  typing.className = 'msg bot'; typing.id = 'typing';
  typing.innerHTML = `<div class="av bot">${I.spark}</div><div class="body"><div class="bubble"><div class="typing"><i></i><i></i><i></i></div></div></div>`;
  m.appendChild(typing); m.scrollTop = m.scrollHeight;

  // The bot message is created lazily on the first streamed token so the
  // typing indicator stays visible until the model actually starts replying.
  let botIdx = -1;
  const ensureBubble = () => {
    if (botIdx !== -1) return;
    const t = $('typing'); if (t) t.remove();
    botIdx = S.messages.length;
    S.messages.push({ content: '', isUser: false, time: now(), sources: [] });
    mountChat();
  };
  const liveUpdate = () => {
    const bubbles = document.querySelectorAll('.msg.bot .bubble');
    const el = bubbles[bubbles.length - 1];
    // textContent keeps everything escaped (no raw HTML) while .bubble's
    // white-space:pre-wrap preserves the answer's line breaks.
    if (el) { el.textContent = S.messages[botIdx].content; const mm = $('msgs'); if (mm) mm.scrollTop = mm.scrollHeight; }
  };

  try {
    // Authenticated → /api/chat/auth/stream (saves history, emits citations).
    // Guest/public  → /api/chat/stream (role-filtered, emits citations too).
    let url, headers = {};
    if (S.token) {
      headers['Authorization'] = `Bearer ${S.token}`;
      url = `${API}/api/chat/auth/stream?q=${encodeURIComponent(text)}&session_id=${encodeURIComponent(S.sessionId || '')}`;
    } else {
      url = `${API}/api/chat/stream?q=${encodeURIComponent(text)}&role=${encodeURIComponent(S.role || 'Public')}`;
    }

    const resp = await fetch(url, { headers });
    if (!resp.ok || !resp.body) throw new Error('HTTP ' + resp.status);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '', finished = false;

    while (!finished) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();
      for (const part of parts) {
        const match = part.match(/^data: (.*)$/m);
        if (!match) continue;
        const data = match[1];
        if (data === '[DONE]') { finished = true; break; }
        if (data.startsWith('[META]')) {
          try {
            const meta = JSON.parse(data.slice(6));
            ensureBubble();
            S.messages[botIdx].sources = meta.source_documents || [];
            S.messages[botIdx].citations = meta.citations || [];
            if (meta.session_id) S.sessionId = meta.session_id;
          } catch {}
          continue;
        }
        if (data.startsWith('[ERROR')) { ensureBubble(); S.messages[botIdx].content += '\n[Error generating response]'; continue; }
        // Normal token — restore escaped newlines, render live.
        ensureBubble();
        S.messages[botIdx].content += data.replace(/\\n/g, '\n');
        liveUpdate();
      }
    }

    if (botIdx === -1) { ensureBubble(); S.messages[botIdx].content = 'No response received. Please try again.'; }
    mountChat();
    if (S.token) loadHistory().then(renderHistory);
  } catch {
    const t = $('typing'); if (t) t.remove();
    if (botIdx === -1) {
      S.messages.push({ content: 'Cannot reach the server. Make sure the backend is running.', isUser: false, time: now(), sources: [] });
    }
    mountChat();
  } finally {
    S.busy = false; const b = $('sendBtn'); if (b) b.disabled = false;
  }
}

/* ═══════════════════════════════════════════════════════════════════ ADMIN: DOCUMENTS */
function documentsHTML() {
  return `
  <div class="sec-head"><h3>Document ingestion</h3></div>
  <div class="drop" onclick="document.getElementById('file').click()">
    <div class="ic">${I.upload.replace('viewBox="0 0 24 24"', 'viewBox="0 0 24 24" width="34" height="34"')}</div>
    <div class="dt">Drop PDF, DOCX or DOC files, or click to upload</div>
    <div class="ds">SOPs, circulars, examination guidelines — indexed into the knowledge base.</div>
  </div>
  <input type="file" id="file" accept=".pdf,.docx,.doc" multiple style="display:none" onchange="uploadFiles(event)">
  <div id="uplist" style="margin-top:1rem"></div>`;
}

async function uploadFiles(e) {
  const list = $('uplist');
  for (const f of e.target.files) {
    const row = document.createElement('div');
    row.className = 'uprow';
    row.innerHTML = `<div class="l"><span class="ic">${I.doc}</span><div><div class="nm">${esc(f.name)}</div><div class="sz">${(f.size / 1024).toFixed(1)} KB</div></div></div><span class="tag" style="background:var(--surface-2);color:var(--text-3)">uploading…</span>`;
    list.prepend(row);
    const tag = row.querySelector('.tag');
    try {
      const fd = new FormData(); fd.append('file', f);
      const r = await fetch(`${API}/api/upload`, { method: 'POST', headers: { 'Authorization': `Bearer ${S.token}` }, body: fd });
      if (r.ok) { tag.className = 'tag ok'; tag.textContent = 'Indexed'; }
      else { tag.className = 'tag err'; tag.textContent = 'Failed'; }
    } catch { tag.className = 'tag err'; tag.textContent = 'Error'; }
  }
}

/* ═══════════════════════════════════════════════════════════════════ ADMIN: USERS */
async function usersHTML() { return `<div id="uload"><div class="sec-head"><h3>User directory</h3></div><p style="color:var(--text-3);font-size:.88rem">Loading…</p></div>`; }
/* users needs async fetch — handle after render */
function go_users_after() {}

/* override go() handling for users with real fetch */
const _origGo = go;
go = function (view) {
  _origGo(view);
  if (view === 'users') loadUsers();
};

async function loadUsers() {
  const scroll = $('scroll');
  let rows = [
    { username: 'public_user', role: 'Public' }, { username: 'student_test', role: 'Student' },
    { username: 'faculty_test', role: 'Faculty' }, { username: 'admin_test', role: 'Admin' },
  ];
  try {
    const r = await fetch(`${API}/api/users`, { headers: { 'Authorization': `Bearer ${S.token}` } });
    if (r.ok) rows = await r.json();
  } catch {}
  scroll.innerHTML = `<div class="view">
    <div class="sec-head"><h3>User directory</h3><span class="chip">${rows.length} accounts</span></div>
    <div class="utable">
      <div class="hr"><div>User</div><div>Role</div><div>Status</div></div>
      ${rows.map(u => `<div class="rw"><div class="who"><span class="av">${initials(u.username)}</span>${esc(u.username)}</div><div><span class="role-pill">${u.role}</span></div><div><span class="dotok">Active</span></div></div>`).join('')}
    </div>
  </div>`;
}

/* ═══════════════════════════════════════════════════════════════════ HISTORY */
async function loadHistory() {
  if (!S.token) return;
  try {
    const r = await fetch(`${API}/api/history`, { headers: { 'Authorization': `Bearer ${S.token}` } });
    if (r.ok) S.history = await r.json();
  } catch {}
}

function dateLabel(iso) {
  const d = new Date(iso), today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  if (sameDay) return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function renderHistory() {
  const el = $('histList'); if (!el) return;
  if (!S.history.length) { el.innerHTML = `<div class="hist-empty">No conversations yet</div>`; return; }
  el.innerHTML = S.history.map(c => `
    <div class="hist-item ${c.session_id === S.sessionId ? 'active' : ''}" onclick="openConversation('${c.session_id}')">
      <span class="hi-ic">${I.chat}</span>
      <span class="hi-text">${esc(c.preview || 'New conversation')}</span>
      <span class="hi-date">${dateLabel(c.timestamp)}</span>
      <button class="hi-del" title="Delete conversation" onclick="deleteConversation('${c.session_id}', event)">${I.trash}</button>
    </div>`).join('');
}

function newChat() {
  S.messages = []; S.sessionId = null; S.view = 'chat';
  go('chat'); renderHistory();
  const i = $('q'); if (i) i.focus();
}

async function openConversation(id) {
  try {
    const r = await fetch(`${API}/api/history/${id}`, { headers: { 'Authorization': `Bearer ${S.token}` } });
    if (r.ok) {
      const rows = await r.json();
      S.messages = rows.map(m => ({
        content: m.content, isUser: m.is_user, sources: m.sources || [],
        time: new Date(m.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      }));
      S.sessionId = id; S.view = 'chat';
      go('chat'); renderHistory();
    }
  } catch {}
}

async function deleteConversation(id, ev) {
  ev.stopPropagation();
  try { await fetch(`${API}/api/history/${id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${S.token}` } }); } catch {}
  if (S.sessionId === id) { S.messages = []; S.sessionId = null; if (S.view === 'chat') mountChat(); }
  await loadHistory(); renderHistory();
}

/* ═══════════════════════════════════════════════════════════════════ DOCUMENT VIEWER */
/* Clicking a citation opens the original document (RBAC-enforced server-side)
   with the answer's source passage highlighted. Public/guest users never have
   clickable citations, and the endpoint rejects them regardless. */
async function openDoc(docId, chunkIndex) {
  if (!S.token || !docId) return;
  closeDoc();
  const modal = document.createElement('div');
  modal.id = 'docModal'; modal.className = 'doc-modal';
  modal.innerHTML = `
    <div class="doc-modal-card">
      <div class="doc-modal-head">
        <span class="doc-modal-title">${I.doc} Source document</span>
        <div class="doc-modal-actions">
          <button class="doc-dl" id="docDl">Download original</button>
          <button class="doc-x" onclick="closeDoc()" title="Close">${I.x}</button>
        </div>
      </div>
      <div class="doc-modal-body" id="docBody"><div class="doc-loading">Loading document…</div></div>
    </div>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', e => { if (e.target === modal) closeDoc(); });

  const qs = (chunkIndex !== '' && chunkIndex != null) ? `?chunk_index=${encodeURIComponent(chunkIndex)}` : '';
  const body = $('docBody');
  try {
    const r = await fetch(`${API}/api/documents/${docId}/view${qs}`, {
      headers: { 'Authorization': `Bearer ${S.token}` },
    });
    if (r.ok) {
      const docHtml = await r.text();
      const frame = document.createElement('iframe');
      frame.className = 'doc-frame';
      frame.setAttribute('sandbox', 'allow-same-origin allow-scripts');
      frame.srcdoc = docHtml;
      body.innerHTML = ''; body.appendChild(frame);
    } else if (r.status === 403) {
      body.innerHTML = `<div class="doc-err">You don't have permission to open this document.</div>`;
    } else if (r.status === 404) {
      body.innerHTML = `<div class="doc-err">This document is no longer available.</div>`;
    } else {
      body.innerHTML = `<div class="doc-err">Could not load the document (error ${r.status}).</div>`;
    }
  } catch {
    if (body) body.innerHTML = `<div class="doc-err">Cannot reach the server.</div>`;
  }
  const dl = $('docDl'); if (dl) dl.onclick = () => downloadDoc(docId);
}

function closeDoc() { const m = $('docModal'); if (m) m.remove(); }

async function downloadDoc(docId) {
  if (!S.token || !docId) return;
  try {
    const r = await fetch(`${API}/api/documents/${docId}/download`, {
      headers: { 'Authorization': `Bearer ${S.token}` },
    });
    if (!r.ok) {
      if (r.status === 404) {
        try {
          const errData = await r.json();
          if (errData.status === 'missing') {
            alert(errData.message || 'Original source document is not available.');
            return;
          }
        } catch {}
      }
      alert('Could not download original document (error ' + r.status + ').');
      return;
    }
    const blob = await r.blob();
    const cd = r.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="?([^"]+)"?/);
    const name = m ? m[1] : 'document';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  } catch {
    alert('Cannot reach the server to download the document.');
  }
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDoc(); });

/* ═══════════════════════════════════════════════════════════════════ */
function logout() {
  closeDoc();
  Object.assign(S, { user: null, role: null, token: null, isPublic: false, sessionId: null, view: 'home', messages: [], history: [], busy: false });
  renderLanding();
}

/* ═══════════════════════════════════════════════════════════════════ GLOBAL EXPORTS
   Inline HTML handlers (onclick="openDoc(...)", onsubmit="doLogin(...)", …) resolve
   their function names against `window`. Top-level declarations in a classic script
   normally land on `window` automatically, but we bind them explicitly so the handlers
   keep working regardless of caching, future bundling, or module wrapping. Every
   function referenced by an inline handler MUST appear here. */
Object.assign(window, {
  // auth / landing
  openLogin, closeLogin, enterGuest, fill, doLogin, logout, setApiUrl,
  // navigation
  go, newChat, openConversation, deleteConversation,
  // chat
  sendMsg, quick,
  // admin
  uploadFiles,
  // citation document viewer
  openDoc, closeDoc, downloadDoc,
});

renderLanding();
