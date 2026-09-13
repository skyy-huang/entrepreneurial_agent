/* ════════════════════════════════════════════════
   role_switcher.js — 学生端/教师端无刷新切换
   ════════════════════════════════════════════════ */
'use strict';

(function () {
  let currentRole = 'student';
  let teacherLoggedIn = false;

  // ── DOM refs ────────────────────────────────────
  const tabStudent  = document.getElementById('tabStudent');
  const tabTeacher  = document.getElementById('tabTeacher');
  const roleSlider  = document.getElementById('roleSlider');
  const studentView = document.getElementById('studentView');
  const teacherView = document.getElementById('teacherView');
  const phaseBadge  = document.getElementById('phaseBadge');
  const roundInfo   = document.getElementById('roundInfoWrap');
  const newSessionBtn = document.getElementById('newSessionBtn');

  // Login overlay elements
  const teacherLoginOverlay = document.getElementById('teacherLoginOverlay');
  const showTeacherLoginBtn = document.getElementById('showTeacherLogin');
  const backToStudentBtn    = document.getElementById('backToStudent');
  const loginSubmitBtn      = document.getElementById('loginSubmitBtn');
  const loginErrorMsg       = document.getElementById('loginErrorMsg');

  // ── Init ─────────────────────────────────────────
  function init() {
    // Tab click handlers
    tabStudent.addEventListener('click', () => switchTo('student'));
    tabTeacher.addEventListener('click', () => switchTo('teacher'));

    // Login overlay from student setup screen
    if (showTeacherLoginBtn) {
      showTeacherLoginBtn.addEventListener('click', (e) => {
        e.preventDefault();
        showTeacherLoginPopup();
      });
    }

    // Back to student from login popup
    if (backToStudentBtn) {
      backToStudentBtn.addEventListener('click', (e) => {
        e.preventDefault();
        hideTeacherLoginPopup();
      });
    }

    // Login submit
    if (loginSubmitBtn) {
      loginSubmitBtn.addEventListener('click', handleTeacherLogin);
    }

    // Check if teacher is already logged in
    const token = localStorage.getItem('teacherToken');
    if (token) {
      teacherLoggedIn = true;
      tabTeacher.classList.add('logged-in');
    }

    // Position slider initially
    positionSlider('student');
  }

  // ── Switch view ────────────────────────────────
  function switchTo(role) {
    if (role === currentRole) return;

    if (role === 'teacher' && !teacherLoggedIn) {
      // Need login first
      showTeacherLoginPopup();
      return;
    }

    currentRole = role;

    // Update tabs
    tabStudent.classList.toggle('active', role === 'student');
    tabTeacher.classList.toggle('active', role === 'teacher');

    // Animate slider
    positionSlider(role);

    // Toggle views with smooth crossfade
    if (role === 'student') {
      teacherView.classList.add('hidden');
      studentView.classList.remove('hidden');
      // Show student-specific topbar items
      if (phaseBadge) phaseBadge.style.display = '';
      if (roundInfo) roundInfo.style.display = '';
      if (newSessionBtn) newSessionBtn.style.display = '';
      document.body.classList.remove('teacher-page');

    } else {
      studentView.classList.add('hidden');
      teacherView.classList.remove('hidden');
      // Hide student-specific topbar items, show teacher stuff
      if (phaseBadge) phaseBadge.style.display = 'none';
      if (roundInfo) roundInfo.style.display = 'none';
      if (newSessionBtn) newSessionBtn.style.display = 'none';
      document.body.classList.add('teacher-page');

      // Trigger teacher data load if available
      if (typeof loadDashboard === 'function') {
        loadDashboard();
      }
    }
  }

  // ── Position the slider pill ───────────────────
  function positionSlider(role) {
    if (!roleSlider) return;
    if (role === 'teacher') {
      roleSlider.style.transform = 'translateX(100%)';
    } else {
      roleSlider.style.transform = 'translateX(0)';
    }
  }

  // ── Teacher login popup ────────────────────────
  function showTeacherLoginPopup() {
    if (teacherLoginOverlay) {
      teacherLoginOverlay.classList.remove('hidden');
    }
  }

  function hideTeacherLoginPopup() {
    if (teacherLoginOverlay) {
      teacherLoginOverlay.classList.add('hidden');
      if (loginErrorMsg) loginErrorMsg.textContent = '';
    }
  }

  async function handleTeacherLogin() {
    const usernameEl = document.getElementById('teacherUsername');
    const passwordEl = document.getElementById('teacherPassword');
    const username = usernameEl ? usernameEl.value.trim() : '';
    const password = passwordEl ? passwordEl.value : '';

    if (!username || !password) {
      if (loginErrorMsg) loginErrorMsg.textContent = '请输入账号和密码';
      return;
    }

    if (loginErrorMsg) loginErrorMsg.textContent = '';
    loginSubmitBtn.disabled = true;
    loginSubmitBtn.textContent = '登录中...';

    try {
      const res = await fetch('/api/teacher/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || '登录失败');
      }

      const data = await res.json();
      localStorage.setItem('teacherToken', data.token);
      localStorage.setItem('teacherUsername', data.username);

      teacherLoggedIn = true;
      tabTeacher.classList.add('logged-in');

      // Update teacher greeting
      const welcomeEl = document.getElementById('teacherWelcome');
      if (welcomeEl) welcomeEl.textContent = `你好, ${data.username}`;
      const logoutBtn = document.getElementById('logoutBtn');
      if (logoutBtn) logoutBtn.style.display = 'inline-block';

      hideTeacherLoginPopup();

      // If the app layout is visible, switch to teacher; otherwise show it
      const appLayout = document.getElementById('appLayout');
      const overlay = document.getElementById('overlay');
      if (appLayout && appLayout.classList.contains('hidden')) {
        // User was on the setup screen — show the app and go teacher
        overlay.classList.add('hidden');
        appLayout.classList.remove('hidden');
      }
      switchTo('teacher');

    } catch (err) {
      if (loginErrorMsg) loginErrorMsg.textContent = err.message;
    } finally {
      loginSubmitBtn.disabled = false;
      loginSubmitBtn.textContent = '登录';
    }
  }

  // ── Expose for teacher.js to call ──────────────
  window.roleSwitcher = {
    switchTo,
    isTeacherLoggedIn: () => teacherLoggedIn,
    handleLogout: function () {
      localStorage.removeItem('teacherToken');
      localStorage.removeItem('teacherUsername');
      teacherLoggedIn = false;
      tabTeacher.classList.remove('logged-in');
      switchTo('student');
      const welcomeEl = document.getElementById('teacherWelcome');
      if (welcomeEl) welcomeEl.textContent = '未登录';
      const logoutBtn = document.getElementById('logoutBtn');
      if (logoutBtn) logoutBtn.style.display = 'none';
    },
  };

  // Init when DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
