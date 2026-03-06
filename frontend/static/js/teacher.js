/* ════════════════════════════════════════════════
   teacher.js — 教师端看板逻辑
   ════════════════════════════════════════════════ */
'use strict';

let ruleBarChart = null;
let classRadarChart = null;
let phaseChart = null;
let allTeamData = [];

const SCORE_LABELS = {
  pain_point_discovery: '痛点发现',
  solution_planning:    '方案策划',
  business_modeling:    '商业建模',
  resource_leverage:    '资源杠杆',
  pitch_expression:     '路演表达',
};

const HIGH_SEVERITY_RULES = new Set(['H1','H2','H5','H6','H7','H8','H10','H13','H14']);

// ── 初始化 ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  document.getElementById('refreshBtn').addEventListener('click', loadDashboard);
  document.getElementById('teamSearch').addEventListener('input', filterTable);
});

// ── 加载看板数据 ────────────────────────────────────
async function loadDashboard() {
  const refreshBtn = document.getElementById('refreshBtn');
  refreshBtn.disabled = true;
  refreshBtn.textContent = '加载中…';
  try {
    const data = await fetch('/api/teacher/dashboard').then(r => r.json());
    renderDashboard(data);
    document.getElementById('lastUpdate').textContent =
      '最后更新：' + new Date().toLocaleTimeString('zh-CN');
  } catch (err) {
    console.error('加载看板失败', err);
    document.getElementById('suggestionsList').innerHTML =
      `<p style="color:#ef4444">加载失败：${err.message}</p>`;
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = '🔄 刷新';
  }
}

// ── 渲染全局看板 ──────────────────────────────────
function renderDashboard(data) {
  allTeamData = data.team_details || [];

  // 摘要卡片
  document.getElementById('totalTeams').textContent = data.total_teams;
  document.getElementById('highRiskCount').textContent = data.high_risk_count || 0;
  document.getElementById('improvingCount').textContent =
    data.learning_value_index?.improving || 0;
  document.getElementById('stagnantCount').textContent =
    data.learning_value_index?.stagnant || 0;
  document.getElementById('improvementRate').textContent =
    (data.learning_value_index?.improvement_rate || 0) + '%';

  // 教学建议
  renderSuggestions(data.teaching_suggestions || []);

  // 规则排行榜
  renderRuleChart(data.rule_ranking || []);
  renderRuleDetails(data.rule_ranking || []);

  // 班级能力雷达
  renderClassRadar(data.avg_capability_scores || {});

  // 阶段分布
  renderPhaseChart(data.phase_distribution || {});

  // 团队表格
  renderTeamTable(allTeamData);
}

// ── 教学建议 ──────────────────────────────────────
function renderSuggestions(suggestions) {
  const el = document.getElementById('suggestionsList');
  if (!suggestions.length) {
    el.innerHTML = '<p class="loading-hint">暂无建议数据</p>';
    return;
  }
  el.innerHTML = suggestions.map(s => {
    let cls = 'green';
    if (s.startsWith('🔴')) cls = 'red';
    else if (s.startsWith('🟡')) cls = 'yellow';
    return `<div class="suggestion-item ${cls}">${escHtml(s)}</div>`;
  }).join('');
}

