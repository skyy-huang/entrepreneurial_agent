/* ════════════════════════════════════════════════
   teacher.js — 教师端看板逻辑（嵌入式，配合 role_switcher.js）
   ════════════════════════════════════════════════ */
'use strict';

let ruleBarChart = null;
let classRadarChart = null;
let phaseChart = null;
let allTeamData = [];

const TEACHER_SCORE_LABELS = {
  pain_point_discovery: '痛点发现',
  solution_planning:    '方案策划',
  business_modeling:    '商业建模',
  resource_leverage:    '资源杠杆',
  pitch_expression:     '路演表达',
};

const HIGH_SEVERITY_RULES = new Set(['H1','H2','H5','H6','H7','H8','H10','H13','H14']);

// ── 初始化 ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const refreshBtn = document.getElementById('refreshBtn');
  const teamSearch = document.getElementById('teamSearch');
  const logoutBtn = document.getElementById('logoutBtn');

  if (refreshBtn) refreshBtn.addEventListener('click', loadDashboard);
  if (teamSearch) teamSearch.addEventListener('input', filterTable);
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      if (window.roleSwitcher) {
        window.roleSwitcher.handleLogout();
      }
    });
  }

  // Auto-check login state on load
  checkTeacherState();
});

function checkTeacherState() {
  const token = localStorage.getItem('teacherToken');
  const username = localStorage.getItem('teacherUsername');
  if (token && username) {
    const welcomeEl = document.getElementById('teacherWelcome');
    const logoutBtn = document.getElementById('logoutBtn');
    if (welcomeEl) welcomeEl.textContent = `你好, ${username}`;
    if (logoutBtn) logoutBtn.style.display = 'inline-block';
  }
}

