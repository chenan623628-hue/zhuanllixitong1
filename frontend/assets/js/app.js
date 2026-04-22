let currentChallengeId = null;
let currentChallengeType = null;
let availableFactors = [];

document.addEventListener('DOMContentLoaded', async () => {
  await checkAuthAndRedirect();
  initLoginForm();
  initMfaForm();
  initLogoutButton();
});

async function checkAuthAndRedirect() {
  const isAuthenticated = authService.isAuthenticated();
  
  if (isAuthenticated) {
    const user = await authService.getCurrentUser();
    if (user) {
      showMainApp(user);
      return;
    }
  }
  
  showLoginPage();
}

function showLoginPage() {
  document.getElementById('login-container').style.display = 'flex';
  document.getElementById('main-container').style.display = 'none';
  document.getElementById('login-form-container').style.display = 'block';
  document.getElementById('mfa-container').style.display = 'none';
  document.getElementById('username').focus();
}

function showMainApp(user) {
  document.getElementById('login-container').style.display = 'none';
  document.getElementById('main-container').style.display = 'block';
  
  if (user) {
    document.getElementById('user-name').textContent = user.username;
    document.getElementById('user-avatar').textContent = user.username.charAt(0).toUpperCase();
    
    if (user.is_admin) {
      document.getElementById('admin-nav').style.display = 'inline-block';
    }
  }
}

function initLoginForm() {
  const loginForm = document.getElementById('login-form');
  const togglePassword = document.getElementById('toggle-password');
  const passwordInput = document.getElementById('password');
  const eyeIcon = document.getElementById('eye-icon');

  togglePassword.addEventListener('click', () => {
    const type = passwordInput.type === 'password' ? 'text' : 'password';
    passwordInput.type = type;
    eyeIcon.textContent = type === 'password' ? '👁️' : '🙈';
  });

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
      showLoginError('请输入用户名和密码');
      return;
    }
    
    setLoginLoading(true);
    hideLoginError();
    
    try {
      const result = await authService.login(username, password);
      
      if (result.success) {
        const user = await authService.getCurrentUser();
        showMainApp(user);
      } else if (result.requiresMfa) {
        currentChallengeId = result.challengeId;
        currentChallengeType = result.challengeType;
        availableFactors = result.availableFactors || [];
        showMfaForm(result.challengeType, result.availableFactors);
      } else {
        showLoginError(result.error || '登录失败');
      }
    } catch (error) {
      showLoginError('网络错误，请稍后重试');
      console.error('Login error:', error);
    } finally {
      setLoginLoading(false);
    }
  });
}

function showMfaForm(challengeType, factors) {
  document.getElementById('login-form-container').style.display = 'none';
  document.getElementById('mfa-container').style.display = 'block';
  
  const subtitle = document.getElementById('mfa-subtitle');
  const codeLabel = document.getElementById('mfa-code-label');
  
  switch (challengeType) {
    case 'totp':
      subtitle.textContent = '请输入身份验证器应用中的 6 位验证码';
      codeLabel.textContent = '动态令牌';
      break;
    case 'sms':
      subtitle.textContent = '验证码已发送至您的手机';
      codeLabel.textContent = '短信验证码';
      break;
    case 'email':
      subtitle.textContent = '验证码已发送至您的邮箱';
      codeLabel.textContent = '邮箱验证码';
      break;
    default:
      subtitle.textContent = '请输入验证码';
      codeLabel.textContent = '验证码';
  }
  
  if (factors && factors.length > 1) {
    showFactorSelector(factors);
  }
  
  clearMfaInputs();
  document.querySelector('.mfa-digit[data-index="0"]').focus();
}

