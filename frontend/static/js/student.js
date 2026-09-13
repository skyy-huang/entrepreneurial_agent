/* ════════════════════════════════════════════════
   student.js — 学生端交互逻辑
   ════════════════════════════════════════════════ */
'use strict';

// ── 状态 ──────────────────────────────────────────
let sessionId = null;
let radarChart = null;

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
const overlay       = document.getElementById('overlay');
const appLayout     = document.getElementById('appLayout');
const studentInput  = document.getElementById('studentIdInput');  const studentPwdInput = document.getElementById('studentPasswordInput');const startBtn      = document.getElementById('startBtn');
const resumeLink    = document.getElementById('resumeLink');
const resumeArea    = document.getElementById('resumeArea');
const resumeInput   = document.getElementById('resumeInput');
const resumeBtn     = document.getElementById('resumeBtn');
const messagesWrap  = document.getElementById('messagesWrap');
const userInput     = document.getElementById('userInput');
const sendBtn       = document.getElementById('sendBtn');
const sendLabel     = document.getElementById('sendLabel');
const phaseBadge    = document.getElementById('phaseBadge');
const roundCount    = document.getElementById('roundCount');
const sessionInfo   = document.getElementById('sessionInfo');
const fallaciesList = document.getElementById('fallaciesList');
const fallacyCount  = document.getElementById('fallacyCount');
const taskCard      = document.getElementById('taskCard');
const taskText      = document.getElementById('taskText');
const hypergraphCard = document.getElementById('hypergraphCard');
const hypergraphPre  = document.getElementById('hypergraphPre');
const historySidebar = document.getElementById('historySidebar');
const historyList   = document.getElementById('historyList');
const newSessionSidebarBtn = document.getElementById('newSessionSidebarBtn');
const newSessionBtn  = document.getElementById('newSessionBtn');
const uploadBtn      = document.getElementById('uploadBtn');
const fileUpload     = document.getElementById('fileUpload');
const filePreview    = document.getElementById('filePreview');
const fileNameDisp   = document.getElementById('fileName');
const removeFileBtn  = document.getElementById('removeFileBtn');
const competitionBtn = document.getElementById('competitionBtn');
const financialBtn   = document.getElementById('financialBtn');

let currentFile = null;
let sessionHistoryData = [];

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
  sendBtn.disabled = userInput.value.trim().length === 0 && !currentFile;
  if (competitionBtn) competitionBtn.disabled = userInput.value.trim().length === 0;    if (financialBtn) financialBtn.disabled = userInput.value.trim().length === 0 && !currentFile;
});
newSessionBtn.addEventListener('click', () => {
  if (confirm('确定要结束当前会话并重新开始吗？')) {
    sessionId = null;
    location.reload();
  }
});
uploadBtn.addEventListener('click', () => {
  fileUpload.click();
});
if (competitionBtn) {
  competitionBtn.addEventListener('click', handleCompetition);
}
  if (financialBtn) {
    financialBtn.addEventListener('click', handleFinancialAnalysis);
  }
fileUpload.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  currentFile = file;
  
  // Format Size
  let sizeText = '';
  if (file.size > 1024 * 1024) {
     sizeText = (file.size / 1024 / 1024).toFixed(2) + ' MB';
  } else {
     sizeText = (file.size / 1024).toFixed(2) + ' KB';
  }

  // Determine Ext & Icon color
  const ext = file.name.split('.').pop().toLowerCase();
  let iconColor = '#ef4444';
  let extLabel = 'PDF';
  if (ext === 'doc' || ext === 'docx') { iconColor = '#3b82f6'; extLabel = 'DOC'; }
  if (ext === 'txt') { iconColor = '#10b981'; extLabel = 'TXT'; }

  document.getElementById('fileName').textContent = file.name;
  document.getElementById('fileSizeHint').textContent = `${extLabel} · ${sizeText}`;
  
  const fileIconBox = document.getElementById('fileIconBox');
  if(fileIconBox) {
    fileIconBox.style.background = iconColor;
    fileIconBox.textContent = extLabel;
  }

  filePreview.style.display = 'flex';
  sendBtn.disabled = false;
    if (financialBtn) financialBtn.disabled = false;
    if (competitionBtn) competitionBtn.disabled = true;
    if (financialBtn) financialBtn.disabled = false;
    if (competitionBtn) competitionBtn.disabled = true;
});
if (newSessionSidebarBtn) {
  newSessionSidebarBtn.addEventListener('click', handleCreateNewSession);
}
removeFileBtn.addEventListener('click', (e) => {
  e.preventDefault();
  currentFile = null;
  fileUpload.value = '';
  filePreview.style.display = 'none';
  sendBtn.disabled = userInput.value.trim().length === 0;    if (financialBtn) financialBtn.disabled = userInput.value.trim().length === 0;
});