// ── 规则柱状图 ────────────────────────────────────
function renderRuleChart(ranking) {
  const ctx = document.getElementById('ruleBarChart').getContext('2d');
  const top = ranking.slice(0, 10);
  const labels = top.map(r => r.rule_id);
  const values = top.map(r => r.percentage);
  const colors = top.map(r =>
    r.severity === 'high' ? 'rgba(239,68,68,0.7)' : 'rgba(245,158,11,0.7)'
  );

  if (ruleBarChart) ruleBarChart.destroy();
  ruleBarChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '触发率 (%)',
        data: values,
        backgroundColor: colors,
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          max: 100,
          ticks: { color: '#94a3b8', callback: v => v + '%' },
          grid: { color: '#334155' },
        },
        y: {
          ticks: { color: '#e2e8f0', font: { weight: 'bold' } },
          grid: { display: false },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.raw}% 的团队触发`,
          },
        },
      },
    },
  });
}

// ── 规则详情列表 ──────────────────────────────────
function renderRuleDetails(ranking) {
  const el = document.getElementById('ruleDetailList');
  el.innerHTML = ranking.slice(0, 8).map(r => `
    <div class="rule-detail-item">
      <span class="rule-badge">${r.rule_id}</span>
      <span class="rule-pct">${r.percentage}%</span>
      <span class="rule-name">${r.name}</span>
      <span style="font-size:11px;color:#475569">${r.count}队</span>
    </div>
  `).join('');
}

// ── 班级能力雷达 ──────────────────────────────────
function renderClassRadar(scores) {
  const ctx = document.getElementById('classRadarChart').getContext('2d');
  const labels = Object.values(SCORE_LABELS);
  const values = Object.keys(SCORE_LABELS).map(k => scores[k] || 5);

  if (classRadarChart) classRadarChart.destroy();
  classRadarChart = new Chart(ctx, {
    type: 'radar',
    data: {
      labels,
      datasets: [{
        label: '班级平均',
        data: values,
        backgroundColor: 'rgba(16,185,129,0.15)',
        borderColor: '#10b981',
        pointBackgroundColor: '#10b981',
        borderWidth: 2,
        pointRadius: 3,
      }],
    },
    options: {
      scales: {
        r: {
          min: 0, max: 10,
          ticks: { stepSize: 2, color: '#475569', backdropColor: 'transparent', font: { size: 10 } },
          grid: { color: '#334155' },
          angleLines: { color: '#334155' },
          pointLabels: { color: '#94a3b8', font: { size: 11 } },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
}

// ── 阶段分布饼图 ──────────────────────────────────
function renderPhaseChart(dist) {
  const ctx = document.getElementById('phaseChart').getContext('2d');
  const entries = Object.entries(dist);
  if (phaseChart) phaseChart.destroy();
  if (!entries.length) return;

  phaseChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: entries.map(([k]) => k),
      datasets: [{
        data: entries.map(([, v]) => v),
        backgroundColor: ['rgba(37,99,235,0.7)', 'rgba(245,158,11,0.7)', 'rgba(16,185,129,0.7)'],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'right',
          labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 12, padding: 12 },
        },
      },
    },
  });
}

// ── 团队表格 ──────────────────────────────────────
function renderTeamTable(teams) {
  const tbody = document.getElementById('teamTableBody');
  if (!teams.length) {
    tbody.innerHTML = '<tr><td colspan="10" class="loading-hint">暂无团队数据</td></tr>';
    return;
  }
  tbody.innerHTML = teams.map(t => {
    const s = t.capability_scores || {};
    const avg = t.avg_score || 5;
    const avgCls = avg >= 7 ? 'high' : avg >= 5 ? 'mid' : 'low';

    const ruleTags = (t.triggered_rules || []).map(rid => {
      const isHigh = HIGH_SEVERITY_RULES.has(rid);
      return `<span class="rule-tag ${isHigh ? 'high-sev' : ''}">${rid}</span>`;
    }).join('');

    return `<tr>
      <td><strong>${escHtml(t.student_id)}</strong></td>
      <td>${escHtml(t.current_phase)}</td>
      <td>${t.round_count}</td>
      <td><div class="rule-tags">${ruleTags || '–'}</div></td>
      ${scoreCell(s.pain_point_discovery)}
      ${scoreCell(s.solution_planning)}
      ${scoreCell(s.business_modeling)}
      ${scoreCell(s.resource_leverage)}
      ${scoreCell(s.pitch_expression)}
      <td><span class="score-chip ${avgCls}">${avg}</span></td>
    </tr>`;
  }).join('');
}

function scoreCell(val) {
  if (val === undefined || val === null) return '<td>–</td>';
  const n = parseFloat(val);
  const cls = n >= 7 ? 'high' : n >= 5 ? 'mid' : 'low';
  return `<td><span class="score-chip ${cls}">${n.toFixed(1)}</span></td>`;
}

// ── 表格搜索 ──────────────────────────────────────
function filterTable() {
  const q = document.getElementById('teamSearch').value.trim().toLowerCase();
  if (!q) { renderTeamTable(allTeamData); return; }
  renderTeamTable(allTeamData.filter(t =>
    t.student_id.toLowerCase().includes(q) ||
    (t.triggered_rules || []).some(r => r.toLowerCase().includes(q))
  ));
}

// ── 工具 ──────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
