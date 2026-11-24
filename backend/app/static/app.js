/* ==========================================================================
   CrabBots Attendance — front-end application
   Vanilla JS, hash routing, no build step. All state lives in memory and is
   refreshed from the FastAPI backend.
   ========================================================================== */
(() => {
  'use strict';

  /* ---------------------------------------------------------------- utils */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const esc = (value) =>
    String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

  const pct = (value) => `${Math.round((Number(value) || 0) * 100)}%`;
  const num = (value) => Number(value || 0).toLocaleString();

  const timeOf = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };
  const dateOf = (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' });
  };
  const dateTimeOf = (iso) => (iso ? `${dateOf(iso)} · ${timeOf(iso)}` : '—');
  const timeAgo = (iso) => {
    if (!iso) return '';
    const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 10) return 'just now';
    if (seconds < 60) return `${Math.floor(seconds)}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };
  const initials = (name) =>
    String(name || '?')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join('') || '?';

  const debounce = (fn, wait = 250) => {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  };

  const ICONS = {
    dashboard: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    camera: '<path d="M15 10.5 21 7v10l-6-3.5"/><rect x="3" y="5" width="12" height="14" rx="2.5"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    userPlus: '<path d="M15 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 8.9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.14.37.4.7.74.93.3.2.66.31 1.02.31H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1Z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/>',
    trash: '<path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 8 5-5 5 5M12 3v12"/>',
    check: '<path d="m4 12 5 5L20 6"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>',
    play: '<path d="m6 4 14 8-14 8V4Z"/>',
    stop: '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
    activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    film: '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M7 3v18M17 3v18M2 8h5M2 16h5M17 8h5M17 16h5"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
    scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/>',
    chevronLeft: '<path d="m15 18-6-6 6-6"/>',
    chevronRight: '<path d="m9 18 6-6-6-6"/>',
    arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    sparkles: '<path d="m12 3 1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3Z"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z"/>',
  };

  const icon = (name, cls = '') =>
    `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;

  /* ------------------------------------------------------------------ api */
  class ApiError extends Error {
    constructor(message, status, payload) {
      super(message);
      this.status = status;
      this.payload = payload || {};
      this.code = payload?.error;
    }
  }

  async function api(path, options = {}) {
    const opts = { ...options, headers: { ...(options.headers || {}) } };
    if (opts.body !== undefined && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    const response = await fetch(path, opts);
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    if (!response.ok) {
      const message = data?.detail || data?.message || `Request failed (${response.status})`;
      throw new ApiError(typeof message === 'string' ? message : JSON.stringify(message), response.status, data);
    }
    return data;
  }

  const apiUpload = (path, formData, method = 'POST') => api(path, { method, body: formData });

  /* ---------------------------------------------------------------- state */
  const state = {
    health: null,
    dashboard: null,
    settings: null,
    activeSession: null,
    sessions: [],
    members: [],
    attendance: { total: 0, items: [] },
    filters: { q: '', session_id: '', date: '', offset: 0, limit: 50 },
    add: { file: null, scanFiles: [], cameraStream: null, analysis: null, busy: false, forceDup: false, forceName: false, name: '', consent: false, notes: '', done: null, error: null },
  };

  const live = {
    running: false,
    starting: false,
    stream: null,
    ws: null,
    timer: null,
    inFlight: false,
    pendingSince: 0,
    detections: [],
    activity: [],
    frameTimes: [],
    latency: 0,
    fps: 0,
    lastError: '',
    sentImage: { w: 0, h: 0 },
    sessionId: null,
    targetFps: 8,
    overlayBoxes: new Map(),
    seenAttendanceMembers: new Set(),
  };

  /* --------------------------------------------------------------- toasts */
  function toast(message, type = 'info', ttl = 4200) {
    const root = $('#toast-root');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `${icon(type === 'success' ? 'check' : type === 'error' ? 'alert' : 'info')}<div>${esc(message)}</div>`;
    root.appendChild(el);
    const remove = () => {
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 200);
    };
    el.addEventListener('click', remove);
    setTimeout(remove, ttl);
  }

  /* ---------------------------------------------------------------- modal */
  let modalCleanup = null;
  function openModal({ title, subtitle = '', body = '', actions = [], wide = false }) {
    closeModal();
    const root = $('#modal-root');
    root.innerHTML = `
      <div class="modal-backdrop" data-modal-backdrop>
        <div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}" style="${wide ? 'width:min(760px,100%)' : ''}">
          <div class="modal-head">
            <div style="flex:1">
              <h2>${esc(title)}</h2>
              ${subtitle ? `<p>${esc(subtitle)}</p>` : ''}
            </div>
            <button class="btn btn-subtle btn-icon" data-modal-close aria-label="Close">${icon('x')}</button>
          </div>
          <div class="modal-body">${body}</div>
          <div class="modal-foot">
            ${actions
              .map(
                (action, index) =>
                  `<button class="btn ${action.class || 'btn-ghost'}" data-modal-action="${index}">${esc(action.label)}</button>`,
              )
              .join('')}
          </div>
        </div>
      </div>`;
    const backdrop = $('[data-modal-backdrop]', root);
    const close = () => closeModal();
    backdrop.addEventListener('mousedown', (event) => {
      if (event.target === backdrop) close();
    });
    $$('[data-modal-close]', root).forEach((btn) => btn.addEventListener('click', close));
    actions.forEach((action, index) => {
      const btn = $(`[data-modal-action="${index}"]`, root);
      if (btn) {
        btn.addEventListener('click', async () => {
          if (action.onClick) {
            const result = action.onClick(close);
            if (result && typeof result.then === 'function') {
              btn.disabled = true;
              try {
                await result;
              } finally {
                btn.disabled = false;
              }
            }
          } else {
            close();
          }
        });
      }
    });
    const onKey = (event) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    modalCleanup = () => document.removeEventListener('keydown', onKey);
    setTimeout(() => {
      const focusTarget = $('.modal-body input, .modal-body select, .modal-foot .btn', root);
      if (focusTarget) focusTarget.focus();
    }, 30);
    return { close, root };
  }

  function closeModal() {
    const root = $('#modal-root');
    if (root) root.innerHTML = '';
    if (modalCleanup) {
      modalCleanup();
      modalCleanup = null;
    }
  }

  function confirmDialog({ title, message, confirmLabel = 'Confirm', danger = false }) {
    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        resolve(value);
      };
      openModal({
        title,
        body: `<p style="font-size:13.5px;color:var(--ink-soft)">${esc(message)}</p>`,
        actions: [
          { label: 'Cancel', class: 'btn-ghost', onClick: (close) => { finish(false); close(); } },
          {
            label: confirmLabel,
            class: danger ? 'btn-danger' : 'btn-primary',
            onClick: (close) => { finish(true); close(); },
          },
        ],
      });
    });
  }

  /* ---------------------------------------------------------------- shell */
  const ROUTES = [
    { id: 'dashboard', label: 'Dashboard', icon: 'dashboard', title: 'Dashboard', subtitle: 'Today at a glance' },
    { id: 'live', label: 'Live recognition', icon: 'camera', title: 'Live recognition', subtitle: 'Real-time identification and attendance' },
    { id: 'members', label: 'Members', icon: 'users', title: 'Members', subtitle: 'Registered CrabBots roster' },
    { id: 'add', label: 'Enroll member', icon: 'userPlus', title: 'Enroll member', subtitle: 'Enroll from a photo or webcam scan' },
    { id: 'attendance', label: 'Attendance', icon: 'clock', title: 'Attendance', subtitle: 'History, corrections and export' },
    { id: 'settings', label: 'Settings', icon: 'settings', title: 'Settings', subtitle: 'Recognition, tracking and privacy' },
  ];

  function renderNav() {
    const nav = $('#nav');
    nav.innerHTML = ROUTES.map(
      (route) => `
      <a class="nav-link" href="#/${route.id}" data-route="${route.id}" title="${esc(route.label)}">
        ${icon(route.icon)}<span class="nav-label">${esc(route.label)}</span>
      </a>`,
    ).join('');
  }

  function currentRoute() {
    const raw = (location.hash || '#/dashboard').replace(/^#\/?/, '');
    const page = raw.split('?')[0].split('/')[0];
    return ROUTES.find((route) => route.id === page) || ROUTES[0];
  }

  async function route() {
    const page = currentRoute();
    if (live.running && page.id !== 'live') stopLive({ silent: true });
    if (page.id !== 'add') stopEnrolCamera();
    $$('.nav-link').forEach((link) => link.classList.toggle('active', link.dataset.route === page.id));
    $('#page-title').textContent = page.title;
    $('#page-subtitle').textContent = page.subtitle;
    const view = $('#view');
    view.innerHTML = loadingBlock();
    try {
      const renderers = {
        dashboard: renderDashboard,
        live: renderLive,
        members: renderMembers,
        add: renderAddMember,
        attendance: renderAttendance,
        settings: renderSettings,
      };
      await renderers[page.id]();
    } catch (error) {
      console.error(error);
      view.innerHTML = errorBlock(error);
    }
  }

  const loadingBlock = () => `
    <div class="stack">
      <div class="skeleton" style="height:96px"></div>
      <div class="skeleton" style="height:320px"></div>
    </div>`;

  const errorBlock = (error) => `
    <div class="card card-pad">
      <div class="notice bad">${icon('alert')}<div><strong>Something went wrong.</strong><br>${esc(error.message || error)}</div></div>
      <button class="btn btn-ghost mt-16" data-action="reload">${icon('refresh')} Try again</button>
    </div>`;

  function noticeBlock(kind, title, message) {
    return `<div class="notice ${kind}">${icon(kind === 'bad' || kind === 'warn' ? 'alert' : kind === 'ok' ? 'check' : 'info')}<div>${title ? `<strong>${esc(title)}</strong><br>` : ''}${message}</div></div>`;
  }

  function modelsBanner() {
    if (!state.health || state.health.models?.models_present) return '';
    return noticeBlock(
      'warn',
      'Face models are not installed',
      'Run <span class="mono">python scripts/download_models.py</span> in the project folder, then restart the server. Recognition and enrolment are unavailable until then.',
    );
  }

  function healthPill() {
    const pill = $('#health-pill');
    if (!state.health) {
      pill.className = 'health-pill';
      $('.health-label', pill).textContent = 'Connecting…';
      return;
    }
    const modelsOk = state.health.models?.models_present;
    const dbOk = state.health.database?.ok;
    pill.className = `health-pill ${dbOk && modelsOk ? 'ok' : dbOk ? 'warn' : 'bad'}`;
    $('.health-label', pill).textContent = dbOk && modelsOk ? 'System ready' : dbOk ? 'Models missing' : 'Database error';
  }

  async function refreshHealth() {
    try {
      state.health = await api('/api/health');
    } catch {
      state.health = null;
    }
    healthPill();
    if (state.health) $('#version').textContent = `v${state.health.version}`;
  }

  async function refreshSession() {
    try {
      const data = await api('/api/sessions/active');
      state.activeSession = data.session || null;
    } catch {
      state.activeSession = null;
    }
    const chip = $('#session-chip');
    const text = $('#session-text');
    if (state.activeSession) {
      text.textContent = state.activeSession.name;
      chip.querySelector('.pulse-dot').classList.add('live');
      chip.title = `Active session: ${state.activeSession.name}`;
    } else {
      text.textContent = 'No active session';
      chip.querySelector('.pulse-dot').classList.remove('live');
      chip.title = 'No active session — one is created automatically when attendance is recorded';
    }
    return state.activeSession;
  }

  function bindShell() {
    $('#session-chip').addEventListener('click', openSessionsModal);
    $('#btn-session-manage').addEventListener('click', openSessionsModal);
    document.addEventListener('click', handleGlobalClick);
    // CSP blocks inline handlers, so avatar image failures are handled here.
    document.addEventListener(
      'error',
      (event) => {
        const img = event.target;
        if (img instanceof HTMLImageElement && img.closest('.avatar')) {
          const holder = img.parentElement;
          holder.textContent = holder.dataset.initials || '?';
        }
      },
      true,
    );
    window.addEventListener('resize', debounce(() => drawOverlay(live.detections), 120));
  }

  async function handleGlobalClick(event) {
    const target = event.target.closest(
      '[data-action], [data-delete-member], [data-remove-attendance], [data-page]',
    );
    if (!target) return;

    if (target.dataset.action === 'reload') return route();

    if (target.dataset.action === 'new-session') {
      target.disabled = true;
      try {
        await api('/api/sessions', { method: 'POST', body: { name: null } });
        toast('New session started', 'success');
        await refreshSession();
        if (currentRoute().id === 'dashboard') await renderDashboard();
        if (currentRoute().id === 'live') renderLiveSession();
      } catch (error) {
        toast(error.message, 'error');
      } finally {
        target.disabled = false;
      }
      return;
    }

    if (target.dataset.action === 'sessions') return openSessionsModal();

    if (target.dataset.action === 'end-session') {
      const session = state.activeSession;
      if (!session) return toast('There is no active session', 'info');
      const ok = await confirmDialog({
        title: 'End this session?',
        message: `Attendance will stop for “${session.name}”. You can start another session from Sessions.`,
        confirmLabel: 'End session',
      });
      if (!ok) return;
      try {
        await api(`/api/sessions/${session.id}/end`, { method: 'POST' });
        await refreshSession();
        const toggle = $('#record-toggle');
        if (toggle) toggle.checked = false;
        renderLiveSession();
        toast('Session ended — attendance recording paused', 'info', 4000);
      } catch (error) {
        toast(error.message, 'error');
      }
      return;
    }

    if (target.dataset.deleteMember) {
      const id = target.dataset.deleteMember;
      const member = state.members.find((item) => item.id === id);
      if (!member) return;
      const ok = await confirmDialog({
        title: `Delete ${member.name}?`,
        message:
          'This removes the member, their face embeddings and their thumbnail. Attendance history is kept (the API supports purging it too). This cannot be undone.',
        confirmLabel: 'Delete member',
        danger: true,
      });
      if (!ok) return;
      try {
        await api(`/api/members/${id}`, { method: 'DELETE' });
        toast(`${member.name} deleted`, 'success');
        await Promise.all([renderMembers(), refreshHealth()]);
      } catch (error) {
        toast(error.message, 'error');
      }
      return;
    }

    if (target.dataset.removeAttendance) {
      await removeAttendance(target.dataset.removeAttendance);
      return;
    }

    if (target.dataset.page) {
      state.filters.offset = Math.max(
        0,
        state.filters.offset + Number(target.dataset.page) * state.filters.limit,
      );
      await loadAttendance();
    }
  }

  /* ------------------------------------------------------------ dashboard */
  async function renderDashboard() {
    const [dashboard] = await Promise.all([api('/api/dashboard'), refreshSession(), refreshHealth()]);
    state.dashboard = dashboard;
    const active = dashboard.active_session;
    const recent = dashboard.recent || [];
    const models = state.health?.models || {};

    $('#view').innerHTML = `
      <div class="stack">
        ${modelsBanner()}
        <div class="grid stats">
          <div class="card stat">
            <div class="stat-top"><span class="stat-label">Registered members</span><span class="stat-icon brand">${icon('users')}</span></div>
            <div class="stat-value">${num(dashboard.members)}</div>
            <div class="stat-foot">${num(dashboard.gallery_members)} in the live gallery</div>
          </div>
          <div class="card stat">
            <div class="stat-top"><span class="stat-label">Present today</span><span class="stat-icon green">${icon('check')}</span></div>
            <div class="stat-value">${num(dashboard.present_today)}</div>
            <div class="stat-foot">${num(dashboard.attendance_today)} check-ins recorded</div>
          </div>
          <div class="card stat">
            <div class="stat-top"><span class="stat-label">Unknown detections</span><span class="stat-icon amber">${icon('eye')}</span></div>
            <div class="stat-value">${num(dashboard.unknown_today)}</div>
            <div class="stat-foot">Rejected, never auto-enrolled</div>
          </div>
          <div class="card stat">
            <div class="stat-top"><span class="stat-label">In current session</span><span class="stat-icon teal">${icon('activity')}</span></div>
            <div class="stat-value">${num(dashboard.session_present)}</div>
            <div class="stat-foot">${active ? esc(active.name) : 'No active session'}</div>
          </div>
        </div>

        <div class="grid cols-main">
          <div class="card">
            <div class="card-head">
              <div><h2>Recent attendance</h2><div class="sub">Latest check-ins across all sessions</div></div>
              <a class="btn btn-ghost btn-sm" href="#/attendance">View all ${icon('arrowRight')}</a>
            </div>
            ${
              recent.length
                ? `<div class="table-wrap"><table>
                    <thead><tr><th>Member</th><th>Method</th><th>Confidence</th><th class="td-right">Time</th></tr></thead>
                    <tbody>
                      ${recent
                        .map(
                          (row) => `
                        <tr>
                          <td><div class="cell-person"><span class="avatar">${esc(initials(row.member_name))}</span><div><div style="font-weight:600">${esc(row.member_name)}</div><div class="small muted">${esc(row.session_name || 'No session')}</div></div></div></td>
                          <td><span class="badge ${row.method === 'live' ? 'info' : ''}">${esc(row.method)}</span></td>
                          <td>${confidenceCell(row.confidence)}</td>
                          <td class="td-right small muted nowrap">${esc(timeOf(row.timestamp))}</td>
                        </tr>`,
                        )
                        .join('')}
                    </tbody></table></div>`
                : emptyBlock('clock', 'No attendance yet', 'Start the live camera or analyse a photo to record the first check-in.')
            }
          </div>

          <div class="stack">
            <div class="card">
              <div class="card-head"><div><h2>Session</h2><div class="sub">${active ? 'Recording attendance' : 'Not recording'}</div></div>
                ${active ? '<span class="badge ok dot">Live</span>' : '<span class="badge">Idle</span>'}
              </div>
              <div class="card-body stack" style="gap:12px">
                ${
                  active
                    ? `<div><div style="font-weight:600;font-size:14px">${esc(active.name)}</div>
                         <div class="small muted">Started ${esc(dateTimeOf(active.started_at || active.created_at))}</div></div>
                       <div class="row"><span class="badge info">${num(dashboard.session_present)} present</span><span class="badge">${esc(active.id)}</span></div>`
                    : `<div class="small muted">No session is active. Attendance recording creates one automatically.</div>`
                }
                <div class="row">
                  <a class="btn btn-primary" href="#/live">${icon('camera')} Open live</a>
                  <button class="btn btn-ghost" data-action="new-session">${icon('plus')} New session</button>
                </div>
              </div>
            </div>

            <div class="card">
              <div class="card-head"><h2>System</h2>${models.pipeline_ready ? '<span class="badge ok dot">Ready</span>' : '<span class="badge warn dot">Warming up</span>'}</div>
              <div class="card-body stack" style="gap:10px">
                <div class="row-between small"><span class="muted">Detector</span><span class="mono">YuNet · MIT</span></div>
                <div class="row-between small"><span class="muted">Embeddings</span><span class="mono">SFace · 128-D</span></div>
                <div class="row-between small"><span class="muted">Match threshold</span><span class="mono">${(dashboard.thresholds?.recognition_threshold ?? 0).toFixed(2)}</span></div>
                <div class="row-between small"><span class="muted">Gallery embeddings</span><span class="mono">${num(state.health?.gallery?.embeddings ?? 0)}</span></div>
                <a class="btn btn-subtle btn-sm mt-16" href="#/settings">${icon('settings')} Tune settings</a>
              </div>
            </div>
          </div>
        </div>
      </div>`;

  }

  function confidenceCell(value) {
    const v = Number(value) || 0;
    const cls = v >= 0.7 ? '' : v >= 0.5 ? 'medium' : 'low';
    return `<div class="conf"><div class="conf-track"><div class="conf-fill ${cls}" style="width:${Math.max(2, v * 100)}%"></div></div><span class="conf-num">${pct(v)}</span></div>`;
  }

  function emptyBlock(iconName, title, message) {
    return `<div class="empty">${icon(iconName)}<strong>${esc(title)}</strong><p>${esc(message)}</p></div>`;
  }

  /* ----------------------------------------------------------------- live */
  async function renderLive() {
    await Promise.all([refreshSession(), refreshHealth()]);
    live.targetFps = Number(state.settings?.values?.target_fps || 8);
    const modelsMissing = state.health && !state.health.models?.models_present;

    $('#view').innerHTML = `
      <div class="stack">
        ${modelsBanner()}
        <div class="live-grid">
          <div class="stack">
            <div class="card" style="overflow:hidden">
              <div class="stage" id="stage">
                <video id="live-video" autoplay muted playsinline></video>
                <canvas id="live-overlay"></canvas>
                <div class="stage-empty" id="stage-empty">
                  ${icon('camera')}
                  <strong>Camera is off</strong>
                  <p>Start the camera to recognise people in real time. Everything is processed locally by the server; frames are never stored.</p>
                </div>
                <div class="stage-hud hidden" id="stage-hud"></div>
                <div class="stage-banner hidden" id="stage-banner"></div>
              </div>
              <div class="live-controls">
                <button class="btn btn-primary" id="btn-cam" ${modelsMissing ? 'disabled' : ''}>${icon('play')} <span>Start camera</span></button>
                <select class="input" id="camera-select" style="max-width:230px" aria-label="Camera"></select>
                <label class="toggle"><input type="checkbox" id="record-toggle" checked> Record attendance</label>
                <div class="spacer"></div>
                <button class="btn btn-ghost btn-sm" id="btn-photo" ${modelsMissing ? 'disabled' : ''}>${icon('image')} Photo</button>
                <button class="btn btn-ghost btn-sm" id="btn-video" ${modelsMissing ? 'disabled' : ''}>${icon('film')} Video</button>
                <input type="file" id="photo-input" accept="image/jpeg,image/png,image/webp" hidden />
                <input type="file" id="video-input" accept="video/mp4,video/quicktime,video/x-msvideo,video/webm" hidden />
              </div>
            </div>

            <div class="card hidden" id="media-result"></div>
          </div>

          <div class="stack">
            <div class="card">
              <div class="card-head"><h2>In frame</h2><span class="badge" id="frame-count">0 faces</span></div>
              <div class="det-list" id="det-list"></div>
            </div>
            <div class="card">
              <div class="card-head"><h2>Recent activity</h2><span class="badge" id="activity-count">0</span></div>
              <div class="activity" id="live-activity"></div>
            </div>
            <div class="card">
              <div class="card-head"><h2>Session</h2></div>
              <div class="card-body stack" style="gap:10px">
                <div id="live-session" class="small muted">Loading…</div>
                <div class="row">
                  <button class="btn btn-ghost btn-sm" data-action="sessions">${icon('clock')} Manage</button>
                  <button class="btn btn-ghost btn-sm" data-action="end-session">End session</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>`;

    renderDetections([]);
    renderLiveActivity();
    renderLiveSession();
    bindLivePage();
  }

  function bindLivePage() {
    const camBtn = $('#btn-cam');
    camBtn.addEventListener('click', () => {
      if (live.running) stopLive();
      else startLive();
    });

    $('#camera-select').addEventListener('change', async () => {
      if (!live.running) return;
      await stopLive({ silent: true, keepWs: true });
      await startLive();
    });

    $('#photo-input').addEventListener('change', async (event) => {
      const file = event.target.files?.[0];
      event.target.value = '';
      if (file) await analyzePhoto(file);
    });
    $('#video-input').addEventListener('change', async (event) => {
      const file = event.target.files?.[0];
      event.target.value = '';
      if (file) await analyzeVideo(file);
    });
    $('#btn-photo').addEventListener('click', () => $('#photo-input').click());
    $('#btn-video').addEventListener('click', () => $('#video-input').click());
  }

  function renderLiveSession() {
    const el = $('#live-session');
    if (!el) return;
    if (state.activeSession) {
      el.innerHTML = `<div style="font-weight:600;color:var(--ink)">${esc(state.activeSession.name)}</div>
        <div class="small muted">Started ${esc(dateTimeOf(state.activeSession.started_at || state.activeSession.created_at))}</div>`;
    } else {
      el.innerHTML = '<div>No active session. Attendance recording starts one automatically.</div>';
    }
  }

  async function populateCameras() {
    const select = $('#camera-select');
    if (!select || !navigator.mediaDevices?.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const cameras = devices.filter((device) => device.kind === 'videoinput');
      if (!cameras.length) {
        select.innerHTML = '<option value="">No camera found</option>';
        return;
      }
      const current = select.value;
      select.innerHTML = cameras
        .map((camera, index) => `<option value="${esc(camera.deviceId)}">${esc(camera.label || `Camera ${index + 1}`)}</option>`)
        .join('');
      if (current && cameras.some((camera) => camera.deviceId === current)) select.value = current;
    } catch {
      /* labels unavailable until permission is granted */
    }
  }

  function setStageBanner(message) {
    const banner = $('#stage-banner');
    if (!banner) return;
    if (!message) {
      banner.classList.add('hidden');
      banner.textContent = '';
    } else {
      banner.classList.remove('hidden');
      banner.textContent = message;
    }
  }

  function cameraErrorMessage(error) {
    if (!window.isSecureContext) {
      return 'Camera access needs a secure context. Open the app at http://localhost:8000 or serve it over HTTPS.';
    }
    switch (error?.name) {
      case 'NotAllowedError':
      case 'SecurityError':
        return 'Camera permission was denied. Allow camera access in the browser site settings and try again.';
      case 'NotFoundError':
      case 'OverconstrainedError':
        return 'No camera was found. Connect a camera, or use “Photo” to analyse an uploaded image instead.';
      case 'NotReadableError':
        return 'The camera is busy in another application. Close it and try again.';
      default:
        return `Could not start the camera: ${error?.message || 'unknown error'}`;
    }
  }

  async function startLive() {
    if (live.running || live.starting) return;
    live.starting = true;
    setStageBanner('');
    const button = $('#btn-cam');
    if (button) {
      button.disabled = true;
      button.innerHTML = `${icon('refresh', 'spin')} <span>Starting…</span>`;
    }
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw Object.assign(new Error('unsupported'), { name: 'NotSupportedError' });
      }
      const deviceId = $('#camera-select')?.value || undefined;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: deviceId
          ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
          : { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      live.stream = stream;
      const video = $('#live-video');
      video.srcObject = stream;
      await video.play().catch(() => {});
      $('#stage-empty')?.classList.add('hidden');
      $('#stage-hud')?.classList.remove('hidden');
      live.running = true;
      live.detections = [];
      live.frameTimes = [];
      live.lastError = '';
      await populateCameras();
      openLiveSocket();
      updateCamButton();
      startFrameLoop();
      toast('Camera started — step into frame', 'success');
    } catch (error) {
      console.error(error);
      live.running = false;
      setStageBanner(cameraErrorMessage(error));
      toast(cameraErrorMessage(error), 'error', 6500);
      updateCamButton();
    } finally {
      live.starting = false;
    }
  }

  function updateCamButton() {
    const button = $('#btn-cam');
    if (!button) return;
    button.disabled = false;
    button.className = `btn ${live.running ? 'btn-danger-ghost' : 'btn-primary'}`;
    button.innerHTML = live.running ? `${icon('stop')} <span>Stop camera</span>` : `${icon('play')} <span>Start camera</span>`;
  }

  async function stopLive({ silent = false, keepWs = false } = {}) {
    live.running = false;
    clearTimeout(live.timer);
    live.timer = null;
    live.inFlight = false;
    if (!keepWs && live.ws) {
      try {
        live.ws.close();
      } catch {
        /* noop */
      }
      live.ws = null;
    }
    if (live.stream) {
      live.stream.getTracks().forEach((track) => track.stop());
      live.stream = null;
    }
    const video = $('#live-video');
    if (video) video.srcObject = null;
    live.detections = [];
    live.overlayBoxes.clear();
    drawOverlay([]);
    $('#stage-empty')?.classList.remove('hidden');
    $('#stage-hud')?.classList.add('hidden');
    if (!keepWs) setStageBanner('');
    updateCamButton();
    const list = $('#det-list');
    if (list) renderDetections([]);
    if (!silent) toast('Camera stopped', 'info', 2200);
  }

  function openLiveSocket() {
    if (live.ws) {
      try { live.ws.close(); } catch { /* noop */ }
    }
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${proto}//${location.host}/ws/live`);
    live.ws = socket;
    socket.addEventListener('open', () => {
      live.inFlight = false;
      scheduleFrame(0);
    });
    socket.addEventListener('message', (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      handleLiveMessage(message);
    });
    socket.addEventListener('close', () => {
      if (live.running) {
        setStageBanner('Connection to the recognition server was lost. Restarting…');
        setTimeout(() => {
          if (live.running) {
            openLiveSocket();
            startFrameLoop();
          }
        }, 1500);
      }
    });
    socket.addEventListener('error', () => {
      /* close handler drives recovery */
    });
  }

  function startFrameLoop() {
    clearTimeout(live.timer);
    live.timer = setTimeout(captureFrame, 60);
  }

  const frameCanvas = document.createElement('canvas');

  function captureFrame() {
    if (!live.running) return;
    if (!live.ws || live.ws.readyState !== WebSocket.OPEN) {
      live.timer = setTimeout(captureFrame, 300);
      return;
    }
    if (live.inFlight) {
      if (performance.now() - live.pendingSince > 6000) {
        live.inFlight = false;
      } else {
        live.timer = setTimeout(captureFrame, 120);
        return;
      }
    }
    const video = $('#live-video');
    if (!video || video.readyState < 2 || !video.videoWidth) {
      live.timer = setTimeout(captureFrame, 250);
      return;
    }
    const targetWidth = Math.min(640, video.videoWidth);
    const scale = targetWidth / video.videoWidth;
    frameCanvas.width = targetWidth;
    frameCanvas.height = Math.round(video.videoHeight * scale);
    const ctx = frameCanvas.getContext('2d');
    ctx.drawImage(video, 0, 0, frameCanvas.width, frameCanvas.height);
    const image = frameCanvas.toDataURL('image/jpeg', 0.72);
    live.sentImage = { w: frameCanvas.width, h: frameCanvas.height };
    try {
      live.ws.send(
        JSON.stringify({
          type: 'frame',
          image,
          session_id: state.activeSession?.id || null,
          record: $('#record-toggle')?.checked ?? true,
          ts: Date.now(),
        }),
      );
      live.inFlight = true;
      live.pendingSince = performance.now();
      // Watchdog: if a result never arrives, unblock the loop instead of freezing.
      live.timer = setTimeout(captureFrame, 6000);
    } catch {
      live.inFlight = false;
    }
  }

  function handleLiveMessage(message) {
    if (message.type === 'ready') {
      live.sessionId = message.session_id;
      return;
    }
    if (message.type === 'error') {
      live.inFlight = false;
      setStageBanner(message.message || 'Recognition error');
      if (message.code === 'models_missing') stopLive({ silent: true });
      return;
    }
    if (message.type !== 'result') return;

    live.inFlight = false;
    const now = performance.now();
    live.latency = Math.round(now - live.pendingSince);
    live.frameTimes.push(now);
    live.frameTimes = live.frameTimes.filter((time) => now - time < 2000);
    live.fps = Math.round((live.frameTimes.length / 2) * 10) / 10;
    live.detections = message.detections || [];

    drawOverlay(live.detections);
    renderDetections(live.detections);
    updateHud(live.detections, message);
    pushLiveEvents(message);
    scheduleNextFrame();
  }

  function scheduleNextFrame() {
    clearTimeout(live.timer);
    const interval = Math.max(40, Math.round(1000 / Math.max(1, live.targetFps)));
    live.timer = setTimeout(captureFrame, interval);
  }

  function updateHud(detections, message) {
    const hud = $('#stage-hud');
    if (!hud) return;
    hud.classList.remove('hidden');
    hud.innerHTML = `
      <span class="hud-chip live">LIVE</span>
      <span class="hud-chip">${live.fps.toFixed(1)} fps</span>
      <span class="hud-chip">${live.latency} ms</span>
      <span class="hud-chip">${detections.length} face${detections.length === 1 ? '' : 's'}</span>
      ${message?.attendance_created?.length ? '<span class="hud-chip">check-in recorded</span>' : ''}`;
  }

  function colorForStatus(status) {
    if (status === 'recognized') return '#34d399';
    if (status === 'unknown') return '#f87171';
    return '#fbbf24';
  }

  function drawOverlay(detections) {
    const canvas = $('#live-overlay');
    const video = $('#live-video');
    if (!canvas || !video) return;
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!width || !height) return;
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    // Detection boxes are returned in the dimensions of the resized frame
    // sent to the backend (currently up to 640px wide), not the camera's
    // original video dimensions. Use those exact dimensions to align boxes.
    const sourceW = live.sentImage.w || video.videoWidth;
    const sourceH = live.sentImage.h || video.videoHeight;
    if (!sourceW || !sourceH) return;
    const scale = Math.min(width / sourceW, height / sourceH);
    const offsetX = (width - sourceW * scale) / 2;
    const offsetY = (height - sourceH * scale) / 2;

    // Only draw enrolled members; unknown and pending detections are hidden.
    const visibleDetections = detections.filter((det) => det.status === 'recognized');
    const activeTrackIds = new Set();
    visibleDetections.forEach((det) => {
      const [rawX, rawY, rawW, rawH] = det.bbox;
      const trackKey = String(det.track_id ?? [rawX, rawY].join(':'));
      activeTrackIds.add(trackKey);
      const previous = live.overlayBoxes.get(trackKey);
      // Smooth small frame-to-frame detector changes to prevent box/label jitter.
      const amount = previous ? 0.35 : 1;
      const box = previous
        ? {
            x: previous.x + (rawX - previous.x) * amount,
            y: previous.y + (rawY - previous.y) * amount,
            w: previous.w + (rawW - previous.w) * amount,
            h: previous.h + (rawH - previous.h) * amount,
          }
        : { x: rawX, y: rawY, w: rawW, h: rawH };
      live.overlayBoxes.set(trackKey, box);
      const rx = offsetX + box.x * scale;
      const ry = offsetY + box.y * scale;
      const rw = box.w * scale;
      const rh = box.h * scale;
      const color = colorForStatus(det.status);

      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(2, Math.round(scale * 3));
      ctx.shadowColor = 'rgba(0,0,0,0.35)';
      ctx.shadowBlur = 6;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(rx, ry, rw, rh, 10);
      else ctx.rect(rx, ry, rw, rh);
      ctx.stroke();
      ctx.restore();

      let label;
      if (det.status === 'recognized') label = `${det.name || 'Member'} · ${pct(det.confidence)}`;
      else if (det.status === 'unknown') label = 'Unknown person';
      else label = 'Identifying…';

      ctx.font = '600 13px Inter, system-ui, sans-serif';
      const textWidth = ctx.measureText(label).width;
      const chipW = textWidth + 16;
      const chipH = 24;
      const chipX = Math.max(2, Math.min(rx, width - chipW - 2));
      const chipY = Math.max(2, ry - chipH - 6);
      ctx.fillStyle = color;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(chipX, chipY, chipW, chipH, 6);
      else ctx.rect(chipX, chipY, chipW, chipH);
      ctx.fill();
      ctx.fillStyle = '#0b1220';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, chipX + 8, chipY + chipH / 2 + 1);

      if (det.track_id) {
        ctx.font = '500 10px "Cascadia Code", monospace';
        ctx.fillStyle = 'rgba(255,255,255,0.85)';
        ctx.fillText(`#${det.track_id}`, rx + 4, ry + rh + 12);
      }
    });
    for (const trackKey of live.overlayBoxes.keys()) {
      if (!activeTrackIds.has(trackKey)) live.overlayBoxes.delete(trackKey);
    }
  }

  function renderDetections(detections) {
    const list = $('#det-list');
    const count = $('#frame-count');
    if (!list) return;
    // One row per enrolled member; hide unknown and pending faces.
    const uniqueMembers = new Map();
    detections.filter((det) => det.status === 'recognized').forEach((det) => {
      const key = String(det.member_id || det.name || det.track_id);
      const current = uniqueMembers.get(key);
      if (!current || (det.confidence || 0) > (current.confidence || 0)) uniqueMembers.set(key, det);
    });
    const visible = [...uniqueMembers.values()];
    if (count) count.textContent = `${visible.length} known`;
    if (!visible.length) {
      list.innerHTML = emptyBlock('scan', 'No faces in view', live.running ? 'Look towards the camera to be recognised.' : 'Start the camera to begin.');
      return;
    }
    const sorted = visible.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    list.innerHTML = sorted
      .map((det) => {
        const label = det.name || 'Member';
        const conf = Number(det.confidence) || 0;
        const confClass = conf >= 0.7 ? '' : conf >= 0.5 ? 'medium' : 'low';
        return `<div class="det-item">
          <div class="det-avatar recognized">${esc(initials(det.name))}</div>
          <div class="det-main">
            <div class="det-name">${esc(label)} ${det.attendance_recorded ? '<span class="badge ok" style="font-size:10px;padding:0 6px">recorded</span>' : ''}</div>
            <div class="det-meta">Track <span class="track-chip">#${esc(det.track_id)}</span> · ${esc(det.hits)} frames · ${esc(det.evidence)} votes</div>
            <div class="det-bar">${confidenceCell(conf)}</div>
          </div>
        </div>`;
      })
      .join('');
  }

  function pushLiveEvents(message) {
    const events = [];
    (message.attendance_created || []).forEach((record) => {
      // Keep only one activity entry per known member during this live run.
      const memberKey = String(record.member_id || record.member_name || '').trim().toLowerCase();
      if (!memberKey || live.seenAttendanceMembers.has(memberKey)) return;
      live.seenAttendanceMembers.add(memberKey);
      events.push({
        kind: 'attendance', name: record.member_name, confidence: record.confidence,
        ts: record.timestamp, id: record.id, member_id: record.member_id,
      });
      toast(`${record.member_name} checked in`, 'success', 3200);
      refreshSession();
    });
    // Unknown detections are deliberately omitted from Recent activity.
    if (!events.length) return;
    live.activity = [...events, ...live.activity].slice(0, 12);
    renderLiveActivity();
  }

  function renderLiveActivity() {
    const root = $('#live-activity');
    const count = $('#activity-count');
    if (!root) return;
    if (count) count.textContent = String(live.activity.length);
    if (!live.activity.length) {
      root.innerHTML = emptyBlock('activity', 'No known visitors yet', 'Recognized members appear here once when they check in.');
      return;
    }
    root.innerHTML = live.activity
      .map(
        (item) => `<div class="activity-item">
          <span class="activity-dot ${item.kind === 'unknown' ? 'unknown' : ''}"></span>
          <div><div style="font-weight:600">${esc(item.name)}</div>
          <div class="small muted">${item.kind === 'unknown' ? 'Rejected · no identity assigned' : `Checked in · ${pct(item.confidence)}`}</div></div>
          <span class="activity-time">${esc(timeAgo(item.ts))}</span>
        </div>`,
      )
      .join('');
  }

  /* ------------------------------------------------------- media analysis */
  async function analyzePhoto(file) {
    const panel = $('#media-result');
    if (!panel) return;
    panel.classList.remove('hidden');
    panel.innerHTML = `<div class="card-body row"><span class="btn-icon spin">${icon('refresh')}</span><div><strong>Analysing photo…</strong><div class="small muted">${esc(file.name)}</div></div></div>`;
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('record', $('#record-toggle')?.checked ? 'true' : 'false');
      if (state.activeSession) form.append('session_id', state.activeSession.id);
      const result = await apiUpload('/api/recognize/photo', form);
      const detections = result.detections || [];
      panel.innerHTML = `
        <div class="card-head"><div><h2>Photo analysis</h2><div class="sub">${esc(file.name)} · ${result.faces} face${result.faces === 1 ? '' : 's'} · ${result.latency_ms} ms</div></div>
          <span class="badge ${detections.some((d) => d.status === 'recognized') ? 'ok' : 'warn'}">${detections.some((d) => d.status === 'recognized') ? 'Match found' : 'No match'}</span>
        </div>
        <div class="card-body">
          <div class="preview-wrap"><img src="${result.annotated_image}" alt="Annotated photo analysis" /></div>
          <div class="stack mt-16" style="gap:8px">
            ${detections
              .map(
                (det) => `<div class="row-between" style="padding:10px 12px;border:1px solid var(--line);border-radius:10px">
                  <div class="cell-person">
                    <span class="avatar ${det.status === 'recognized' ? '' : ''}">${det.status === 'recognized' ? esc(initials(det.name)) : '?'}</span>
                    <div><div style="font-weight:600">${det.status === 'recognized' ? esc(det.name) : 'Unknown person'}</div>
                    <div class="small muted">${esc(det.match_reason)} · ${esc(det.attendance?.reason || 'not recorded')}</div></div>
                  </div>
                  ${confidenceCell(det.confidence)}
                </div>`,
              )
              .join('')}
          </div>
        </div>`;
      if (result.attendance_created?.length) {
        toast(`${result.attendance_created[0].member_name} checked in`, 'success');
        await refreshSession();
      }
    } catch (error) {
      panel.innerHTML = `<div class="card-body">${noticeBlock('bad', 'Could not analyse this photo', esc(error.message))}</div>`;
    }
  }

  async function analyzeVideo(file) {
    const panel = $('#media-result');
    if (!panel) return;
    panel.classList.remove('hidden');
    panel.innerHTML = `<div class="card-body row"><span class="btn-icon spin">${icon('refresh')}</span><div><strong>Processing video…</strong><div class="small muted">${esc(file.name)} — sampled frames are tracked and voted on. This can take a few seconds.</div></div></div>`;
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('record', $('#record-toggle')?.checked ? 'true' : 'false');
      if (state.activeSession) form.append('session_id', state.activeSession.id);
      const result = await apiUpload('/api/recognize/video', form);
      panel.innerHTML = `
        <div class="card-head"><div><h2>Video analysis</h2><div class="sub">${result.frames_processed} frames sampled · ${result.video_duration_seconds}s video · ${result.avg_latency_ms} ms/frame</div></div>
          <span class="badge ${result.recognized.length ? 'ok' : 'warn'}">${result.recognized.length} recognised</span>
        </div>
        <div class="card-body stack">
          <div class="grid cols-3">
            <div class="stat" style="padding:14px"><span class="stat-label">Recognised people</span><div class="stat-value" style="font-size:22px">${result.recognized.length}</div></div>
            <div class="stat" style="padding:14px"><span class="stat-label">Check-ins created</span><div class="stat-value" style="font-size:22px">${result.attendance_created.length}</div></div>
            <div class="stat" style="padding:14px"><span class="stat-label">Unknown tracks</span><div class="stat-value" style="font-size:22px">${result.unknown_tracks}</div></div>
          </div>
          ${
            result.recognized.length
              ? `<div class="stack" style="gap:8px">${result.recognized
                  .map(
                    (person) => `<div class="row-between" style="padding:10px 12px;border:1px solid var(--line);border-radius:10px">
                      <div class="cell-person"><span class="avatar">${esc(initials(person.name))}</span><div><div style="font-weight:600">${esc(person.name)}</div><div class="small muted">Track #${esc(person.track_id)}</div></div></div>
                      ${confidenceCell(person.confidence)}
                    </div>`,
                  )
                  .join('')}</div>`
              : noticeBlock('warn', 'No confident identification', 'Tracks were seen but none accumulated enough consistent evidence. Try a clearer or slower clip.')
          }
          ${
            result.annotated_frames?.length
              ? `<div><div class="section-title" style="margin-bottom:8px">Annotated samples</div>
                 <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
                   ${result.annotated_frames.map((src) => `<img src="${src}" alt="Annotated video frame" style="border-radius:8px;width:100%" />`).join('')}
                 </div></div>`
              : ''
          }
        </div>`;
      if (result.attendance_created?.length) {
        toast(`${result.attendance_created.length} check-in(s) recorded`, 'success');
        await refreshSession();
      }
    } catch (error) {
      panel.innerHTML = `<div class="card-body">${noticeBlock('bad', 'Could not process this video', esc(error.message))}</div>`;
    }
  }

  /* -------------------------------------------------------------- members */
  async function renderMembers() {
    const data = await api('/api/members');
    state.members = data.items || [];
    const search = state.memberQuery || '';
    $('#view').innerHTML = `
      <div class="stack">
        <div class="card">
          <div class="card-head">
            <div><h2>Members</h2><div class="sub">${data.total} registered · embeddings stay on this machine</div></div>
            <div class="row">
              <div style="position:relative">
                ${icon('search', '')}
                <input class="input" id="member-search" placeholder="Search members…" value="${esc(search)}" style="padding-left:34px;min-width:220px" />
              </div>
              <a class="btn btn-primary" href="#/add">${icon('plus')} Enrol member</a>
            </div>
          </div>
          <div class="card-body" id="member-grid-wrap">${memberGrid(state.members, search)}</div>
        </div>
      </div>`;

    // Position the search icon inside the input.
    const searchWrap = $('#member-search')?.parentElement;
    if (searchWrap) {
      const svg = searchWrap.querySelector('svg');
      if (svg) Object.assign(svg.style, { position: 'absolute', left: '11px', top: '50%', transform: 'translateY(-50%)', width: '15px', height: '15px', color: '#98a2b3', pointerEvents: 'none' });
    }

    const onSearch = debounce((value) => {
      state.memberQuery = value;
      const filtered = state.members.filter((m) => m.name.toLowerCase().includes(value.toLowerCase()));
      $('#member-grid-wrap').innerHTML = memberGrid(filtered, value);
    }, 160);
    $('#member-search')?.addEventListener('input', (event) => onSearch(event.target.value));
  }

  function memberGrid(members, query) {
    if (!members.length) {
      return emptyBlock('users', query ? 'No matching members' : 'No members yet', query ? 'Try a different search.' : 'Enroll the first CrabBots member from a clear photograph.');
    }
    return `<div class="member-grid">${members
      .map(
        (member) => `<div class="card member-card">
          <div class="member-top">
            <span class="avatar lg" data-initials="${esc(initials(member.name))}">${member.has_thumbnail ? `<img src="/api/members/${esc(member.id)}/thumbnail" alt="" loading="lazy" />` : esc(initials(member.name))}</span>
            <div style="min-width:0">
              <div class="member-name">${esc(member.name)}</div>
              <div class="member-meta">Enrolled ${esc(dateOf(member.created_at))}</div>
              <div class="row" style="gap:5px;margin-top:5px">
                <span class="badge">${member.embedding_count} embedding${member.embedding_count === 1 ? '' : 's'}</span>
                ${member.is_demo ? '<span class="badge warn">demo</span>' : ''}
                ${member.consent ? '<span class="badge ok">consented</span>' : '<span class="badge bad">no consent</span>'}
              </div>
            </div>
          </div>
          <div class="member-actions">
            <a class="btn btn-subtle btn-sm" href="#/live">${icon('camera')} Recognise</a>
            <button class="btn btn-danger-ghost btn-sm" data-delete-member="${esc(member.id)}">${icon('trash')} Delete</button>
          </div>
        </div>`,
      )
      .join('')}</div>`;
  }

  /* ----------------------------------------------------------- add member */
  function renderAddMember() {
    const add = state.add;
    $('#view').innerHTML = `
      <div class="grid cols-main">
        <div class="stack">
          <div class="card">
            <div class="card-head"><div><h2>1 · Photograph</h2><div class="sub">Upload one photo or capture several face angles</div></div>
              ${add.analysis ? '<span class="badge ok dot">Analysed</span>' : ''}
            </div>
            <div class="card-body">
              <div class="dropzone" id="dropzone" tabindex="0" role="button">
                ${icon('upload')}
                <strong>Drop a photo here, or click to browse</strong>
                <span>JPG, PNG or WebP · max ${state.settings?.values?.max_upload_mb || 12} MB · exactly one person</span>
              </div>
              <input type="file" id="enrol-file" accept="image/jpeg,image/png,image/webp" hidden />
              <div id="enrol-preview" class="mt-16">${add.analysis?.preview_image || add.errorImage ? `<div class="preview-wrap"><img src="${add.analysis?.preview_image || add.errorImage}" alt="Enrolment preview" /></div>` : ''}</div>
              <div class="divider" style="margin:18px 0"></div>
              <div class="row-between">
                <div><strong>Or scan with webcam</strong><div class="small muted">Capture several angles to improve recognition.</div></div>
                <button class="btn btn-ghost btn-sm" id="btn-camera-start">${icon('camera')} Start camera</button>
              </div>
              <div id="enrol-camera-wrap" class="enrol-camera-wrap hidden">
                <video id="enrol-camera" autoplay muted playsinline></video>
                <div class="small muted">Follow each prompt and keep your face well lit and inside the frame.</div>
                <div class="row">
                  <button class="btn btn-subtle btn-sm" data-scan-angle="front" disabled>1 · Look straight</button>
                  <button class="btn btn-subtle btn-sm" data-scan-angle="left" disabled>2 · Turn left</button>
                  <button class="btn btn-subtle btn-sm" data-scan-angle="right" disabled>3 · Turn right</button>
                  <button class="btn btn-subtle btn-sm" data-scan-angle="tilt" disabled>4 · Tilt head</button>
                </div>
                <div class="row-between">
                  <span class="small muted" id="scan-count">${add.scanFiles.length} of 4 angles captured</span>
                  <button class="btn btn-ghost btn-sm" id="btn-camera-stop">Stop camera</button>
                </div>
              </div>
              <div id="scan-thumbnails" class="scan-thumbnails">${add.scanFiles.map((file) => `<span class="badge ok">${esc(file.name.replace('camera-', '').replace('.jpg', ''))} captured</span>`).join('')}</div>
              <div id="enrol-error" class="mt-16">${add.error ? noticeBlock('bad', 'Cannot use this photo', esc(add.error)) : ''}</div>
            </div>
          </div>

          <div class="card" id="quality-card">
            <div class="card-head"><h2>2 · Quality checks</h2>${add.analysis?.quality?.passed ? '<span class="badge ok dot">Passed</span>' : ''}</div>
            <div class="card-body" id="quality-body">${qualityBlock(add.analysis)}</div>
          </div>
        </div>

        <div class="stack">
          <div class="card">
            <div class="card-head"><div><h2>3 · Member details</h2><div class="sub">Saved to the local roster</div></div></div>
            <div class="card-body stack">
              ${add.done ? successBlock(add.done) : `
              <div class="field">
                <label for="enrol-name">Full name</label>
                <input class="input" id="enrol-name" placeholder="e.g. Alex Rivera" maxlength="80" value="${esc(add.name)}" />
              </div>
              <div class="field">
                <label for="enrol-notes">Notes <span class="muted">(optional)</span></label>
                <input class="input" id="enrol-notes" placeholder="Team, role…" maxlength="200" value="${esc(add.notes)}" />
              </div>
              <label class="check"><input type="checkbox" id="enrol-consent" ${add.consent ? 'checked' : ''} />
                <span>I confirm this person consents to their face embedding being stored for CrabBots attendance. Face embeddings from the photo and camera angles, plus an optional thumbnail, are kept.</span>
              </label>
              ${add.analysis?.duplicate ? noticeBlock('warn', 'Possible existing member', `This face is ${pct(add.analysis.duplicate.similarity)} similar to <strong>${esc(add.analysis.duplicate.name)}</strong>. ${add.forceDup ? 'Duplicate override enabled — enrollment will proceed.' : 'Confirm below if it is a different person.'}`) : ''}
              ${add.forceDup ? '<span class="badge warn">Duplicate override enabled</span>' : ''}
              <div class="row">
                <button class="btn btn-primary" id="btn-enrol" ${add.analysis?.ok && add.name.trim().length >= 2 && add.consent ? '' : 'disabled'}>
                  ${icon('userPlus')} Enrol member
                </button>
                ${add.analysis?.duplicate && !add.forceDup ? '<button class="btn btn-ghost" id="btn-force-dup">It\'s a different person</button>' : ''}
              </div>
              <div class="small muted">Recognition becomes active immediately — no restart required.</div>
              `}
            </div>
          </div>

          <div class="card">
            <div class="card-head"><h2>How enrolment works</h2></div>
            <div class="card-body stack" style="gap:10px">
              ${stepRow('scan', 'Detect', 'YuNet finds the face and five landmarks.')}
              ${stepRow('shield', 'Validate', 'Sharpness, lighting, size and pose are checked.')}
              ${stepRow('activity', 'Embed', 'SFace creates a 128-D reference for each captured angle; all are stored locally.')}
              ${stepRow('sparkles', 'Recognise', 'The gallery updates instantly for live matching.')}
            </div>
          </div>
        </div>
      </div>`;

    bindAddMember();
  }

  function stepRow(iconName, title, text) {
    return `<div class="row" style="align-items:flex-start;gap:10px"><span class="stat-icon" style="width:28px;height:28px;border-radius:8px;background:var(--surface-2);color:var(--muted)">${icon(iconName)}</span><div><div style="font-weight:600;font-size:12.5px">${esc(title)}</div><div class="small muted">${esc(text)}</div></div></div>`;
  }

  function qualityBlock(analysis) {
    if (!analysis) {
      return `<div class="empty" style="padding:22px">${icon('shield')}<strong>No photo analysed</strong><p>Upload a photo or capture a webcam angle to see sharpness, lighting, face size and pose checks.</p></div>`;
    }
    const quality = analysis.quality;
    if (!quality) {
      return `<div class="small muted">Quality information is unavailable for this photo.</div>`;
    }
    return `
      <div class="quality-list">
        ${quality.checks
          .map((check) => {
            const cls = check.passed ? 'pass' : check.severity === 'warn' ? 'warn' : 'fail';
            return `<div class="quality-item ${cls}">
              <span class="quality-icon">${icon(check.passed ? 'check' : check.severity === 'warn' ? 'alert' : 'x')}</span>
              <div><span class="q-label">${esc(check.label)}</span> <span class="q-value">${esc(check.value)}</span>
              ${check.passed ? '' : `<div class="q-hint">${esc(check.hint)}</div>`}</div>
            </div>`;
          })
          .join('')}
      </div>
      <div class="divider" style="margin:14px 0"></div>
      <div class="small ${quality.passed ? 'muted' : ''}" style="color:${quality.passed ? 'var(--green)' : 'var(--red)'}">${esc(quality.summary)}</div>`;
  }

  function successBlock(member) {
    return `<div class="stack" style="align-items:center;text-align:center;gap:12px;padding:10px 0">
      <span class="avatar lg" style="width:72px;height:72px;flex-basis:72px;border-radius:18px">${member.preview_image ? `<img src="${member.preview_image}" alt="" />` : esc(initials(member.name))}</span>
      <div><div style="font-weight:650;font-size:16px">${esc(member.name)} is enrolled</div>
      <div class="small muted">Recognisable by the live camera right now.</div></div>
      <div class="row" style="justify-content:center">
        <a class="btn btn-primary" href="#/live">${icon('camera')} Recognise now</a>
        <button class="btn btn-ghost" id="btn-enrol-another">Enrol another</button>
      </div>
    </div>`;
  }

  function bindAddMember() {
    const dropzone = $('#dropzone');
    const input = $('#enrol-file');
    const cameraVideo = $('#enrol-camera');
    if (state.add.cameraStream && cameraVideo) {
      cameraVideo.srcObject = state.add.cameraStream;
      $('#enrol-camera-wrap')?.classList.remove('hidden');
      cameraVideo.play().catch(() => {});
    }
    $$('[data-scan-angle]').forEach((button) => {
      const captured = state.add.scanFiles.some((file) => file.name === `camera-${button.dataset.scanAngle}.jpg`);
      button.disabled = !state.add.cameraStream || captured;
      if (captured) button.classList.add('btn-primary');
    });
    if (dropzone && input) {
      dropzone.addEventListener('click', () => input.click());
      dropzone.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          input.click();
        }
      });
      ['dragenter', 'dragover'].forEach((type) =>
        dropzone.addEventListener(type, (event) => {
          event.preventDefault();
          dropzone.classList.add('dragover');
        }),
      );
      ['dragleave', 'drop'].forEach((type) =>
        dropzone.addEventListener(type, (event) => {
          event.preventDefault();
          dropzone.classList.remove('dragover');
        }),
      );
      dropzone.addEventListener('drop', (event) => {
        const file = event.dataTransfer?.files?.[0];
        if (file) selectEnrolFile(file);
      });
      input.addEventListener('change', (event) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (file) selectEnrolFile(file);
      });
    }

    $('#enrol-name')?.addEventListener('input', (event) => {
      state.add.name = event.target.value;
      const button = $('#btn-enrol');
      if (button) button.disabled = !(state.add.analysis?.ok && (state.add.file || state.add.scanFiles.length) && state.add.name.trim().length >= 2 && state.add.consent);
    });
    $('#enrol-notes')?.addEventListener('input', (event) => {
      state.add.notes = event.target.value;
    });
    $('#enrol-consent')?.addEventListener('change', (event) => {
      state.add.consent = event.target.checked;
      const button = $('#btn-enrol');
      if (button) button.disabled = !(state.add.analysis?.ok && (state.add.file || state.add.scanFiles.length) && state.add.name.trim().length >= 2 && state.add.consent);
    });
    $('#btn-enrol')?.addEventListener('click', enrollMember);
    $('#btn-force-dup')?.addEventListener('click', () => {
      state.add.forceDup = true;
      renderAddMember();
    });
    $('#btn-enrol-another')?.addEventListener('click', () => {
      stopEnrolCamera();
      state.add = { file: null, scanFiles: [], cameraStream: null, analysis: null, busy: false, forceDup: false, forceName: false, name: '', consent: false, notes: '', done: null, error: null, errorImage: null };
      renderAddMember();
    });
    $('#btn-camera-start')?.addEventListener('click', startEnrolCamera);
    $('#btn-camera-stop')?.addEventListener('click', stopEnrolCamera);
    $$('[data-scan-angle]').forEach((button) => button.addEventListener('click', () => captureEnrolAngle(button.dataset.scanAngle)));
  }

  async function startEnrolCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      toast('Camera access is unavailable. Use localhost or HTTPS and a supported browser.', 'error', 6000);
      return;
    }
    try {
      stopEnrolCamera();
      state.add.cameraStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      const video = $('#enrol-camera');
      const wrap = $('#enrol-camera-wrap');
      if (!video || !wrap) throw new Error('Camera preview is not available. Please reopen Enroll Members.');
      video.srcObject = state.add.cameraStream;
      wrap.classList.remove('hidden');
      // Wait for the browser to attach the camera stream before starting playback.
      if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
        await new Promise((resolve, reject) => {
          const onReady = () => { cleanup(); resolve(); };
          const onError = () => { cleanup(); reject(new Error('The camera preview could not be loaded.')); };
          const cleanup = () => {
            video.removeEventListener('loadedmetadata', onReady);
            video.removeEventListener('error', onError);
          };
          video.addEventListener('loadedmetadata', onReady, { once: true });
          video.addEventListener('error', onError, { once: true });
        });
      }
      await video.play();
      $$('[data-scan-angle]').forEach((button) => {
        const captured = state.add.scanFiles.some((file) => file.name === `camera-${button.dataset.scanAngle}.jpg`);
        button.disabled = captured;
      });
      const startButton = $('#btn-camera-start');
      if (startButton) startButton.disabled = true;
    } catch (error) {
      stopEnrolCamera();
      toast(`Could not start camera: ${error.message || error}`, 'error', 6000);
    }
  }

  function stopEnrolCamera() {
    if (state.add.cameraStream) {
      state.add.cameraStream.getTracks().forEach((track) => track.stop());
      state.add.cameraStream = null;
    }
    const video = $('#enrol-camera');
    if (video) {
      video.pause();
      video.srcObject = null;
    }
    $('#enrol-camera-wrap')?.classList.add('hidden');
    const startButton = $('#btn-camera-start');
    if (startButton) startButton.disabled = false;
    $$('[data-scan-angle]').forEach((button) => { button.disabled = true; });
  }

  async function captureEnrolAngle(angle) {
    const video = $('#enrol-camera');
    if (!video || !video.videoWidth || !video.videoHeight) {
      toast('Wait for the camera image to appear, then try again.', 'info');
      return;
    }
    if (state.add.scanFiles.some((file) => file.name === `camera-${angle}.jpg`)) {
      toast('That angle has already been captured.', 'info');
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92));
    if (!blob) {
      toast('Could not capture this camera frame. Please try again.', 'error');
      return;
    }
    const file = new File([blob], `camera-${angle}.jpg`, { type: 'image/jpeg' });
    file.previewUrl = URL.createObjectURL(blob);
    state.add.scanFiles.push(file);
    const count = $('#scan-count');
    if (count) count.textContent = `${state.add.scanFiles.length} of 4 angles captured`;
    const thumbs = $('#scan-thumbnails');
    if (thumbs) thumbs.innerHTML = state.add.scanFiles.map((item) =>
      `<div class="scan-thumb"><img src="${item.previewUrl}" alt="${esc(item.name)}" /><span>${esc(item.name.replace('camera-', '').replace('.jpg', ''))}</span></div>`).join('');
    const button = $('[data-scan-angle]').find((item) => item.dataset.scanAngle === angle);
    if (button) { button.disabled = true; button.classList.add('btn-primary'); }
    // Analyse the straight-on reference once. Angled captures are retained as
    // additional embeddings and should not be rejected for their intentional pose.
    if (angle === 'front' && !state.add.file && !state.add.analysis) {
      await analyzeEnrolImage(file);
    }
    const enrolButton = $('#btn-enrol');
    if (enrolButton) enrolButton.disabled = !((state.add.file || state.add.scanFiles.some((item) => item.name === 'camera-front.jpg')) && state.add.analysis?.ok && state.add.name.trim().length >= 2 && state.add.consent);
    toast(`${angle[0].toUpperCase() + angle.slice(1)} angle captured`, 'success', 1800);
  }

  async function analyzeEnrolImage(file) {
    const preview = $('#enrol-preview');
    if (preview) {
      const url = URL.createObjectURL(file);
      preview.innerHTML = `<div class="preview-wrap"><img src="${url}" alt="Selected enrollment image" /></div>`;
      $('#quality-body').innerHTML = `<div class="row"><span class="btn-icon spin">${icon('refresh')}</span><span class="small muted">Checking face, sharpness, lighting and duplicates…</span></div>`;
    }
    try {
      const form = new FormData();
      form.append('file', file);
      state.add.analysis = await apiUpload('/api/members/preview', form);
      state.add.error = null;
    } catch (error) {
      state.add.analysis = null;
      state.add.error = error.message;
      if (error.payload?.preview_image) state.add.errorImage = error.payload.preview_image;
    }
    if (state.add.cameraStream) {
      const quality = $('#quality-body');
      if (quality) quality.innerHTML = qualityBlock(state.add.analysis);
      const previewWrap = $('#enrol-preview');
      if (previewWrap) previewWrap.innerHTML = state.add.analysis?.preview_image
        ? `<div class="preview-wrap"><img src="${state.add.analysis.preview_image}" alt="Captured front-facing enrollment image" /></div>`
        : '';
      const error = $('#enrol-error');
      if (error) error.innerHTML = state.add.error ? noticeBlock('bad', 'Cannot use this photo', esc(state.add.error)) : '';
      const enrolButton = $('#btn-enrol');
      if (enrolButton) enrolButton.disabled = !(state.add.analysis?.ok && state.add.name.trim().length >= 2 && state.add.consent);
    } else {
      renderAddMember();
    }
  }

  async function selectEnrolFile(file) {
    if (!file.type.startsWith('image/')) {
      toast('Choose a JPG, PNG or WebP image', 'error');
      return;
    }
    const maxMb = Number(state.settings?.values?.max_upload_mb || 12);
    if (file.size > maxMb * 1024 * 1024) {
      toast(`Image is larger than ${maxMb} MB`, 'error');
      return;
    }
    state.add.file = file;
    state.add.analysis = null;
    state.add.done = null;
    state.add.error = null;
    state.add.errorImage = null;
    state.add.forceDup = false;
    renderAddMember();
    await analyzeEnrolImage(file);
  }

  async function enrollMember() {
    const add = state.add;
    if ((!add.file && !add.scanFiles.length) || !add.analysis?.ok) return;
    const button = $('#btn-enrol');
    if (button) {
      button.disabled = true;
      button.innerHTML = `${icon('refresh', 'spin')} Enrolling…`;
    }
    try {
      const form = new FormData();
      if (add.file) {
        form.append('file', add.file);
        add.scanFiles.forEach((scan) => form.append('scan_files', scan));
      } else {
        form.append('file', add.scanFiles[0]);
        add.scanFiles.slice(1).forEach((scan) => form.append('scan_files', scan));
      }
      form.append('name', add.name.trim());
      form.append('consent', add.consent ? 'true' : 'false');
      form.append('force_duplicate', add.forceDup ? 'true' : 'false');
      form.append('force_duplicate_name', add.forceName ? 'true' : 'false');
      if (add.notes.trim()) form.append('notes', add.notes.trim());
      const member = await apiUpload('/api/members', form);
      stopEnrolCamera();
      state.add.done = member;
      state.add.analysis = null;
      state.add.file = null;
      await Promise.all([refreshHealth(), refreshSession()]);
      toast(`${member.name} enrolled — live recognition is active`, 'success', 5200);
      renderAddMember();
    } catch (error) {
      if (error.code === 'duplicate_face') {
        state.add.forceDup = false;
        state.add.analysis = { ...(state.add.analysis || {}), duplicate: error.payload?.duplicate || state.add.analysis?.duplicate };
        toast('This face looks like an existing member. Confirm “It’s a different person” to override.', 'error', 6000);
      } else if (error.code === 'duplicate_name') {
        state.add.forceName = true;
        toast('A member with this name already exists. Press Enroll again to keep the name.', 'error', 6000);
      } else {
        state.add.error = error.message;
        toast(error.message, 'error', 5000);
      }
      renderAddMember();
    }
  }

  /* ----------------------------------------------------------- attendance */
  async function renderAttendance() {
    const [sessionsData] = await Promise.all([api('/api/sessions?limit=50'), refreshSession()]);
    state.sessions = sessionsData.items || [];
    const filters = state.filters;

    $('#view').innerHTML = `
      <div class="stack">
        <div class="card">
          <div class="card-head">
            <div><h2>Attendance history</h2><div class="sub" id="attendance-sub">Loading…</div></div>
            <div class="row">
              <a class="btn btn-ghost" id="btn-export" href="/api/attendance/export.csv${filters.session_id ? `?session_id=${encodeURIComponent(filters.session_id)}` : ''}">${icon('download')} Export CSV</a>
            </div>
          </div>
          <div class="card-body">
            <div class="form-grid" style="grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) minmax(0,1fr)">
              <div class="field">
                <label for="att-q">Search</label>
                <input class="input" id="att-q" placeholder="Member name or source…" value="${esc(filters.q)}" />
              </div>
              <div class="field">
                <label for="att-session">Session</label>
                <select class="input" id="att-session">
                  <option value="">All sessions</option>
                  ${state.sessions.map((session) => `<option value="${esc(session.id)}" ${filters.session_id === session.id ? 'selected' : ''}>${esc(session.name)}</option>`).join('')}
                </select>
              </div>
              <div class="field">
                <label for="att-date">Date</label>
                <input class="input" id="att-date" type="date" value="${esc(filters.date)}" />
              </div>
            </div>
          </div>
          <div id="attendance-table"></div>
          <div class="card-foot row-between" id="attendance-foot"></div>
        </div>
      </div>`;

    $('#att-q').addEventListener('input', debounce((event) => {
      state.filters.q = event.target.value;
      state.filters.offset = 0;
      loadAttendance();
    }, 240));
    $('#att-session').addEventListener('change', (event) => {
      state.filters.session_id = event.target.value;
      state.filters.offset = 0;
      updateExportLink();
      loadAttendance();
    });
    $('#att-date').addEventListener('change', (event) => {
      state.filters.date = event.target.value;
      state.filters.offset = 0;
      loadAttendance();
    });
    await loadAttendance();
  }

  function updateExportLink() {
    const link = $('#btn-export');
    if (!link) return;
    link.href = `/api/attendance/export.csv${state.filters.session_id ? `?session_id=${encodeURIComponent(state.filters.session_id)}` : ''}`;
  }

  async function loadAttendance() {
    const filters = state.filters;
    const params = new URLSearchParams({
      limit: String(filters.limit),
      offset: String(filters.offset),
    });
    if (filters.q) params.set('q', filters.q);
    if (filters.session_id) params.set('session_id', filters.session_id);
    if (filters.date) params.set('date', filters.date);
    const table = $('#attendance-table');
    if (!table) return;
    table.innerHTML = '<div class="card-body"><div class="skeleton" style="height:180px"></div></div>';
    try {
      const data = await api(`/api/attendance?${params}`);
      state.attendance = data;
      const sub = $('#attendance-sub');
      if (sub) sub.textContent = `${num(data.total)} record${data.total === 1 ? '' : 's'}`;
      const rows = data.items || [];
      table.innerHTML = rows.length
        ? `<div class="table-wrap"><table>
            <thead><tr><th>Member</th><th>Session</th><th>Method</th><th>Confidence</th><th>Recorded</th><th class="td-right">Actions</th></tr></thead>
            <tbody>${rows
              .map(
                (row) => `<tr>
                  <td><div class="cell-person"><span class="avatar">${esc(initials(row.member_name))}</span><div><div style="font-weight:600">${esc(row.member_name)}</div><div class="small muted">${esc(row.id)}</div></div></div></td>
                  <td class="small">${esc(row.session_name || '—')}</td>
                  <td><span class="badge ${row.method === 'live' ? 'info' : row.method === 'manual' ? 'warn' : ''}">${esc(row.method)}</span></td>
                  <td>${confidenceCell(row.confidence)}</td>
                  <td class="small muted nowrap">${esc(dateTimeOf(row.timestamp))}</td>
                  <td class="td-right"><button class="btn btn-danger-ghost btn-sm" data-remove-attendance="${esc(row.id)}">${icon('trash')} Remove</button></td>
                </tr>`,
              )
              .join('')}</tbody></table></div>`
        : emptyBlock('clock', 'No attendance records', 'Adjust the filters, or record attendance from the live camera.');
      const foot = $('#attendance-foot');
      if (foot) {
        const from = data.total ? filters.offset + 1 : 0;
        const to = Math.min(filters.offset + filters.limit, data.total);
        foot.innerHTML = `
          <span class="small muted">Showing ${from}–${to} of ${num(data.total)}</span>
          <div class="row">
            <button class="btn btn-ghost btn-sm" data-page="-1" ${filters.offset === 0 ? 'disabled' : ''}>${icon('chevronLeft')} Previous</button>
            <button class="btn btn-ghost btn-sm" data-page="1" ${to >= data.total ? 'disabled' : ''}>Next ${icon('chevronRight')}</button>
          </div>`;
      }
    } catch (error) {
      table.innerHTML = `<div class="card-body">${noticeBlock('bad', 'Could not load attendance', esc(error.message))}</div>`;
    }
  }

  async function removeAttendance(recordId) {
    const modal = openModal({
      title: 'Remove attendance record',
      subtitle: 'The record is soft-deleted and the change is written to the audit log.',
      body: `
        <div class="stack">
          <div class="field"><label for="remove-reason">Reason</label>
            <input class="input" id="remove-reason" placeholder="e.g. wrong person recognised" maxlength="300" />
          </div>
          <div class="field"><label for="remove-operator">Operator</label>
            <input class="input" id="remove-operator" value="${esc(state.settings?.values?.operator_name || 'Operator')}" maxlength="80" />
          </div>
        </div>`,
      actions: [
        { label: 'Cancel', class: 'btn-ghost' },
        {
          label: 'Remove record',
          class: 'btn-danger',
          onClick: async (close) => {
            const reason = $('#remove-reason')?.value.trim();
            const operator = $('#remove-operator')?.value.trim() || 'Operator';
            if (!reason || reason.length < 2) {
              toast('Add a short reason', 'error');
              return;
            }
            try {
              await api(`/api/attendance/${recordId}`, { method: 'DELETE', body: { reason, operator } });
              toast('Attendance record removed', 'success');
              close();
              await loadAttendance();
            } catch (error) {
              toast(error.message, 'error');
            }
          },
        },
      ],
    });
    setTimeout(() => $('#remove-reason')?.focus(), 60);
    return modal;
  }

  /* ------------------------------------------------------------- settings */
  const SETTING_GROUPS = [
    {
      title: 'Recognition',
      note: 'Calibrated on LFW; the default 0.42 threshold trades false accepts against missed matches.',
      fields: [
        { key: 'recognition_threshold', label: 'Match threshold', type: 'range', step: 0.01, hint: 'Cosine similarity required to accept an identity.' },
        { key: 'recognition_margin', label: 'Ambiguity margin', type: 'range', step: 0.01, hint: 'Top match must beat the runner-up by this gap.' },
        { key: 'detector_score_threshold', label: 'Detector confidence', type: 'range', step: 0.01, hint: 'YuNet score needed to consider a face.' },
        { key: 'min_face_size_px', label: 'Minimum face size (px)', type: 'number', step: 1, hint: 'Faces smaller than this at processing resolution are ignored.' },
      ],
    },
    {
      title: 'Tracking & temporal evidence',
      note: 'Evidence is accumulated per track so one blurry frame cannot decide an identity.',
      fields: [
        { key: 'track_iou_threshold', label: 'IoU association threshold', type: 'range', step: 0.01 },
        { key: 'track_max_age_frames', label: 'Track lifetime (frames)', type: 'number', step: 1 },
        { key: 'track_min_hits', label: 'Minimum hits', type: 'number', step: 1 },
        { key: 'evidence_window', label: 'Evidence window (frames)', type: 'number', step: 1 },
        { key: 'evidence_consistency', label: 'Vote consistency', type: 'range', step: 0.01 },
      ],
    },
    {
      title: 'Attendance',
      fields: [
        { key: 'attendance_cooldown_seconds', label: 'Cooldown (seconds)', type: 'number', step: 10, hint: 'Minimum gap before the same member can be recorded again.' },
        { key: 'attendance_require_session', label: 'Require an active session', type: 'boolean', hint: 'Create a session automatically when attendance is recorded.' },
      ],
    },
    {
      title: 'Capture & performance',
      fields: [
        { key: 'processing_width', label: 'Processing width (px)', type: 'number', step: 40, hint: 'Frames are downscaled before detection for speed.' },
        { key: 'target_fps', label: 'Target frame rate', type: 'number', step: 1, hint: 'Browser capture rate for live recognition.' },
      ],
    },
    {
      title: 'Enrollment quality',
      fields: [
        { key: 'enroll_min_face_ratio', label: 'Minimum face width (ratio)', type: 'range', step: 0.01 },
        { key: 'enroll_blur_threshold', label: 'Sharpness threshold', type: 'number', step: 5 },
        { key: 'enroll_min_brightness', label: 'Minimum brightness', type: 'number', step: 1 },
        { key: 'enroll_max_brightness', label: 'Maximum brightness', type: 'number', step: 1 },
        { key: 'duplicate_similarity', label: 'Duplicate-face similarity', type: 'range', step: 0.01 },
        { key: 'max_upload_mb', label: 'Max upload size (MB)', type: 'number', step: 1 },
      ],
    },
    {
      title: 'Privacy & operations',
      fields: [
        { key: 'store_thumbnails', label: 'Store member thumbnails', type: 'boolean', hint: 'Thumbnails are deleted with the member.' },
        { key: 'retain_unknown_events', label: 'Log unknown detections', type: 'boolean', hint: 'Counts and timestamps only — never images.' },
        { key: 'operator_name', label: 'Operator name', type: 'text' },
      ],
    },
  ];

  async function renderSettings() {
    const data = await api('/api/settings');
    state.settings = data;
    const values = data.values;
    $('#view').innerHTML = `
      <form class="stack" id="settings-form">
        ${data.admin_protected ? noticeBlock('ok', 'Settings are protected', 'Changes require the admin token configured on the server.') : noticeBlock('warn', 'Settings are open on this machine', 'For a shared deployment set <span class="mono">CRABBOTS_ADMIN_TOKEN</span> so only an operator with the token can change these values.')}
        <div class="grid cols-2">
          ${SETTING_GROUPS.map(
            (group) => `<div class="card">
              <div class="card-head"><div><h2>${esc(group.title)}</h2>${group.note ? `<div class="sub">${esc(group.note)}</div>` : ''}</div></div>
              <div class="card-body stack" style="gap:16px">
                ${group.fields.map((field) => settingField(field, values[field.key], data.bounds[field.key])).join('')}
              </div>
            </div>`,
          ).join('')}
        </div>
        <div class="card card-pad row-between">
          <div class="small muted">Changes apply to the next frame processed. No restart needed.</div>
          <div class="row">
            <button class="btn btn-ghost" type="button" id="btn-reset-settings">${icon('refresh')} Reset defaults</button>
            <button class="btn btn-primary" type="submit">${icon('check')} Save settings</button>
          </div>
        </div>
      </form>`;

    $('#settings-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const valuesOut = {};
      $$('[data-setting]').forEach((input) => {
        const key = input.dataset.setting;
        if (input.type === 'checkbox') valuesOut[key] = input.checked;
        else if (input.type === 'number' || input.type === 'range') valuesOut[key] = Number(input.value);
        else valuesOut[key] = input.value;
      });
      try {
        const result = await api('/api/settings', { method: 'PUT', body: { values: valuesOut } });
        state.settings = { ...state.settings, values: result.values };
        live.targetFps = Number(result.values.target_fps || 8);
        toast('Settings saved', 'success');
        renderSettings();
      } catch (error) {
        toast(error.message, 'error', 5000);
      }
    });

    $('#btn-reset-settings').addEventListener('click', async () => {
      const ok = await confirmDialog({
        title: 'Reset all settings?',
        message: 'Thresholds, tracking and privacy options return to their documented defaults.',
        confirmLabel: 'Reset',
      });
      if (!ok) return;
      try {
        const result = await api('/api/settings/reset', { method: 'POST' });
        state.settings = { ...state.settings, values: result.values };
        toast('Defaults restored', 'success');
        renderSettings();
      } catch (error) {
        toast(error.message, 'error');
      }
    });

    $$('input[type="range"][data-setting]').forEach((range) => {
      range.addEventListener('input', () => {
        const display = $(`[data-value-for="${range.dataset.setting}"]`);
        if (display) display.textContent = Number(range.value).toFixed(range.step.includes('.') ? 2 : 0);
      });
    });
  }

  function settingField(field, value, bounds) {
    const min = bounds ? bounds[0] : 0;
    const max = bounds ? bounds[1] : 100;
    if (field.type === 'boolean') {
      return `<label class="check"><input type="checkbox" data-setting="${field.key}" ${value ? 'checked' : ''} />
        <span><strong>${esc(field.label)}</strong>${field.hint ? `<br><span class="small muted">${esc(field.hint)}</span>` : ''}</span></label>`;
    }
    if (field.type === 'text') {
      return `<div class="field"><label for="set-${field.key}">${esc(field.label)}</label>
        <input class="input" id="set-${field.key}" data-setting="${field.key}" value="${esc(value)}" maxlength="80" /></div>`;
    }
    if (field.type === 'range') {
      const decimals = String(field.step).includes('.') ? 2 : 0;
      return `<div class="field">
        <div class="row-between"><label for="set-${field.key}">${esc(field.label)}</label>
          <span class="range-val" data-value-for="${field.key}">${Number(value).toFixed(decimals)}</span></div>
        <div class="range-row">
          <input type="range" id="set-${field.key}" data-setting="${field.key}" min="${min}" max="${max}" step="${field.step}" value="${value}" />
        </div>
        ${field.hint ? `<span class="hint">${esc(field.hint)}</span>` : ''}
      </div>`;
    }
    return `<div class="field"><label for="set-${field.key}">${esc(field.label)}</label>
      <input class="input" type="number" id="set-${field.key}" data-setting="${field.key}" min="${min}" max="${max}" step="${field.step || 1}" value="${value}" />
      ${field.hint ? `<span class="hint">${esc(field.hint)}</span>` : ''}</div>`;
  }

  /* -------------------------------------------------------------- sessions */
  async function openSessionsModal() {
    let sessions = [];
    try {
      const data = await api('/api/sessions?limit=30');
      sessions = data.items || [];
    } catch (error) {
      toast(error.message, 'error');
      return;
    }
    const active = state.activeSession;
    const modal = openModal({
      title: 'Sessions',
      subtitle: 'Attendance is unique per member per session.',
      wide: true,
      body: `
        <div class="stack">
          <div class="row" style="gap:8px">
            <input class="input" id="new-session-name" placeholder="New session name (optional)" maxlength="120" style="flex:1" />
            <button class="btn btn-primary" id="btn-create-session">${icon('plus')} Start new session</button>
          </div>
          <div class="divider"></div>
          <div class="stack" style="gap:8px">
            ${sessions
              .map(
                (session) => `<div class="row-between" style="padding:10px 12px;border:1px solid var(--line);border-radius:10px">
                  <div><div style="font-weight:600;font-size:13px">${esc(session.name)}</div>
                  <div class="small muted">${esc(dateTimeOf(session.started_at || session.created_at))} · ${session.present_count} present ${session.is_demo ? '· demo' : ''}</div></div>
                  <div class="row">
                    ${session.status === 'active' ? '<span class="badge ok dot">Active</span>' : '<span class="badge">Ended</span>'}
                    ${session.status === 'active'
                      ? `<button class="btn btn-ghost btn-sm" data-end="${esc(session.id)}">End</button>`
                      : `<button class="btn btn-ghost btn-sm" data-start="${esc(session.id)}">Start</button>`}
                  </div>
                </div>`,
              )
              .join('') || '<div class="small muted">No sessions yet.</div>'}
          </div>
        </div>`,
      actions: [{ label: 'Done', class: 'btn-primary' }],
    });

    $('#btn-create-session').addEventListener('click', async () => {
      const name = $('#new-session-name')?.value.trim() || null;
      try {
        await api('/api/sessions', { method: 'POST', body: { name } });
        await refreshSession();
        toast('Session started', 'success');
        modal.close();
        if (currentRoute().id === 'dashboard') renderDashboard();
        if (currentRoute().id === 'live') renderLiveSession();
      } catch (error) {
        toast(error.message, 'error');
      }
    });

    modal.root.addEventListener('click', async (event) => {
      const start = event.target.closest('[data-start]');
      const end = event.target.closest('[data-end]');
      if (!start && !end) return;
      const id = (start || end).dataset.start || (start || end).dataset.end;
      try {
        await api(`/api/sessions/${id}/${start ? 'start' : 'end'}`, { method: 'POST' });
        await refreshSession();
        toast(start ? 'Session started' : 'Session ended', 'success');
        modal.close();
        openSessionsModal();
        if (currentRoute().id === 'live') renderLiveSession();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
    return modal;
  }

  /* ------------------------------------------------------------------ boot */
  async function init() {
    renderNav();
    bindShell();
    try {
      state.settings = await api('/api/settings');
    } catch {
      state.settings = null;
    }
    await Promise.allSettled([refreshHealth(), refreshSession()]);
    window.addEventListener('hashchange', route);
    if (!location.hash) {
      location.hash = '#/dashboard';
    } else {
      route();
    }
    setInterval(refreshHealth, 20000);
    setInterval(() => {
      if (document.visibilityState === 'visible' && currentRoute().id === 'dashboard') refreshSession();
    }, 30000);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