// ── 开始新会话 ────────────────────────────────────
async function handleStart() {
  const sid = studentInput.value.trim();
  const pwd = studentPwdInput ? studentPwdInput.value.trim() : '';
  if (!sid) { studentInput.focus(); return; }
  if (!pwd) { alert('请输入密码（首次使用将自动注册）'); studentPwdInput?.focus(); return; }
  startBtn.disabled = true;
  startBtn.textContent = '正在连接…';
  try {
    const data = await apiPost('/api/student/login', { student_id: sid, password: pwd });
    sessionHistoryData = data.history || [];
    renderHistorySidebar();
    
    if (sessionHistoryData.length > 0) {
      await resumeSession(sessionHistoryData[0].session_id);
    } else {
      await handleCreateNewSession();
    }
  } catch (err) {
    showError('登录失败：' + err.message);
    startBtn.disabled = false;
    startBtn.textContent = '开始挑战 →';
  }
}

async function handleCreateNewSession() {
  const sid = studentInput.value.trim();
  const pwd = studentPwdInput ? studentPwdInput.value.trim() : '';
  newSessionSidebarBtn.disabled = true;
  newSessionSidebarBtn.textContent = '创建中...';
  try {
    const data = await apiPost('/api/session/start', { student_id: sid, password: pwd });
    sessionId = data.session_id;
    // Prepend to history locally
    sessionHistoryData.unshift({
      session_id: sessionId,
      current_phase: data.current_phase || 'value_probe',
      round_count: data.round_count || 0,
      messages: 1
    });
    renderHistorySidebar();
    showApp(data);
  } catch (err) {
    showError('新建会话失败：' + err.message);
  } finally {
    newSessionSidebarBtn.disabled = false;
    newSessionSidebarBtn.textContent = '+ 新建会话';
  }
}

function renderHistorySidebar() {
  if (historySidebar) historySidebar.style.display = 'flex';
  if (!historyList) return;
  
  // 过滤掉轮次为0的会话，除非它是当前正在进行的会话
  sessionHistoryData = sessionHistoryData.filter(h => h.round_count > 0 || h.session_id === sessionId);

  historyList.innerHTML = sessionHistoryData.map(h => {
    return `<div class="history-item ${h.session_id === sessionId ? 'active' : ''}" onclick="resumeSession('${h.session_id}')">
              <div class="hi-title">项目 ${h.session_id}</div>
              <div class="hi-meta">阶段: ${h.current_phase} · 轮次: ${h.round_count}</div>
            </div>`;
  }).join('');
}

// ── 恢复已有会话 ──────────────────────────────────
async function handleResume() {
  const rid = resumeInput.value.trim();
  if (!rid) return;
  resumeBtn.disabled = true;
  await resumeSession(rid);
  resumeBtn.disabled = false;
}

async function resumeSession(rid) {
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
    if (typeof updateKgLogs === 'function') updateKgLogs(data.kb_context || {});
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
  sendBtn.disabled = false;

  messagesWrap.innerHTML = ''; // 全局清理聊天记录窗口
  updateFallacies([]);
  updateHypergraph('');

  if (data.welcome_message) {
    // 清除默认欢迎节点，添加真实欢迎消息
    messagesWrap.innerHTML = '';
    appendMessage(data.welcome_message, 'assistant');
  }
}

