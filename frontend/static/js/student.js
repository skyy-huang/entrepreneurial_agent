/* ════════════════════════════════════════════════
   student.js — 学生端交互逻辑
   ════════════════════════════════════════════════ */
'use strict';

// ── 状态 ──────────────────────────────────────────
let sessionId = null;
let radarChart = null;
let pendingFile = null;   // 待上传的 File 对象

const PHASE_MAP = {
  value_probe:    { label: '价值探测', cls: '' },
  pressure_test:  { label: '压力测试', cls: 'phase-pressure' },
  landing_check:  { label: '落地校验', cls: 'phase-landing' },
};

const SCORE_LABELS = {
  pain_point_discovery: '痛点发现',
  solution_planning:    '方案策划',
  business_modeling:    '商业建模',
  resource_leverage:    '资源杠杆',
  pitch_expression:     '路演表达',
};

// ── DOM 引用 ──────────────────────────────────────
const overlay        = document.getElementById('overlay');
const appLayout      = document.getElementById('appLayout');
const studentInput   = document.getElementById('studentIdInput');
const startBtn       = document.getElementById('startBtn');
const resumeLink     = document.getElementById('resumeLink');
const resumeArea     = document.getElementById('resumeArea');
const resumeInput    = document.getElementById('resumeInput');
const resumeBtn      = document.getElementById('resumeBtn');
const messagesWrap   = document.getElementById('messagesWrap');
const userInput      = document.getElementById('userInput');
const sendBtn        = document.getElementById('sendBtn');
const sendLabel      = document.getElementById('sendLabel');
const phaseBadge     = document.getElementById('phaseBadge');
const roundCount     = document.getElementById('roundCount');
const sessionInfo    = document.getElementById('sessionInfo');
const fallaciesList  = document.getElementById('fallaciesList');
const fallacyCount   = document.getElementById('fallacyCount');
const taskCard       = document.getElementById('taskCard');
const taskText       = document.getElementById('taskText');
const hypergraphCard = document.getElementById('hypergraphCard');
const hypergraphPre  = document.getElementById('hypergraphPre');
const newSessionBtn  = document.getElementById('newSessionBtn');
// 文件上传相关
const fileInput      = document.getElementById('fileInput');
const uploadLabel    = document.getElementById('uploadLabel');
const fileBadge      = document.getElementById('fileBadge');
const fileBadgeName  = document.getElementById('fileBadgeName');
const fileBadgeRemove = document.getElementById('fileBadgeRemove');
const uploadDropZone = document.getElementById('uploadDropZone');

// ── 入口 ──────────────────────────────────────────
startBtn.addEventListener('click', handleStart);
studentInput.addEventListener('keydown', e => { if (e.key === 'Enter') handleStart(); });
resumeLink.addEventListener('click', e => { e.preventDefault(); resumeArea.classList.toggle('hidden'); });
resumeBtn.addEventListener('click', handleResume);
sendBtn.addEventListener('click', handleSend);
userInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) handleSend();
});
userInput.addEventListener('input', () => {
  updateSendBtn();
});
newSessionBtn.addEventListener('click', () => {
  if (confirm('确定要结束当前会话并重新开始吗？')) {
    sessionId = null;
    location.reload();
  }
});

// ── 文件上传事件 ──────────────────────────────────
fileInput.addEventListener('change', () => {
  if (fileInput.files && fileInput.files[0]) {
    setPendingFile(fileInput.files[0]);
  }
});

fileBadgeRemove.addEventListener('click', () => {
  clearPendingFile();
});

// 拖拽支持（整个 chat-section）
const chatSection = document.querySelector('.chat-section');
chatSection.addEventListener('dragover', e => {
  e.preventDefault();
  if (!sessionId) return;
  uploadDropZone.classList.remove('hidden');
  uploadDropZone.classList.add('drag-over');
});
chatSection.addEventListener('dragleave', e => {
  if (!chatSection.contains(e.relatedTarget)) {
    uploadDropZone.classList.add('hidden');
    uploadDropZone.classList.remove('drag-over');
  }
});
chatSection.addEventListener('drop', e => {
  e.preventDefault();
  uploadDropZone.classList.add('hidden');
  uploadDropZone.classList.remove('drag-over');
  if (!sessionId) return;
  const dt = e.dataTransfer;
  if (dt && dt.files && dt.files[0]) {
    setPendingFile(dt.files[0]);
  }
});
uploadDropZone.addEventListener('click', () => {
  fileInput.click();
});

// ── 文件管理 ──────────────────────────────────────
function setPendingFile(file) {
  const name = file.name.toLowerCase();
  if (!name.endsWith('.pdf') && !name.endsWith('.docx')) {
    showError('仅支持 PDF 或 Word（.docx）文件');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showError('文件过大，请上传 10 MB 以内的文件');
    return;
  }
  pendingFile = file;
  fileBadgeName.textContent = file.name;
  fileBadge.classList.remove('hidden');
  uploadLabel.classList.add('has-file');
  updateSendBtn();
}

