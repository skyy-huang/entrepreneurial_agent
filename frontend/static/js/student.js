'use strict';

const PHASES = { value_probe: '价值探测', pressure_test: '压力测试', landing_check: '落地校验' };
const SCORE_LABELS = { pain_point_discovery: '痛点发现', solution_planning: '方案策划', business_modeling: '商业建模', resource_leverage: '资源杠杆', pitch_expression: '路演表达' };
const FLOW_PROMPTS = { F1: '例如：请解释问题—解决方案匹配，并给我一个正例和反例。', F2: '描述你的项目：谁遇到了什么问题？你打算怎么解决？', F3: '粘贴项目版本或评审材料，系统会按量规指出优点、证据缺口和修改建议。' };
let sessionId = null;
let studentId = '';
let password = '';
let history = [];
let currentFlow = 'F2';
let currentFile = null;
// 记住 F2 的真实阶段名，避免切换到 F1/F3 再切回来时被重置成「价值探测」
let lastPhaseLabel = PHASES.value_probe;
let flowMessages = { F1: [], F2: [], F3: [] };

const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

function showError(message) { $('accessError').textContent = message; }
function api(url, options = {}) {
  const isForm = options.body instanceof FormData;
  const headers = isForm ? { ...(options.headers || {}) } : { 'Content-Type': 'application/json', ...(options.headers || {}) };
  return fetch(url, { ...options, headers }).then(async (response) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `请求失败（${response.status}）`);
    return data;
  });
}
function renderMarkdown(content) {
  if (typeof marked === 'undefined') return `<p>${escapeHtml(content).replace(/\n/g, '<br>')}</p>`;
  const html = marked.parse(String(content ?? ''), { breaks: true, gfm: true });
  return typeof DOMPurify === 'undefined' ? html : DOMPurify.sanitize(html);
}
function saveFlowCache() { if (sessionId) sessionStorage.setItem(`flow-messages-${sessionId}`, JSON.stringify(flowMessages)); }
function loadFlowCache() {
  if (!sessionId) return;
  try { flowMessages = JSON.parse(sessionStorage.getItem(`flow-messages-${sessionId}`)) || { F1: [], F2: [], F3: [] }; }
  catch { flowMessages = { F1: [], F2: [], F3: [] }; }
}
function addMessage(flow, content, role, meta = {}) {
  flowMessages[flow].push({ content: content || '', role, ...meta });
  saveFlowCache();
  if (flow === currentFlow) renderCurrentFlow();
}
function extractFileMessage(message) {
  if (message.fileName) return message;
  const legacy = String(message.content || '').match(/^\[FILE:\s*(.+?)\|(.+?)\]\n([\s\S]*)$/);
  const current = String(message.content || '').match(/^学生上传文件：(.+)\n补充说明：([\s\S]*?)\n\n/);
  if (legacy) return { ...message, fileName: legacy[1], fileSize: legacy[2], content: legacy[3].trim() };
  if (current) return { ...message, fileName: current[1], fileSize: '', content: current[2].trim() };
  return message;
}
function renderFileCard(message) {
  const size = message.fileSize ? ` · ${escapeHtml(String(message.fileSize))}` : '';
  const note = message.content ? `<p class="file-message-note">${escapeHtml(message.content).replace(/\n/g, '<br>')}</p>` : '';
  const extension = String(message.fileName).split('.').pop().slice(0, 4).toUpperCase();
  return `<div class="attachment-card"><div class="attachment-icon">${escapeHtml(extension)}</div><div class="attachment-info"><strong>${escapeHtml(message.fileName)}</strong><span>项目材料${size}</span></div></div>${note}`;
}
function renderCurrentFlow() {
  $('messagesWrap').innerHTML = '';
  const messages = flowMessages[currentFlow] || [];
  if (!messages.length) {
    $('messagesWrap').innerHTML = `<div class="flow-empty"><strong>${currentFlow === 'F1' ? '从一个概念开始' : currentFlow === 'F3' ? '把一版材料放进来' : '从你的真实想法开始'}</strong><p>${FLOW_PROMPTS[currentFlow]}</p></div>`;
    return;
  }
  messages.forEach((rawMessage) => {
    const message = extractFileMessage(rawMessage);
    const item = document.createElement('article');
    item.className = `message message-${message.role === 'user' ? 'user' : 'assistant'}`;
    let content = message.content || '';
    if (message.role === 'user' && content.includes('[系统摘要只读不回]')) content = content.split('[系统摘要只读不回]')[0].trim();
    if (content.length > 5000) content = `${content.slice(0, 5000)}\n\n> 历史消息过长，已折叠未显示的文件摘要。`;
    const body = message.fileName ? renderFileCard({ ...message, content }) : message.role === 'user' ? `<p>${escapeHtml(content).replace(/\n/g, '<br>')}</p>` : renderMarkdown(content);
    item.innerHTML = `<div class="message-role">${message.role === 'user' ? '你' : '原点'}</div><div class="message-body ${message.role === 'user' ? '' : 'markdown-body'}">${body}</div>`;
    $('messagesWrap').appendChild(item);
  });
  $('messagesWrap').scrollTop = $('messagesWrap').scrollHeight;
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
  flowMessages = { F1: [], F2: [], F3: [] };
  history.unshift({ session_id: sessionId, current_phase: data.current_phase, round_count: 0 });
  openWorkspace(data);
}
async function resumeSession(id) {
  try {
    const data = await api(`/api/session/${encodeURIComponent(id)}`);
    sessionId = id;
    loadFlowCache();
    flowMessages.F2 = (data.messages || []).map((message) => extractFileMessage({ content: message.content, role: message.role }));
    openWorkspace({ ...data, welcome_message: null });
  } catch (error) { showError(error.message); }
}
function openWorkspace(data) {
  $('welcomePanel').classList.add('hidden');
  $('workspace').classList.remove('hidden');
  $('sessionInfo').textContent = `ID ${data.session_id}`;
  $('projectTitle').textContent = `项目 ${data.session_id}`;
  if (data.welcome_message && !flowMessages.F2.length) addMessage('F2', data.welcome_message, 'assistant');
  updateState(data);
  renderHistory();
  renderCurrentFlow();
  updateFlowControls();
}
function renderHistory() {
  $('historyList').innerHTML = history.length ? history.map((item) => `<div class="history-item ${item.session_id === sessionId ? 'active' : ''}"><button class="history-open" data-session="${escapeHtml(item.session_id)}"><strong>项目 ${escapeHtml(item.session_id)}</strong><span>${escapeHtml(PHASES[item.current_phase] || item.current_phase || '价值探测')} · ${item.round_count || 0} 轮</span></button><button class="history-delete" data-session="${escapeHtml(item.session_id)}" title="删除项目">×</button></div>`).join('') : '<div class="rail-empty">还没有历史项目。</div>';
  document.querySelectorAll('.history-open').forEach((item) => item.addEventListener('click', () => resumeSession(item.dataset.session)));
  document.querySelectorAll('.history-delete').forEach((item) => item.addEventListener('click', (event) => { event.stopPropagation(); deleteSession(item.dataset.session); }));
}
async function deleteSession(id) {
  if (!window.confirm('删除这个项目？项目对话和诊断记录将一并移除。')) return;
  try {
    await api(`/api/student/session/${encodeURIComponent(id)}`, { method: 'DELETE', body: JSON.stringify({ student_id: studentId, password }) });
    history = history.filter((item) => item.session_id !== id);
    sessionStorage.removeItem(`flow-messages-${id}`);
    if (sessionId === id) { sessionId = null; $('workspace').classList.add('hidden'); $('welcomePanel').classList.remove('hidden'); }
    renderHistory();
  } catch (error) { showError(`删除失败：${error.message}`); }
}
function appendWorkflowResult(data) {
  if (currentFlow === 'F1') {
    const checks = (data.understanding_checks || []).map((item, index) => `${index + 1}. ${item}`).join('\n');
    const judge = (data.how_to_judge || []).map((item) => `- ${item}`).join('\n');
    const pitfalls = (data.common_pitfalls || []).map((item) => `- ${item}`).join('\n');
    const kbNote = data.knowledge_base_hit ? '' : '\n\n> ⚠️ 本地知识库未收录该概念，以上仅为通用拆解路径，不构成该概念的定义。';
    const llmNote = data.llm_enhanced ? `\n\n## 大模型补充（未经核验）\n\n${data.llm_unverified_note || ''}\n\n${data.llm_supplement || ''}` : '';
    addMessage('F1', `# ${data.title}\n\n${data.explanation}${kbNote}\n\n## 判断方法\n${judge}\n\n## 常见误区\n${pitfalls}\n\n## 正例\n${data.positive_example}\n\n## 反例\n${data.negative_example}\n\n## 理解检查\n${checks}\n\n> ${data.source_note}${llmNote}\n\n**运行编号：** ${data.run_id}`, 'assistant');
    return;
  }
  const dimensions = (data.dimensions || []).map((item) => `| ${item.dimension} | ${item.score}/${item.max} | ${item.status} |`).join('\n');
  const gaps = (data.evidence_gaps || []).map((item) => `- ${item}`).join('\n') || '暂无明显缺口，但仍需人工核验来源。';
  const recommendations = (data.recommendations || []).map((item) => `- ${item}`).join('\n');
  const claims = (data.claim_labels || []).slice(0, 8).map((item) => `- **${item.label}** ${item.claim}（${item.can_use_now}）`).join('\n');
  const level = data.quality_level ? `\n\n**质量等级：** ${data.quality_level.level}／4 · ${data.quality_level.name}\n\n> ${data.quality_level.anchor}` : '';
  const risks = (data.integrity_risks || []).length
    ? `\n\n## ⚠️ 诚信风险提示\n${data.integrity_risks.map((item) => `- ${item}`).join('\n')}`
    : '';
  const dist = data.evidence_distribution
    ? `\n\n## 证据分布\n事实 F：${data.evidence_distribution.counts.F} ｜ 推断 I：${data.evidence_distribution.counts.I} ｜ 假设 H：${data.evidence_distribution.counts.H} ｜ 模拟 S：${data.evidence_distribution.counts.S}`
    : '';
  addMessage('F3', `# 评审结果：${data.overall_score}/100${level}\n\n| 维度 | 得分 | 状态 |\n| --- | ---: | --- |\n${dimensions}${dist}${risks}\n\n## 证据缺口\n${gaps}\n\n## 修改建议\n${recommendations}\n\n## 材料边界初筛\n${claims || '暂无可拆分陈述。'}\n\n> ${data.integrity_note || ''}\n\n**运行编号：** ${data.run_id}`, 'assistant');
}
function updateState(data) {
  const phase = PHASES[data.current_phase] || '价值探测';
  lastPhaseLabel = phase;
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
function updateFlowControls() {
  document.querySelectorAll('.flow-tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.flow === currentFlow));
  $('userInput').placeholder = FLOW_PROMPTS[currentFlow];
  // F2 显示真实阶段；F1/F3 显示流程名。不能把 F2 的阶段重置回默认值。
  $('phaseLabel').textContent = currentFlow === 'F1' ? '理论学习' : currentFlow === 'F3' ? '评审反馈' : lastPhaseLabel;
  $('uploadBtn').disabled = currentFlow !== 'F2';
  $('uploadBtn').title = currentFlow === 'F2' ? '上传 PDF、DOCX、DOC 或 TXT' : '文件上传仅用于项目指导流程';
}
async function sendMessage(event) {
  event.preventDefault();
  const input = $('userInput');
  const message = input.value.trim();
  if ((!message && !currentFile) || (currentFlow === 'F2' && !sessionId)) return;
  const file = currentFile;
  // 文件上传只对 F2 生效；其他流程即使残留了文件也按普通文本处理
  const isUpload = currentFlow === 'F2' && !!file;
  if (isUpload) addMessage(currentFlow, message, 'user', { fileName: file.name, fileSize: `${(file.size / 1024).toFixed(1)} KB` });
  else addMessage(currentFlow, message, 'user');
  input.value = '';
  clearSelectedFile();
  $('sendBtn').disabled = true;
  $('sendBtn').innerHTML = currentFlow === 'F2' ? '处理中…' : '评审中…';
  try {
    let data;
    if (isUpload) {
      const form = new FormData();
      form.append('session_id', sessionId);
      form.append('file', file);
      if (message) form.append('message', message);
      data = await api('/api/upload', { method: 'POST', body: form });
    } else if (currentFlow === 'F1') data = await api('/api/learn', { method: 'POST', body: JSON.stringify({ question: message }) });
    else if (currentFlow === 'F3') data = await api('/api/review', { method: 'POST', body: JSON.stringify({ project_text: message }) });
    else data = await api('/api/chat', { method: 'POST', body: JSON.stringify({ session_id: sessionId, message, agent_mode: 'coach' }) });
    // 按「实际调用的接口」决定渲染方式，而不是按当前标签页，避免两个形状串味
    if (isUpload || currentFlow === 'F2') {
      addMessage('F2', data.coach_response, 'assistant');
      updateState(data);
      const item = history.find((entry) => entry.session_id === sessionId);
      if (item) { item.round_count = data.round_count; item.current_phase = data.current_phase; }
      renderHistory();
    } else appendWorkflowResult(data);
  } catch (error) { addMessage(currentFlow, `### 请求未完成\n\n${error.message}`, 'assistant'); }
  finally { $('sendBtn').disabled = false; $('sendBtn').innerHTML = '发送 <span>↗</span>'; input.focus(); }
}

$('accessForm').addEventListener('submit', enterWorkspace);
$('composerForm').addEventListener('submit', sendMessage);
$('userInput').addEventListener('keydown', (event) => {
  if (event.key !== 'Enter' || event.isComposing) return;
  if (event.ctrlKey) return;
  event.preventDefault();
  $('composerForm').requestSubmit();
});
$('newSessionBtn').addEventListener('click', createSession);
$('railNewBtn').addEventListener('click', createSession);
function clearSelectedFile() {
  currentFile = null;
  $('fileUpload').value = '';
  $('fileName').textContent = '';
  $('filePreview').classList.add('hidden');
}
$('uploadBtn').addEventListener('click', () => { if (currentFlow === 'F2') $('fileUpload').click(); });
$('fileUpload').addEventListener('change', (event) => { currentFile = event.target.files[0] || null; $('fileName').textContent = currentFile ? `已选择：${currentFile.name}` : ''; $('filePreview').classList.toggle('hidden', !currentFile); });
$('removeFileBtn').addEventListener('click', clearSelectedFile);
document.querySelectorAll('.flow-tab').forEach((button) => button.addEventListener('click', () => {
  const nextFlow = button.dataset.flow;
  // 切换流程必须清空已选文件：上传只属于 F2，残留会让 F3 收到 F2 形状的响应，
  // 界面上就会渲染出「评审结果：undefined/100」。
  if (nextFlow !== 'F2') clearSelectedFile();
  currentFlow = nextFlow;
  renderCurrentFlow();
  updateFlowControls();
}));
