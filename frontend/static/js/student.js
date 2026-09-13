'use strict';

const PHASES = { value_probe: '价值探测', pressure_test: '压力测试', landing_check: '落地校验' };
const SCORE_LABELS = { pain_point_discovery: '痛点发现', solution_planning: '方案策划', business_modeling: '商业建模', resource_leverage: '资源杠杆', pitch_expression: '路演表达' };
let sessionId = null;
let studentId = '';
let password = '';
let history = [];

const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

function showError(message) { $('accessError').textContent = message; }
function api(url, options = {}) {
  return fetch(url, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options }).then(async (response) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `请求失败（${response.status}）`);
    return data;
  });
}

async function enterWorkspace(event) {
  event.preventDefault();
  studentId = $('studentIdInput').value.trim();
  password = $('studentPasswordInput').value.trim();
  if (!studentId || !password) return;
  $('startBtn').disabled = true;
  $('startBtn').innerHTML = '正在进入…';
  showError('');
  try {
    const login = await api('/api/student/login', { method: 'POST', body: JSON.stringify({ student_id: studentId, password }) });
    history = login.history || [];
    await createSession();
  } catch (error) {
    showError(error.message);
    $('startBtn').disabled = false;
    $('startBtn').innerHTML = '进入工作台 <span>↗</span>';
  }
}

async function createSession() {
  const data = await api('/api/session/start', { method: 'POST', body: JSON.stringify({ student_id: studentId, password }) });
  sessionId = data.session_id;
  history.unshift({ session_id: sessionId, current_phase: data.current_phase, round_count: 0 });
  openWorkspace(data);
}

async function resumeSession(id) {
  try {
    const data = await api(`/api/session/${encodeURIComponent(id)}`);
    sessionId = id;
    openWorkspace({ ...data, welcome_message: null });
    $('messagesWrap').innerHTML = '';
    (data.messages || []).forEach((message) => appendMessage(message.content, message.role));
  } catch (error) { showError(error.message); }
}

function openWorkspace(data) {
  $('welcomePanel').classList.add('hidden');
  $('workspace').classList.remove('hidden');
  $('sessionInfo').textContent = `ID ${data.session_id}`;
  $('projectTitle').textContent = `项目 ${data.session_id}`;
  $('messagesWrap').innerHTML = '';
  if (data.welcome_message) appendMessage(data.welcome_message, 'assistant');
  updateState(data);
  renderHistory();
}

function renderHistory() {
  $('historyList').innerHTML = history.length ? history.map((item) => `<button class="history-item ${item.session_id === sessionId ? 'active' : ''}" data-session="${escapeHtml(item.session_id)}"><strong>项目 ${escapeHtml(item.session_id)}</strong><span>${escapeHtml(PHASES[item.current_phase] || item.current_phase || '价值探测')} · ${item.round_count || 0} 轮</span></button>`).join('') : '<div class="rail-empty">还没有历史项目。</div>';
  document.querySelectorAll('.history-item').forEach((item) => item.addEventListener('click', () => resumeSession(item.dataset.session)));
}

function appendMessage(content, role) {
  const item = document.createElement('article');
  item.className = `message message-${role === 'user' ? 'user' : 'assistant'}`;
  item.innerHTML = `<div class="message-role">${role === 'user' ? '你' : '原点'}</div><div class="message-body">${escapeHtml(content).replace(/\n/g, '<br>')}</div>`;
  $('messagesWrap').appendChild(item);
  $('messagesWrap').scrollTop = $('messagesWrap').scrollHeight;
}

function updateState(data) {
  const phase = PHASES[data.current_phase] || '价值探测';
  $('phaseLabel').textContent = phase;
  $('phasePill').textContent = phase;
  $('roundCount').textContent = data.round_count || 0;
  const scores = data.capability_scores || {};
  $('scoresGrid').innerHTML = Object.entries(SCORE_LABELS).map(([key, label]) => `<div class="score-row"><span>${label}</span><strong>${Number(scores[key] ?? 5).toFixed(1)}</strong><div class="score-track"><i style="width:${Math.max(0, Math.min(100, Number(scores[key] ?? 5) * 10))}%"></i></div></div>`).join('');
  const fallacies = data.detected_fallacies || [];
  $('fallacyCount').textContent = fallacies.length;
  $('fallaciesList').innerHTML = fallacies.length ? fallacies.slice(0, 4).map((item) => `<div class="risk-item"><span>${escapeHtml(item.rule_id || '—')}</span><p>${escapeHtml(item.name || item.description || '待验证问题')}</p></div>`).join('') : '<p class="empty-state">目前没有新的逻辑缺口。</p>';
  $('taskText').textContent = data.next_task || '完成第一轮描述后，这里会出现一个明确动作。';
}

async function sendMessage(event) {
  event.preventDefault();
  const input = $('userInput');
  const message = input.value.trim();
  if (!message || !sessionId) return;
  appendMessage(message, 'user');
  input.value = '';
  $('sendBtn').disabled = true;
  $('sendBtn').innerHTML = '诊断中…';
  try {
    const data = await api('/api/chat', { method: 'POST', body: JSON.stringify({ session_id: sessionId, message, agent_mode: 'coach' }) });
    appendMessage(data.coach_response, 'assistant');
    updateState(data);
    const item = history.find((entry) => entry.session_id === sessionId);
    if (item) { item.round_count = data.round_count; item.current_phase = data.current_phase; }
    renderHistory();
  } catch (error) { appendMessage(`请求未完成：${error.message}`, 'assistant'); }
  finally { $('sendBtn').disabled = false; $('sendBtn').innerHTML = '发送 <span>↗</span>'; input.focus(); }
}

$('accessForm').addEventListener('submit', enterWorkspace);
$('composerForm').addEventListener('submit', sendMessage);
$('userInput').addEventListener('keydown', (event) => { if (event.key === 'Enter' && event.ctrlKey) sendMessage(event); });
$('newSessionBtn').addEventListener('click', createSession);
$('railNewBtn').addEventListener('click', createSession);