function clearPendingFile() {
  pendingFile = null;
  fileInput.value = '';
  fileBadge.classList.add('hidden');
  uploadLabel.classList.remove('has-file');
  updateSendBtn();
}

function updateSendBtn() {
  sendBtn.disabled = !sessionId || (userInput.value.trim().length === 0 && !pendingFile);
}

// ── 开始新会话 ────────────────────────────────────
async function handleStart() {
  const sid = studentInput.value.trim();
  if (!sid) { studentInput.focus(); return; }
  startBtn.disabled = true;
  startBtn.textContent = '正在连接…';
  try {
    const data = await apiPost('/api/session/start', { student_id: sid });
    sessionId = data.session_id;
    showApp(data);
  } catch (err) {
    showError('连接失败：' + err.message);
    startBtn.disabled = false;
    startBtn.textContent = '开始挑战 →';
  }
}

// ── 恢复已有会话 ──────────────────────────────────
async function handleResume() {
  const rid = resumeInput.value.trim();
  if (!rid) return;
  resumeBtn.disabled = true;
  try {
    const data = await apiGet(`/api/session/${rid}`);
    sessionId = rid;
    // 重建历史消息
    showApp({
      session_id: rid,
      welcome_message: null,
      current_phase: data.current_phase,
      round_count: data.round_count,
      capability_scores: data.capability_scores,
    });
    data.messages.forEach(m => appendMessage(m.content, m.role === 'user' ? 'user' : 'assistant'));
    updateFallacies(data.detected_fallacies || []);
    updateHypergraph(data.hypergraph_summary || '');
  } catch (err) {
    showError('恢复失败：' + err.message);
  } finally {
    resumeBtn.disabled = false;
  }
}

// ── 展示主界面 ────────────────────────────────────
function showApp(data) {
  overlay.classList.add('hidden');
  appLayout.classList.remove('hidden');
  sessionInfo.textContent = `ID: ${data.session_id}`;
  updatePhase(data.current_phase);
  roundCount.textContent = data.round_count;
  initRadar(data.capability_scores);
  updateScoresGrid(data.capability_scores);
  updateSendBtn();

  if (data.welcome_message) {
    // 清除默认欢迎节点，添加真实欢迎消息
    messagesWrap.innerHTML = '';
    appendMessage(data.welcome_message, 'assistant');
  }
}

// ── 发送消息（文字 or 文件）────────────────────────
async function handleSend() {
  if (!sessionId) return;

  if (pendingFile) {
    await handleFileUpload();
  } else {
    await handleTextSend();
  }
}

// ── 纯文字发送 ────────────────────────────────────
async function handleTextSend() {
  const msg = userInput.value.trim();
  if (!msg) return;

  appendMessage(msg, 'user');
  userInput.value = '';
  setSending(true, '思考中…');

  const thinking = appendMessage('教练正在思考中…', 'thinking');

  try {
    const data = await apiPost('/api/chat', { session_id: sessionId, message: msg });
    thinking.remove();
    appendMessage(data.coach_response, 'assistant', data.next_task);
    updateAnalytics(data);
  } catch (err) {
    thinking.remove();
    appendMessage('⚠️ 请求失败：' + err.message, 'assistant');
  } finally {
    setSending(false);
  }
}

// ── 文件上传并获取教练回复 ────────────────────────
async function handleFileUpload() {
  const file = pendingFile;
  clearPendingFile();

  appendFileMessage(file.name);
  setSending(true, '解析中…');

  const thinking = appendMessage(`📄 正在解析《${file.name}》，教练准备中…`, 'thinking');

  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `文件上传失败 (HTTP ${res.status})`);
    }
    const data = await res.json();
    thinking.remove();
    // 展示文件摘要（折叠）
    appendFileSummary(file.name, data.file_summary);
    appendMessage(data.coach_response, 'assistant', data.next_task);
    updateAnalytics(data);
  } catch (err) {
    thinking.remove();
    appendMessage('⚠️ 文件处理失败：' + err.message, 'assistant');
  } finally {
    setSending(false);
  }
}

// ── 发送状态管理 ──────────────────────────────────
function setSending(isSending, label) {
  sendBtn.disabled = isSending;
  uploadLabel.style.pointerEvents = isSending ? 'none' : '';
  uploadLabel.style.opacity = isSending ? '0.5' : '';
  if (isSending) {
    sendLabel.textContent = label || '思考中…';
  } else {
    sendLabel.textContent = '发 送';
    updateSendBtn();
  }
}

// ── 消息渲染 ──────────────────────────────────────
function appendMessage(content, role, task) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  if (role === 'assistant' && task) {
    // 分离教练回复和任务部分
    const taskMarker = '【任务】';
    const idx = content.indexOf(taskMarker);
    if (idx !== -1) {
      const mainText = content.slice(0, idx).trim();
      const taskContent = content.slice(idx + taskMarker.length).trim();
      div.innerHTML = `
        <div>${escapeHtml(mainText)}</div>
        <div class="task-inline">📋 任务：${escapeHtml(taskContent)}</div>
      `;
    } else {
      div.textContent = content;
    }
  } else {
    div.textContent = content;
  }

  messagesWrap.appendChild(div);
  messagesWrap.scrollTop = messagesWrap.scrollHeight;
  return div;
}