// ── 发送消息 ──────────────────────────────────────
async function handleSend() {
  const msg = userInput.value.trim();
  if ((!msg && !currentFile) || !sessionId) return;

  let displayMsg = msg;
  if (currentFile) {
    let sizeText = currentFile.size > 1024 * 1024 ? 
                   (currentFile.size / 1024 / 1024).toFixed(2) + ' MB' : 
                   (currentFile.size / 1024).toFixed(2) + ' KB';
    displayMsg = `[FILE: ${currentFile.name}|${sizeText}]\n${msg}`;
  }

  appendMessage(displayMsg, 'user');
  
  userInput.value = '';
  sendBtn.disabled = true;
  uploadBtn.disabled = true;
  sendLabel.textContent = currentFile ? '阅读并思考中…' : '思考中…';

  const thinking = appendMessage(currentFile ? '教练正在阅读计划书并思考中…' : '教练正在思考中…', 'thinking');

  try {
    const currentMode = document.getElementById('agentModeSelect') ? document.getElementById('agentModeSelect').value : 'coach';
    
    let data;
    if (currentFile) {
      const formData = new FormData();
      formData.append('session_id', sessionId);
      formData.append('file', currentFile);
      formData.append('agent_mode', currentMode);
      if (msg) formData.append('message', msg);
      
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      data = await res.json();
      
      // 清理文件状态
      currentFile = null;
      fileUpload.value = '';
      filePreview.style.display = 'none';
    } else {
      data = await apiPost('/api/chat', { session_id: sessionId, message: msg, agent_mode: currentMode });
    }

    thinking.remove();
    appendMessage(data.coach_response, 'assistant', data.next_task, data.thought_process);
    updatePhase(data.current_phase);
    roundCount.textContent = data.round_count;
    
    // 更新历史记录里的对应状态，保证切换时不会因为 round_count == 0 丢掉
    const hItem = sessionHistoryData.find(h => h.session_id === sessionId);
    if (hItem) {
      hItem.round_count = data.round_count;
      hItem.current_phase = data.current_phase;
      renderHistorySidebar();
    }

    updateRadar(data.capability_scores);
    updateScoresGrid(data.capability_scores);
    updateFallacies(data.detected_fallacies || []);
    updateTask(data.next_task);
    updateHypergraph(data.hypergraph_summary || '');
    if (typeof updateKgLogs === 'function') updateKgLogs(data.kb_context || {});
  } catch (err) {
    thinking.remove();
    appendMessage('⚠️ 请求失败：' + err.message, 'assistant', null, null);
  } finally {
    sendLabel.textContent = '发 送';
    uploadBtn.disabled = false;
    sendBtn.disabled = userInput.value.trim().length === 0 && !currentFile;
  }
}

// ── 提交 IG Form ──────────────────────────────────────
window.submitIGForm = function() {
    const user = document.getElementById('ig_user').value;
    const pain = document.getElementById('ig_pain').value;
    const alt = document.getElementById('ig_alt').value;
    const payer = document.getElementById('ig_payer').value;
    const channel = document.getElementById('ig_channel').value;
    const barrier = document.getElementById('ig_barrier').value;
    const model = document.getElementById('ig_model').value;
    const mvp = document.getElementById('ig_mvp').value;
    
    // Disable inputs
    const container = document.querySelector('.ig-form-card');
    if (container) {
        container.style.opacity = '0.7';
        container.querySelectorAll('input, button').forEach(el => el.disabled = true);
    }

    const combinedMsg = `[信息增益表单提交]
1. 目标客户: ${user || '未填'}
2. 痛点及频率: ${pain || '未填'}
3. 现有替代方案: ${alt || '未填'}
4. 支付方: ${payer || '未填'}
5. 获客渠道: ${channel || '未填'}
6. 核心壁垒: ${barrier || '未填'}
7. 盈利模式: ${model || '未填'}
8. MVP状态: ${mvp || '未填'}`;

    userInput.value = combinedMsg;
    handleSend();
};