// ── 加载看板数据 ────────────────────────────────────
async function loadDashboard() {
  const token = localStorage.getItem('teacherToken');
  if (!token) return;

  const refreshBtn = document.getElementById('refreshBtn');
  refreshBtn.disabled = true;
  refreshBtn.textContent = '加载中…';
  try {
    const res = await fetch('/api/teacher/dashboard', {
      headers: { 'Authorization': token }
    });
    if (!res.ok) {
      if (res.status === 401) {
        if (window.roleSwitcher) window.roleSwitcher.handleLogout();
        throw new Error('登录已过期，请重新登录');
      }
      throw new Error('请求失败，状态码: ' + res.status);
    }
    const data = await res.json();
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
  const labels = Object.values(TEACHER_SCORE_LABELS);
  const values = Object.keys(TEACHER_SCORE_LABELS).map(k => scores[k] || 5);

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
    tbody.innerHTML = '<tr><td colspan="12" class="loading-hint">暂无团队数据</td></tr>';
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
      <td style="font-family: monospace; color: #94a3b8;">${escHtml(t.session_id)}</td>
      <td>${escHtml(t.current_phase)}</td>
      <td>${t.round_count}</td>
      <td><div class="rule-tags">${ruleTags || '–'}</div></td>
      ${scoreCell(s.pain_point_discovery)}
      ${scoreCell(s.solution_planning)}
      ${scoreCell(s.business_modeling)}
      ${scoreCell(s.resource_leverage)}
      ${scoreCell(s.pitch_expression)}
      <td><span class="score-chip ${avgCls}">${avg}</span></td>
      <td style="min-width: 140px;">
        <button class="btn-primary btn-sm" onclick="showGraphViz('${t.session_id}')" style="margin-bottom: 4px;">图谱</button>
        <button class="btn-primary btn-sm" onclick="showGradingReport('${t.session_id}')" style="margin-bottom: 4px; background-color: #8b5cf6; border-color: #8b5cf6;">批改报告</button>
        <button class="btn-danger btn-sm" onclick="deleteTeam('${t.session_id}', '${t.student_id}')">删除</button>
      </td>
    </tr>`;
  }).join('');
}

async function deleteTeam(sessionId, studentId) {
  if (!confirm(`确定要删除学生 ${studentId} 的项目吗？此操作不可恢复。`)) return;
  const token = localStorage.getItem('teacherToken');
  try {
    const res = await fetch(`/api/session/${sessionId}`, { 
      method: 'DELETE',
      headers: { 'Authorization': token }
    });
    if (!res.ok) {
        if (res.status === 401) {
            if (window.roleSwitcher) window.roleSwitcher.handleLogout();
            throw new Error('登录已过期，请重新登录');
        }
        throw new Error('删除失败');
    }
    alert('删除成功');
    loadDashboard(); // 重新加载数据
  } catch (err) {
    console.error(err);
    alert('删除失败：' + err.message);
  }
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

// ── 知识图谱与超边可视化 ──
function showGraphViz(sessionId) {
  const team = allTeamData.find(t => t.session_id === sessionId);
  if (!team || !team.kb_context) return;
  const kb = team.kb_context;

  const overlay = document.getElementById('graphOverlay');
  overlay.style.display = 'flex';

  const container = document.getElementById('graphCanvas');
  container.innerHTML = '';

  const nodes = [];
  const edges = [];
  
  // 中心节点（代表当前项目）
  nodes.push({ id: 'CURRENT', label: '当前项目\n(' + team.student_id + ')', shape: 'box', color: '#60a5fa' });

  // 渲染检索到的图谱节点
  (kb.retrieved_nodes || []).forEach(n => {
    let nid = n.id || n;
    nodes.push({
      id: nid,
      label: nid,
      title: n.desc || n.description || '',
      shape: 'ellipse',
      color: '#a7f3d0'
    });
    // 与当前项目的直接边
    edges.push({ from: 'CURRENT', to: nid, label: '知识引用', dashes: true });
  });

  // 渲染主图谱关系边
  (kb.retrieved_master_edges || []).forEach(e => {
    edges.push({
      from: e.source,
      to: e.target,
      label: e.relation || '',
      color: '#64748b'
    });
  });

  // 渲染超边（将超边作为一个中心方块，链接多个节点）
  (kb.similar_failures || []).forEach(he => {
    let heId = he.id || 'HE_' + Math.random().toString(36).substr(2, 5);
    nodes.push({
      id: heId,
      label: he.description || heId,
      shape: 'hexagon',
      color: '#fca5a5' // 红色表示谬误或高风险
    });
    edges.push({ from: 'CURRENT', to: heId, label: '匹配超边', color: {color:'#ef4444'} });
    
    if (he.nodes && Array.isArray(he.nodes)) {
      he.nodes.forEach(subN => {
        // 如果图里面没有就加上
        if (!nodes.find(x => x.id === subN)) {
          nodes.push({ id: subN, label: subN, shape: 'dot', size: 10, color: '#fba9a9'});
        }
        edges.push({ from: heId, to: subN, color: '#ef4444' });
      });
    }
  });

  const data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
  const options = {
    physics: { barnesHut: { springLength: 200 } },
    nodes: { font: { size: 12 } },
    edges: { font: { size: 10, align: 'middle' }, arrows: 'to' }
  };
  new vis.Network(container, data, options);
}

document.addEventListener('DOMContentLoaded', () => {
  const closeBtn = document.getElementById('closeGraphBtn');
  if (closeBtn) closeBtn.addEventListener('click', () => {
    document.getElementById('graphOverlay').style.display = 'none';
  });
});

async function showGradingReport(sessionId) {
  const token = localStorage.getItem('teacherToken');
  let overlay = document.getElementById('gradingReportOverlay');
  
  if (!overlay) {
    // If not in HTML due to caching, inject it dynamically!
    const modalHtml = `
      <div class="overlay" id="gradingReportOverlay" style="display: none; position: fixed; inset: 0; background: radial-gradient(ellipse at 60% 40%, #1e3a5f 0%, #0f172a 70%); align-items: center; justify-content: center; z-index: 9999;">
        <div class="setup-card" style="background: #fff; border-radius: 16px; padding: 48px 40px; max-width: 800px; width: 90%; max-height: 85vh; display: flex; flex-direction: column;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <h2 style="margin: 0; color: #1e293b;">📋 批改评价报告</h2>
            <button id="closeGradingReportBtn" class="btn-secondary btn-sm" onclick="document.getElementById('gradingReportOverlay').style.display='none'" style="padding: 4px 12px; background: #e2e8f0; border-radius: 4px; cursor: pointer;">关闭</button>
          </div>
          <div id="gradingReportContent" style="flex: 1; padding: 15px; overflow-y: auto; line-height: 1.6; text-align: left; font-size: 14px; background: #f8fafc; border-radius: 8px; color: #334155;">
            加载中...
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    overlay = document.getElementById('gradingReportOverlay');
  }

  const content = document.getElementById('gradingReportContent');
  
  overlay.style.display = 'flex';
  content.innerHTML = '<div style="text-align:center; padding: 40px; color:#64748b;">加载生成中...</div>';
  
  try {
    const res = await fetch(`/api/teacher/student/${sessionId}/grading_report`, {
      method: 'GET',
      headers: { 'Authorization': token }
    });
    if (!res.ok) {
        throw new Error('获取批改报告失败');
    }
    const data = await res.json();
    renderGradingReport(data, content);
  } catch (err) {
    console.error(err);
    content.innerHTML = `<div style="color:#ef4444; padding:20px;">加载失败: ${err.message}</div>`;
  }
}

