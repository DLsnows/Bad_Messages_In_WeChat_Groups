/* ── API Client ──────────────────────────────────────────── */
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${resp.status}`);
  }
  // Handle 204 No Content
  const text = await resp.text();
  return text ? JSON.parse(text) : {};
}

/* ── Toast Notifications ────────────────────────────────── */
function showToast(message, type) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => { el.remove(); }, 3000);
}

/* ── Tab Switching ──────────────────────────────────────── */
function switchTab(name) {
  document.querySelectorAll('.tab-panel').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.getElementById(`tab-${name}`).classList.add('active');
  const navItem = document.querySelector(`.nav-item[data-tab="${name}"]`);
  if (navItem) navItem.classList.add('active');

  // Refresh data on tab switch
  if (name === 'dashboard') loadStatus();
  if (name === 'groups') loadGroups();
  if (name === 'admins') loadAdmins();
  if (name === 'keywords') loadKeywords();
  if (name === 'settings') loadConfig();
  if (name === 'alerts') loadAlerts(1);
}

/* ── Status Polling ─────────────────────────────────────── */
let statusInterval = null;

async function loadStatus() {
  try {
    const data = await api('GET', '/api/v1/status');
    const runningEl = document.getElementById('status-running');
    runningEl.textContent = data.is_running ? '运行中' : '已停止';
    runningEl.style.color = data.is_running ? '#52b788' : '#e94560';
    document.getElementById('status-last-check').textContent = data.last_check_time || '-';
    document.getElementById('status-groups').textContent = data.monitored_groups_count;
    document.getElementById('status-admins').textContent = data.admins_count;
    document.getElementById('status-detected').textContent = data.detected_today;
  } catch (e) {
    console.error('Status poll error:', e);
  }
}

if (!statusInterval) {
  loadStatus();
  statusInterval = setInterval(loadStatus, 5000);
}

/* ── Bot Control ────────────────────────────────────────── */
async function startBot() {
  try {
    const result = await api('POST', '/api/v1/bot/start');
    showToast(result.message || '监控已启动', 'success');
    loadStatus();
  } catch (e) {
    showToast('启动失败: ' + e.message, 'error');
  }
}

async function stopBot() {
  try {
    const result = await api('POST', '/api/v1/bot/stop');
    showToast(result.message || '监控已停止', 'info');
    loadStatus();
  } catch (e) {
    showToast('停止失败: ' + e.message, 'error');
  }
}

/* ── Groups ─────────────────────────────────────────────── */
async function loadGroups() {
  try {
    const groups = await api('GET', '/api/v1/groups');
    const tbody = document.getElementById('groups-tbody');
    tbody.innerHTML = groups.map(g => `
      <tr>
        <td>${escapeHtml(g.group_name)}</td>
        <td><span class="badge ${g.is_active ? 'badge-active' : 'badge-inactive'}">${g.is_active ? '监控中' : '已暂停'}</span></td>
        <td>${formatDate(g.created_at)}</td>
        <td>
          <button class="btn btn-sm ${g.is_active ? 'btn-warning' : 'btn-success'}" onclick="toggleGroup(${g.id})">${g.is_active ? '暂停' : '恢复'}</button>
          <button class="btn btn-danger-sm" onclick="deleteGroup(${g.id})">删除</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    showToast('加载群组失败: ' + e.message, 'error');
  }
}

async function addGroup() {
  const input = document.getElementById('group-name-input');
  const name = input.value.trim();
  if (!name) { showToast('请输入群名称', 'error'); return; }
  try {
    await api('POST', '/api/v1/groups', { group_name: name });
    input.value = '';
    showToast('群组已添加', 'success');
    loadGroups();
  } catch (e) {
    showToast('添加失败: ' + e.message, 'error');
  }
}

async function deleteGroup(id) {
  if (!confirm('确定删除此群组？')) return;
  try {
    await api('DELETE', `/api/v1/groups/${id}`);
    showToast('群组已删除', 'success');
    loadGroups();
  } catch (e) {
    showToast('删除失败: ' + e.message, 'error');
  }
}

async function toggleGroup(id) {
  try {
    await api('PATCH', `/api/v1/groups/${id}/toggle`);
    loadGroups();
  } catch (e) {
    showToast('操作失败: ' + e.message, 'error');
  }
}