// ── 竞赛评审 ──────────────────────────────────────
async function handleFinancialAnalysis() {
  if (!sessionId) return;
  
  const msg = userInput.value.trim();
  if (currentFile || msg) {
      alert("⚠️ 提示：财务分析需要基于您和教练已沟通过的核心商业信息为您诊断（而不是单独处理新文件）。\n\n请先点击右下角的【发送】按钮将资料/文本提交给教练。待教练返回后，再点击此按钮可获得精准的财务模型诊断！");
      return;
  }

  appendMessage(`[请求 💰 财务与市场专项诊断]`, 'user');
  
  if (financialBtn) financialBtn.disabled = true;
  const originalLabel = financialBtn.innerHTML;
  financialBtn.innerHTML = "分析中...";
  
  try {
      const res = await fetch("/api/financial-analysis", {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId })
      });
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.detail || data.error || 'Server Error');
      
      // Update the financialCard
      const financialCard = document.getElementById('financialCard');
      const financialContent = document.getElementById('financialContent');
      if (financialCard && financialContent) {
          financialCard.classList.remove('hidden');
          financialContent.innerHTML = marked.parse(data.analysis || data.reply || '');
      }
      
      // Also show briefly in chat
      appendMessage("💰 财务与市场诊断已完成，请查看右侧专属面板！", 'assistant');
      
  } catch (err) {
      console.error(err);
      appendMessage('⚠️ 财务分析失败: ' + err.message, 'assistant');
  } finally {
      if (financialBtn) {
          financialBtn.disabled = false;
          financialBtn.innerHTML = originalLabel;
      }
  }
}


async function handleCompetition() {
  const msg = userInput.value.trim();
  if (!msg || !sessionId) return;

  if (currentFile) {
      alert("竞赛盲打分模式目前仅支持纯文本分析，请直接将项目内容粘贴在输入框内（暂不支持混合附件）。");
      return;
  }

  appendMessage("[请求 🏆 互联网+ 竞赛盲审测试]\n\n" + msg, 'user');
  
  userInput.value = '';
  sendBtn.disabled = true;
  if(competitionBtn) competitionBtn.disabled = true;
  uploadBtn.disabled = true;
  const originalLabel = competitionBtn.innerHTML;
  competitionBtn.textContent = '评审中…';

  const thinking = appendMessage('竞赛智能体正进行 9 个维度严格盲审打分，请稍候…', 'thinking');

  try {
    const data = await apiPost('/api/competition/score', {
        session_id: sessionId,
        competition_name: "互联网+",
        project_text: msg
    });

    thinking.remove();
    appendMessage(data.coach_response, 'assistant', data.next_task);
    updateTask(data.next_task);
  } catch (err) {
    thinking.remove();
    appendMessage('⚠️ 评审失败：' + err.message, 'assistant');
  } finally {
    competitionBtn.innerHTML = originalLabel;
    uploadBtn.disabled = false;
    const disabled = userInput.value.trim().length === 0;
    sendBtn.disabled = disabled && !currentFile;
    if(competitionBtn) competitionBtn.disabled = disabled;
  }
}

// ── 错误提示 ──────────────────────────────────────
function showError(msg) {
  alert(msg);
}