function appendFileMessage(filename) {
  const div = document.createElement('div');
  div.className = 'message file-upload';
  div.innerHTML = `
    <div class="file-msg-header">
      <span>📎</span>
      <span class="file-msg-name">${escapeHtml(filename)}</span>
    </div>
    <div class="file-msg-body">已上传项目计划书，等待解析…</div>
  `;
  messagesWrap.appendChild(div);
  messagesWrap.scrollTop = messagesWrap.scrollHeight;
  return div;
}

function appendFileSummary(filename, summary) {
  const div = document.createElement('div');
  div.className = 'message assistant';
  const detailId = `summary-${Date.now()}`;
  div.innerHTML = `
    <div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;">
      📄 文件解析完成：<strong>${escapeHtml(filename)}</strong>
    </div>
    <details id="${detailId}">
      <summary style="cursor:pointer;font-size:12px;color:var(--primary);user-select:none;">查看文件摘要 ▶</summary>
      <pre style="margin-top:8px;font-size:11px;color:var(--text-muted);white-space:pre-wrap;word-break:break-word;line-height:1.6;">${escapeHtml(summary)}</pre>
    </details>
  `;
  messagesWrap.appendChild(div);
  messagesWrap.scrollTop = messagesWrap.scrollHeight;
  return div;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/\n/g, '<br>');
}

// ── 分析面板批量更新 ──────────────────────────────
function updateAnalytics(data) {
  updatePhase(data.current_phase);
  roundCount.textContent = data.round_count;
  updateRadar(data.capability_scores);
  updateScoresGrid(data.capability_scores);
  updateFallacies(data.detected_fallacies || []);
  updateTask(data.next_task);
  updateHypergraph(data.hypergraph_summary || '');
}

// ── 阶段更新 ──────────────────────────────────────
function updatePhase(phase) {
  const info = PHASE_MAP[phase] || PHASE_MAP.value_probe;
  phaseBadge.textContent = info.label;
  phaseBadge.className = `phase-badge ${info.cls}`;
}

// ── 漏洞面板 ──────────────────────────────────────
function updateFallacies(fallacies) {
  fallacyCount.textContent = fallacies.length;
  fallacyCount.className = `badge ${fallacies.length === 0 ? 'zero' : ''}`;

  if (fallacies.length === 0) {
    fallaciesList.innerHTML = '<p class="empty-hint">暂未检测到逻辑漏洞</p>';
    return;
  }
  fallaciesList.innerHTML = fallacies.map(f => `
    <div class="fallacy-item ${f.severity || 'medium'}">
      <div class="fallacy-header">
        <span class="fallacy-id">${f.rule_id}</span>
        <span class="fallacy-name">${f.name || ''}</span>
      </div>
      <div style="font-size:11px;color:#94a3b8">${f.description || ''}</div>
      ${f.evidence ? `<div class="fallacy-evidence">「${f.evidence}」</div>` : ''}
    </div>
  `).join('');
}

// ── 任务卡片 ──────────────────────────────────────
function updateTask(task) {
  if (task && task.trim()) {
    taskCard.classList.remove('hidden');
    taskText.textContent = task.trim();
  } else {
    taskCard.classList.add('hidden');
  }
}

// ── 超图摘要 ──────────────────────────────────────
function updateHypergraph(summary) {
  if (summary && summary !== '超图暂无节点（信息尚未提取）') {
    hypergraphCard.classList.remove('hidden');
    hypergraphPre.textContent = summary;
  }
}

// ── 能力评分条 ────────────────────────────────────
function updateScoresGrid(scores) {
  const grid = document.getElementById('scoresGrid');
  grid.innerHTML = Object.entries(scores).map(([key, val]) => `
    <div class="score-item">
      <div class="score-label">${SCORE_LABELS[key] || key}</div>
      <div class="score-bar-wrap">
        <div class="score-bar" style="width:${val * 10}%"></div>
      </div>
      <div class="score-value">${val}</div>
    </div>
  `).join('');
}

// ── 雷达图 ────────────────────────────────────────
function initRadar(scores) {
  const ctx = document.getElementById('radarChart').getContext('2d');
  const labels = Object.values(SCORE_LABELS);
  const values = Object.keys(SCORE_LABELS).map(k => scores[k] || 5);

  radarChart = new Chart(ctx, {
    type: 'radar',
    data: {
      labels,
      datasets: [{
        label: '能力得分',
        data: values,
        backgroundColor: 'rgba(37,99,235,0.2)',
        borderColor: '#2563eb',
        pointBackgroundColor: '#2563eb',
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
      animation: { duration: 400 },
    },
  });
}

function updateRadar(scores) {
  if (!radarChart) { initRadar(scores); return; }
  radarChart.data.datasets[0].data = Object.keys(SCORE_LABELS).map(k => scores[k] || 5);
  radarChart.update('active');
}

// ── HTTP 工具 ─────────────────────────────────────
async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function showError(msg) {
  alert(msg);
}