async function discoverSessions() {
  try {
    const sessions = await api('GET', '/api/v1/wechat/sessions');
    const container = document.getElementById('session-list');
    if (!sessions.length) {
      container.innerHTML = '<div class="session-item">未获取到会话列表，请确保微信已登录</div>';
      container.style.display = 'block';
      return;
    }
    container.innerHTML = sessions.map(s =>
      `<div class="session-item" onclick="fillGroupName('${escapeHtml(s.name)}')">${escapeHtml(s.name)} ${s.chat_type ? '(' + s.chat_type + ')' : ''}</div>`
    ).join('');
    container.style.display = 'block';
  } catch (e) {
    showToast('获取会话失败: ' + e.message, 'error');
  }
}

function fillGroupName(name) {
  document.getElementById('group-name-input').value = name;
  document.getElementById('session-list').style.display = 'none';
}

/* ── Admins ─────────────────────────────────────────────── */
async function loadAdmins() {
  try {
    const admins = await api('GET', '/api/v1/admins');
    const tbody = document.getElementById('admins-tbody');
    tbody.innerHTML = admins.map(a => `
      <tr>
        <td>${escapeHtml(a.admin_name)}</td>
        <td>${escapeHtml(a.wechat_id)}</td>
        <td><span class="badge ${a.is_active ? 'badge-active' : 'badge-inactive'}">${a.is_active ? '启用' : '停用'}</span></td>
        <td>${formatDate(a.created_at)}</td>
        <td>
          <button class="btn btn-sm ${a.is_active ? 'btn-warning' : 'btn-success'}" onclick="toggleAdmin(${a.id})">${a.is_active ? '停用' : '启用'}</button>
          <button class="btn btn-danger-sm" onclick="deleteAdmin(${a.id})">删除</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    showToast('加载管理员失败: ' + e.message, 'error');
  }
}

async function addAdmin() {
  const name = document.getElementById('admin-name-input').value.trim();
  const wxid = document.getElementById('admin-wxid-input').value.trim();
  if (!name || !wxid) { showToast('请填写昵称和微信号', 'error'); return; }
  try {
    await api('POST', '/api/v1/admins', { admin_name: name, wechat_id: wxid });
    document.getElementById('admin-name-input').value = '';
    document.getElementById('admin-wxid-input').value = '';
    showToast('管理员已添加', 'success');
    loadAdmins();
  } catch (e) {
    showToast('添加失败: ' + e.message, 'error');
  }
}

async function deleteAdmin(id) {
  if (!confirm('确定删除此管理员？')) return;
  try {
    await api('DELETE', `/api/v1/admins/${id}`);
    showToast('管理员已删除', 'success');
    loadAdmins();
  } catch (e) {
    showToast('删除失败: ' + e.message, 'error');
  }
}

async function toggleAdmin(id) {
  try {
    await api('PATCH', `/api/v1/admins/${id}/toggle`);
    loadAdmins();
  } catch (e) {
    showToast('操作失败: ' + e.message, 'error');
  }
}

/* ── Keywords ───────────────────────────────────────────── */
async function loadKeywords() {
  try {
    const data = await api('GET', '/api/v1/config/keywords');
    document.getElementById('keywords-textarea').value = data.keywords.join('\n');
  } catch (e) {
    showToast('加载关键词失败: ' + e.message, 'error');
  }
}

async function saveKeywords() {
  const text = document.getElementById('keywords-textarea').value;
  const keywords = text.split('\n').map(s => s.trim()).filter(s => s && !s.startsWith('#'));
  try {
    await api('PUT', '/api/v1/config/keywords', { keywords });
    document.getElementById('keywords-save-status').textContent = '已保存 ' + keywords.length + ' 个关键词';
    setTimeout(() => { document.getElementById('keywords-save-status').textContent = ''; }, 3000);
    showToast('关键词已保存', 'success');
  } catch (e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

/* ── Settings ───────────────────────────────────────────── */
async function loadConfig() {
  try {
    const cfg = await api('GET', '/api/v1/config');
    document.getElementById('setting-interval').value = cfg.monitoring_interval;
    document.getElementById('setting-history-count').value = cfg.history_message_count;
    document.getElementById('setting-llm-base-url').value = cfg.llm_base_url;
    document.getElementById('setting-llm-api-key').value = '';
    document.getElementById('setting-llm-model').value = cfg.llm_model;
    document.getElementById('setting-llm-max-tokens').value = cfg.llm_max_tokens;
    document.getElementById('setting-llm-temperature').value = cfg.llm_temperature;
  } catch (e) {
    showToast('加载配置失败: ' + e.message, 'error');
  }
}

async function saveSettings() {
  const body = {};
  const interval = parseInt(document.getElementById('setting-interval').value);
  if (!isNaN(interval)) body.monitoring_interval = interval;

  const historyCount = parseInt(document.getElementById('setting-history-count').value);
  if (!isNaN(historyCount)) body.history_message_count = historyCount;

  const baseUrl = document.getElementById('setting-llm-base-url').value.trim();
  if (baseUrl) body.llm_base_url = baseUrl;

  const apiKey = document.getElementById('setting-llm-api-key').value.trim();
  if (apiKey) body.llm_api_key = apiKey;

  const model = document.getElementById('setting-llm-model').value.trim();
  if (model) body.llm_model = model;

  const maxTokens = parseInt(document.getElementById('setting-llm-max-tokens').value);
  if (!isNaN(maxTokens)) body.llm_max_tokens = maxTokens;

  const temp = parseFloat(document.getElementById('setting-llm-temperature').value);
  if (!isNaN(temp)) body.llm_temperature = temp;

  try {
    await api('PUT', '/api/v1/config', body);
    document.getElementById('settings-save-status').textContent = '设置已保存';
    setTimeout(() => { document.getElementById('settings-save-status').textContent = ''; }, 3000);
    showToast('设置已保存', 'success');
  } catch (e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

/* ── Alerts ─────────────────────────────────────────────── */
let currentAlertPage = 1;
let currentAlertTotalPages = 1;

async function loadAlerts(page) {
  currentAlertPage = page;
  const verdict = document.getElementById('alert-filter-verdict').value;
  let url = `/api/v1/detected-messages?page=${page}&page_size=20`;
  if (verdict === '__none__') url += '&verdict=null';
  else if (verdict) url += `&verdict=${verdict}`;

  try {
    const data = await api('GET', url);
    const tbody = document.getElementById('alerts-tbody');
    tbody.innerHTML = data.items.map(m => `
      <tr>
        <td>${escapeHtml(m.group_name)}</td>
        <td>${escapeHtml(m.sender)}</td>
        <td title="${escapeHtml(m.content)}">${escapeHtml(m.content.substring(0, 60))}${m.content.length > 60 ? '...' : ''}</td>
        <td><span class="badge badge-warning">${escapeHtml(m.matched_keyword)}</span></td>
        <td>${verdictBadge(m.llm_verdict)}</td>
        <td><span class="badge ${m.is_notified ? 'badge-notified' : 'badge-silent'}">${m.is_notified ? '已通知' : '未通知'}</span></td>
        <td>${formatDate(m.detected_at)}</td>
      </tr>
    `).join('');

    currentAlertTotalPages = data.total_pages;
    document.getElementById('alert-pagination').textContent =
      `共 ${data.total} 条记录 (第 ${data.page}/${data.total_pages} 页)`;

    renderPagination(data.page, data.total_pages);
  } catch (e) {
    showToast('加载告警记录失败: ' + e.message, 'error');
  }
}

function renderPagination(page, totalPages) {
  const container = document.getElementById('alert-page-controls');
  if (totalPages <= 1) { container.innerHTML = ''; return; }

  let html = '';
  if (page > 1) html += `<button onclick="loadAlerts(1)">首页</button><button onclick="loadAlerts(${page - 1})">上一页</button>`;

  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, page + 2);
  for (let i = start; i <= end; i++) {
    html += `<button class="${i === page ? 'active-page' : ''}" onclick="loadAlerts(${i})">${i}</button>`;
  }

  if (page < totalPages) html += `<button onclick="loadAlerts(${page + 1})">下一页</button><button onclick="loadAlerts(${totalPages})">末页</button>`;
  container.innerHTML = html;
}

function verdictBadge(verdict) {
  if (!verdict) return '<span class="badge badge-unreviewed">未审核</span>';
  if (verdict === 'malicious') return '<span class="badge badge-malicious">恶意</span>';
  return '<span class="badge badge-benign">良性</span>';
}

/* ── Utilities ──────────────────────────────────────────── */
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  });
}