// ── 消息渲染 ──────────────────────────────────────
function appendMessage(content, role, task, thoughtProcess) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  let htmlContent = '';

  if (role === 'assistant') {
    let mainText = content;
    let taskText = '';
    
    // 寻找任务标识符
    const taskMarkers = ['【任务】', '**任务**', '任务：', '下一步任务：'];
    let taskIdx = -1;
    let matchedMarker = '';
    for (const marker of taskMarkers) {
        taskIdx = content.indexOf(marker);
        if (taskIdx !== -1) {
            matchedMarker = marker;
            break;
        }
    }

    if (taskIdx !== -1) {
       mainText = content.substring(0, taskIdx).trim();
       taskText = content.substring(taskIdx + matchedMarker.length).replace(/^[\*:\s]+/, '').trim();
    }

    // 渲染思维过程折叠面板
    if (thoughtProcess) {
       const thoughtId = 'thought-' + Date.now() + Math.random().toString(36).substr(2, 9);
       htmlContent += `
       <div class="thought-process-container" style="margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; overflow: hidden; background: rgba(0,0,0,0.1);">
         <div class="thought-toggle" style="padding: 8px 12px; font-size: 12px; color: #94a3b8; cursor: pointer; display: flex; align-items: center; justify-content: space-between; background: rgba(0,0,0,0.2);" onclick="document.getElementById('${thoughtId}').style.display = document.getElementById('${thoughtId}').style.display === 'none' ? 'block' : 'none'">
           <span><span style="margin-right: 4px;">🧠</span> 教练的决策与推理过程</span>
           <span style="font-size: 10px;">▼</span>
         </div>
         <div id="${thoughtId}" style="display: none; padding: 12px; font-size: 12px; color: #cbd5e1; border-top: 1px solid rgba(255,255,255,0.05); white-space: pre-wrap; font-family: monospace;">${escapeHtml(thoughtProcess)}</div>
       </div>`;
    }

    let hasIGForm = false;
    let formHtml = '';
    // 处理 IG Form 注入
    if (mainText.includes('[IG_FORM]')) {
        hasIGForm = true;
        mainText = mainText.replace('[IG_FORM]', '');
        formHtml = `
        <div class="ig-form-card" style="background: rgba(30,41,59,0.8); padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid #3b82f6;">
            <div style="display: grid; gap: 8px; font-size: 13px;">
                <input type="text" id="ig_user" placeholder="1. 你的目标用户群是谁？" class="setup-input" style="padding: 8px; box-sizing: border-box;">
                <input type="text" id="ig_pain" placeholder="2. 他们的主要痛点是什么？" class="setup-input" style="padding: 8px; box-sizing: border-box;">
                <input type="text" id="ig_alt" placeholder="3. 现在的替代方案是什么？" class="setup-input" style="padding: 8px; box-sizing: border-box;">
                <input type="text" id="ig_payer" placeholder="4. 谁为你付款？" class="setup-input" style="padding: 8px; box-sizing: border-box;">
                <input type="text" id="ig_channel" placeholder="5. 打算通过什么渠道获客？" class="setup-input" style="padding: 8px; box-sizing: border-box;">
                <input type="text" id="ig_barrier" placeholder="6. 核心壁垒或技术优势是？" class="setup-input" style="padding: 8px; box-sizing: border-box;">
                <input type="text" id="ig_model" placeholder="7. 概括盈利模式/定价？" class="setup-input" style="padding: 8px; box-sizing: border-box;">
                <input type="text" id="ig_mvp" placeholder="8. 当前处于什么状态(想法/MVP/有营收)？" class="setup-input" style="padding: 8px; box-sizing: border-box;">
                <button onclick="window.submitIGForm()" style="margin-top: 8px; padding: 10px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%;">✅ 提交测算并让教练追问致命缺口</button>
            </div>
        </div>
        `;
    }

    // Replace Markdown rendering
    if (typeof marked !== 'undefined') {
       htmlContent += `<div class="markdown-body">${marked.parse(mainText)}</div>`;
    } else {
       htmlContent += `<div>${escapeHtml(mainText)}</div>`;
    }

    if (taskText) {
        if (typeof marked !== 'undefined') {
            htmlContent += `<div class="task-inline">
                <div style="font-weight:bold; margin-bottom:4px;">📋 任务：</div>
                <div class="markdown-body" style="background:transparent; color:inherit; font-size:inherit; padding:0;">${marked.parse(taskText)}</div>
            </div>`;
        } else {
            htmlContent += `<div class="task-inline">📋 任务：${escapeHtml(taskText)}</div>`;
        }
    }

    if (hasIGForm) {
        htmlContent += formHtml;
    }


  } else if (role === 'thinking') {
    htmlContent = escapeHtml(content);
  } else {
    // User message
    let text = content;
        
    // 隐藏系统注入的摘要（避免刷新历史时显示一大坨）
    const summaryIdx = text.indexOf('\n\n[系统摘要只读不回]');
    if (summaryIdx !== -1) {
        text = text.substring(0, summaryIdx);
    }

    const fileMatch = text.match(/^\[FILE:\s*(.+?)\|(.+?)\]\n([\s\S]*)$/);
    if (fileMatch) {
        const fileName = fileMatch[1];
        const fileSize = fileMatch[2];
        const userText = fileMatch[3].trim();
        
        const ext = fileName.split('.').pop().toLowerCase();
        let iconColor = '#ef4444'; // default red for pdf
        let extLabel = 'PDF';
        if (ext === 'doc' || ext === 'docx') { iconColor = '#3b82f6'; extLabel = 'DOC'; }
        if (ext === 'txt') { iconColor = '#10b981'; extLabel = 'TXT'; }

        // 文件卡片独立在蓝色气泡外面，消息文本在蓝色气泡里
        htmlContent = `
          <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
            <div class="chat-file-card" style="display: flex; align-items: center; gap: 12px; background: rgba(30, 41, 59, 0.7); border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; width: fit-content; max-width: 100%;">
                <div style="background: ${iconColor}; color: white; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 13px; flex-shrink: 0;">
                    ${extLabel}
                </div>
                <div style="display: flex; flex-direction: column; overflow: hidden; text-align: left;">
                    <span style="font-size: 14px; color: #f8fafc; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 240px;" title="${fileName}">${fileName}</span>
                    <span style="font-size: 12px; color: #94a3b8; margin-top: 2px;">${extLabel} · ${fileSize}</span>
                </div>
            </div>
            ${userText ? `<div style="background: #2563eb; color: #fff; padding: 12px 16px; border-radius: 12px 12px 0 12px; max-width: 100%; word-break: break-word;">${escapeHtml(userText)}</div>` : ''}
          </div>
        `;
        // 因为我们重新定制了用户消息的结构让卡片悬浮在外，需要去掉默认包裹的容器样式干扰。这里我们直接替换掉div的class
        div.className = `message ${role} custom-file-wrap`;
    } else {
        htmlContent = `<div>${escapeHtml(text)}</div>`;
    }
  }

  div.innerHTML = htmlContent;

  messagesWrap.appendChild(div);
  messagesWrap.scrollTop = messagesWrap.scrollHeight;
  return div;
}