function showFactorSelector(factors) {
  const selector = document.getElementById('mfa-factor-selector');
  selector.style.display = 'flex';
  selector.innerHTML = factors.map(f => `
    <button type="button" class="factor-btn ${f.is_primary ? 'active' : ''}" data-type="${f.type}">
      <span class="factor-name">${f.name}</span>
      ${f.is_primary ? '<span class="factor-badge">默认</span>' : ''}
    </button>
  `).join('');
  
  selector.querySelectorAll('.factor-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      selector.querySelectorAll('.factor-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
}

function initMfaForm() {
  const mfaForm = document.getElementById('mfa-form');
  const backBtn = document.getElementById('back-to-login');
  const digitInputs = document.querySelectorAll('.mfa-digit');

  backBtn.addEventListener('click', () => {
    currentChallengeId = null;
    currentChallengeType = null;
    showLoginPage();
  });

  digitInputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
      const value = e.target.value;
      if (value && index < digitInputs.length - 1) {
        digitInputs[index + 1].focus();
      }
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !e.target.value && index > 0) {
        digitInputs[index - 1].focus();
      }
    });

    input.addEventListener('paste', (e) => {
      e.preventDefault();
      const paste = (e.clipboardData || window.clipboardData).getData('text');
      const digits = paste.replace(/\D/g, '').slice(0, digitInputs.length);
      
      digits.split('').forEach((d, i) => {
        if (digitInputs[i]) {
          digitInputs[i].value = d;
        }
      });
    });
  });

  mfaForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const digits = document.querySelectorAll('.mfa-digit');
    const code = Array.from(digits).map(d => d.value).join('');
    
    if (code.length !== 6) {
      showMfaError('请输入完整的 6 位验证码');
      return;
    }
    
    setMfaLoading(true);
    hideMfaError();
    
    try {
      const result = await authService.verifyChallenge(currentChallengeId, code);
      
      if (result.success) {
        const user = await authService.getCurrentUser();
        showMainApp(user);
      } else {
        showMfaError(result.error || '验证失败');
        clearMfaInputs();
        document.querySelector('.mfa-digit[data-index="0"]').focus();
      }
    } catch (error) {
      showMfaError('网络错误，请稍后重试');
      console.error('MFA verify error:', error);
    } finally {
      setMfaLoading(false);
    }
  });
}

function clearMfaInputs() {
  document.querySelectorAll('.mfa-digit').forEach(d => d.value = '');
}

function showLoginError(message) {
  const errorEl = document.getElementById('login-error');
  const messageEl = document.getElementById('error-message');
  messageEl.textContent = message;
  errorEl.style.display = 'flex';
}

function hideLoginError() {
  document.getElementById('login-error').style.display = 'none';
}

function showMfaError(message) {
  const errorEl = document.getElementById('mfa-error');
  const messageEl = document.getElementById('mfa-error-message');
  messageEl.textContent = message;
  errorEl.style.display = 'flex';
}

function hideMfaError() {
  document.getElementById('mfa-error').style.display = 'none';
}

function setLoginLoading(loading) {
  const btn = document.getElementById('login-btn');
  const text = document.getElementById('login-btn-text');
  const spinner = document.getElementById('login-btn-loading');
  
  btn.disabled = loading;
  text.style.display = loading ? 'none' : 'inline';
  spinner.style.display = loading ? 'inline-block' : 'none';
}

function setMfaLoading(loading) {
  const btn = document.getElementById('mfa-btn');
  const text = document.getElementById('mfa-btn-text');
  const spinner = document.getElementById('mfa-btn-loading');
  
  btn.disabled = loading;
  text.style.display = loading ? 'none' : 'inline';
  spinner.style.display = loading ? 'inline-block' : 'none';
}

function initLogoutButton() {
  const logoutBtn = document.getElementById('logout-btn');
  logoutBtn.addEventListener('click', async () => {
    await authService.logout();
    showLoginPage();
  });
}

function refreshCaptcha() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let captcha = '';
  for (let i = 0; i < 4; i++) {
    captcha += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  document.getElementById('captcha-text').textContent = captcha;
}