function renderGradingReport(data, container) {
  let html = `<div style="margin-bottom: 20px;">
    <h3 style="margin-bottom: 10px; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">👨‍🏫 教师审阅意见 (Instructor Review Notes)</h3>
    <div style="background: #e0f2fe; border-left: 4px solid #0ea5e9; padding: 12px; border-radius: 4px;">
      ${escHtml(data.instructor_review_notes || '无')}
    </div>
  </div>`;

  html += `<div style="margin-bottom: 20px;">
    <h3 style="margin-bottom: 10px; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">📊 评分量表结构 (Rubric Table)</h3>
    <table class="team-table" style="width: 100%; border-collapse: collapse; margin-top: 10px;">
      <thead>
        <tr>
          <th style="padding: 8px; border: 1px solid #cbd5e1; background: #f1f5f9; text-align: left;">维度 (Rubric)</th>
          <th style="padding: 8px; border: 1px solid #cbd5e1; background: #f1f5f9;">得分</th>
          <th style="padding: 8px; border: 1px solid #cbd5e1; background: #f1f5f9; text-align: left;">缺失项 / 细项</th>
        </tr>
      </thead>
      <tbody>`;
  
  (data.rubric_table || []).forEach(r => {
    let missingInfo = (r.missing || []).map(m => `<span style="display:inline-block; background:#fee2e2; color:#ef4444; padding:2px 6px; border-radius:4px; font-size:12px; margin:2px;">${escHtml(m)}</span>`).join('');
    let breakdownInfo = Object.entries(r.breakdown || {}).map(([k, v]) => `<div><span style="color:#64748b;">${escHtml(k)}:</span> ${(v)}</div>`).join('');
    html += `<tr>
        <td style="padding: 8px; border: 1px solid #cbd5e1;"><strong>${escHtml(TEACHER_SCORE_LABELS[r.rubric_id] || r.rubric_id)}</strong></td>
        <td style="padding: 8px; border: 1px solid #cbd5e1; text-align: center;"><strong>${r.score}</strong></td>
        <td style="padding: 8px; border: 1px solid #cbd5e1; font-size:13px;">
          ${missingInfo ? `<div style="margin-bottom:5px;"><strong>缺失:</strong> ${missingInfo}</div>` : ''}
          ${breakdownInfo}
        </td>
      </tr>`;
  });
  html += `</tbody></table></div>`;

  html += `<div style="margin-bottom: 20px;">
    <h3 style="margin-bottom: 10px; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">🕵️ 证据链追溯 (Detailed Evidence Trace)</h3>
    <div style="display: grid; gap: 10px;">`;
  (data.evidence_trace || []).forEach(f => {
    let severityColor = f.severity === 'high' ? '#ef4444' : '#f59e0b';
    html += `<div style="border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; background:#ffffff;">
      <div style="font-weight: bold; margin-bottom: 6px; color: ${severityColor};">
        [${escHtml(f.rule_id)}] ${escHtml(f.name)}
      </div>
      <div style="font-size: 13px; color: #475569; background: #f8fafc; padding: 8px; border-radius: 4px; border-left: 3px solid #cbd5e1;">
        <strong>诊断证据:</strong><br/>
        ${escHtml(f.evidence)}
      </div>
    </div>`;
  });
  if (!(data.evidence_trace || []).length) {
    html += `<div style="color: #94a3b8; font-size: 13px;">暂无发现明显问题...</div>`;
  }
  html += `</div></div>`;

  html += `<div style="margin-bottom: 20px;">
    <h3 style="margin-bottom: 10px; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">💡 修改建议 (Revision Suggestions)</h3>
    <div style="display: grid; gap: 10px;">`;
  (data.revision_suggestions || []).forEach(rs => {
    html += `<div style="border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; background:#ffffff;">
      <div style="font-weight: bold; margin-bottom: 8px; color: #334155;">
        🎯 针对 ${escHtml(TEACHER_SCORE_LABELS[rs.rubric_id] || rs.rubric_id)} 的提升
      </div>
      <div style="display: flex; gap: 10px; font-size: 13px;">
        <div style="flex: 1; min-width: 0; background: #fefce8; border: 1px solid #fef08a; padding: 8px; border-radius: 4px;">
           <div style="font-weight: bold; margin-bottom: 4px; color: #a16207;">短期改进 (24小时)</div>
           ${escHtml(rs.fix_24h)}
        </div>
        <div style="flex: 1; min-width: 0; background: #f0fdf4; border: 1px solid #bbf7d0; padding: 8px; border-radius: 4px;">
           <div style="font-weight: bold; margin-bottom: 4px; color: #15803d;">长期优化 (72小时)</div>
           ${escHtml(rs.fix_72h)}
        </div>
      </div>
    </div>`;
  });
  if (!(data.revision_suggestions || []).length) {
    html += `<div style="color: #94a3b8; font-size: 13px;">暂无修改建议...(请完成更多评测)</div>`;
  }
  html += `</div></div>`;

  container.innerHTML = html;
}