function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
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
    if (typeof marked !== 'undefined') {
      taskText.innerHTML = marked.parse(task.trim());
      taskText.classList.add('markdown-body');
      taskText.style.background = 'transparent';
      taskText.style.padding = '0';
    } else {
      taskText.textContent = task.trim();
    }
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

// ── 图谱调用日志 ──────────────────────────────────
function updateKgLogs(kbContext) {
  const kgLogsList = document.getElementById('kgLogsList');
  if (!kgLogsList) return;
  
  if (!kbContext || (!kbContext.retrieved_nodes?.length && !kbContext.retrieved_hyperedges?.length && !kbContext.similar_failures?.length)) {
    kgLogsList.innerHTML = '<p class="empty-hint" style="color: #64748b; font-style: italic;">尚未触发关联图谱节点的检索...</p>';
    return;
  }
  
  let html = '';
  
  const addLog = (icon, title, items, color) => {
    if (items && items.length > 0) {
      html += `<div style="margin-bottom: 12px; animation: fadeIn 0.5s;">`;
      html += `<div style="color: ${color}; font-weight: bold; margin-bottom: 4px; font-size: 13px;">${icon} ${title}</div>`;
      items.slice(0, 5).forEach(item => {
        let name = item;
        let details = '';
        if (typeof item === 'object') {
            name = item.id || item.name || JSON.stringify(item);
            if (item.source) details = ` <span style="color:#94a3b8; font-size:10px;">(${item.source})</span>`;
        }
        html += `
        <div style="background: rgba(0,0,0,0.2); padding: 6px 8px; border-radius: 4px; border-left: 3px solid ${color}; margin-bottom: 5px; white-space: normal; word-break: break-all; line-height: 1.4;">
          <span style="color: #f8fafc;">${name}</span>${details}
        </div>`;
      });
      html += `</div>`;
    }
  };
  
  html += `<div style="margin-bottom: 12px; font-size: 11px; color: #10b981;">[SYSTEM] 接收到输入特征，唤醒图谱寻路引擎... 已连接... 检索中...</div>`;
  
  addLog('📌', '标杆知识点命中 (Nodes)', kbContext.retrieved_nodes, '#3b82f6');
  addLog('🔗', '关联超边激活 (Edges)', kbContext.retrieved_hyperedges, '#8b5cf6');
  addLog('⚠️', '相似失败演化路径 (Failure Paths)', kbContext.similar_failures, '#ef4444');
  
  html += `<div style="margin-top: 8px; font-size: 11px; color: #10b981;">[SYSTEM] 图谱上下文已注入大模型 prompt...</div>`;
  
  kgLogsList.innerHTML = html;
  
  // 闪烁特效
  kgLogsList.parentElement.style.boxShadow = '0 0 10px rgba(59, 130, 246, 0.5)';
  setTimeout(() => {
     kgLogsList.parentElement.style.boxShadow = '';
  }, 1000);
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
function initRadar(scores) {  if (radarChart) {
    radarChart.destroy();
    radarChart = null;
  }  const ctx = document.getElementById('radarChart').getContext('2d');
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
