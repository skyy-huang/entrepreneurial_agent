'use strict';

let token = '';
let teams = [];
const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

async function request(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { ...(options.headers || {}), Authorization: token } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `请求失败（${response.status}）`);
  return data;
}

async function login(event) {
  event.preventDefault();
  $('loginError').textContent = '';
  try {
    const response = await fetch('/api/teacher/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: $('teacherUsername').value.trim(), password: $('teacherPassword').value }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '登录失败');
    token = data.token;
    $('teacherIdentity').textContent = `${data.username} · ${data.role}`;
    $('loginView').classList.add('hidden');
    $('dashboardView').classList.remove('hidden');
    await loadDashboard();
  } catch (error) { $('loginError').textContent = error.message; }
}

async function loadDashboard() {
  try {
    const data = await request('/api/teacher/dashboard');
    teams = data.team_details || [];
    $('totalTeams').textContent = data.total_teams ?? 0;
    $('highRiskCount').textContent = data.high_risk_count ?? 0;
    $('improvingCount').textContent = data.learning_value_index?.improving ?? 0;
    $('improvementRate').textContent = `${data.learning_value_index?.improvement_rate ?? 0}%`;
    $('lastUpdate').textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`;
    renderSuggestions(data.teaching_suggestions || []);
    renderDistribution(data.phase_distribution || {});
    renderTeams(teams);
  } catch (error) { $('suggestionsList').innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

function renderSuggestions(items) {
  $('suggestionsList').innerHTML = items.length ? items.slice(0, 4).map((item, index) => `<div class="suggestion"><span>0${index + 1}</span><p>${escapeHtml(item).replace(/\n/g, '<br>')}</p></div>`).join('') : '<p class="empty-state">当前没有足够数据生成建议。</p>';
}

function renderDistribution(distribution) {
  const entries = Object.entries(distribution);
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
  $('phaseDistribution').innerHTML = entries.length ? entries.map(([label, count]) => `<div class="distribution-row"><div><span>${escapeHtml(label)}</span><strong>${count}</strong></div><div class="distribution-track"><i style="width:${count / total * 100}%"></i></div></div>`).join('') : '<p class="empty-state">暂无阶段数据。</p>';
}

function renderTeams(items) {
  $('teamTableBody').innerHTML = items.length ? items.map((team) => {
    const scores = team.capability_scores || {};
    const average = Number(team.avg_score || 0).toFixed(1);
    return `<tr><td><strong>${escapeHtml(team.student_id)}</strong><small>${escapeHtml(team.session_id)}</small></td><td>${escapeHtml(team.current_phase)}</td><td>${team.round_count}</td><td><div class="table-risks">${(team.triggered_rules || []).slice(0, 4).map((rule) => `<span>${escapeHtml(rule)}</span>`).join('') || '<i>—</i>'}</div></td><td><strong>${average}</strong><small>${Object.values(scores).length} 项能力</small></td></tr>`;
  }).join('') : '<tr><td colspan="5" class="empty-state">暂无有效项目数据。</td></tr>';
}

$('loginForm').addEventListener('submit', login);
$('refreshBtn').addEventListener('click', loadDashboard);
$('teamSearch').addEventListener('input', (event) => { const query = event.target.value.trim().toLowerCase(); renderTeams(teams.filter((team) => `${team.student_id} ${(team.triggered_rules || []).join(' ')}`.toLowerCase().includes(query))); });
