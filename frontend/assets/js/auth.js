const API_BASE = '/api/v1';

class AuthService {
  constructor() {
    this.accessToken = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
    this.sessionId = localStorage.getItem('session_id');
    this.user = null;
  }

  async login(username, password, deviceName = null) {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username,
        password,
        device_name: deviceName || this.getDeviceName(),
        device_id: this.getDeviceId(),
      }),
    });

    const data = await response.json();
    
    if (data.code === 0 && data.data) {
      if (data.data.status === 'authenticated') {
        this.setTokens(data.data);
        return { success: true, requiresMfa: false };
      } else if (data.data.status === 'challenge_required') {
        return {
          success: false,
          requiresMfa: true,
          challengeId: data.data.challenge_id,
          challengeType: data.data.challenge_type,
          availableFactors: data.data.available_factors,
          user: data.data.user,
        };
      }
    }
    
    return { success: false, error: data.message, code: data.code };
  }

  async verifyChallenge(challengeId, verificationCode) {
    const response = await fetch(`${API_BASE}/auth/challenge/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        challenge_id: challengeId,
        verification_code: verificationCode,
      }),
    });

    const data = await response.json();
    
    if (data.code === 0 && data.data) {
      this.setTokens(data.data);
      return { success: true };
    }
    
    return { success: false, error: data.message, code: data.code };
  }

  async refreshAccessToken() {
    if (!this.refreshToken) {
      return false;
    }

    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          refresh_token: this.refreshToken,
        }),
      });

      const data = await response.json();
      
      if (data.code === 0 && data.data) {
        this.accessToken = data.data.access_token;
        localStorage.setItem('access_token', this.accessToken);
        return true;
      }
    } catch (e) {
      console.error('Token refresh failed:', e);
    }

    this.logout();
    return false;
  }

  async logout() {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.accessToken}`,
        },
      });
    } catch (e) {
      console.error('Logout API call failed:', e);
    }
    
    this.accessToken = null;
    this.refreshToken = null;
    this.sessionId = null;
    this.user = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('session_id');
    localStorage.removeItem('user');
  }

  async getCurrentUser() {
    if (!this.accessToken) {
      return null;
    }

    try {
      const response = await fetch(`${API_BASE}/auth/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
        },
      });

      if (response.status === 401) {
        const refreshed = await this.refreshAccessToken();
        if (refreshed) {
          return this.getCurrentUser();
        }
        return null;
      }

      const data = await response.json();
      
      if (data.code === 0 && data.data) {
        this.user = data.data;
        localStorage.setItem('user', JSON.stringify(this.user));
        return this.user;
      }
    } catch (e) {
      console.error('Get current user failed:', e);
    }

    return null;
  }

  async getCapabilities() {
    const response = await fetch(`${API_BASE}/auth/factors/capabilities`, {
      method: 'GET',
    });
    return await response.json();
  }

  setTokens(data) {
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.sessionId = data.session_id;
    this.user = data.user;

    localStorage.setItem('access_token', this.accessToken);
    localStorage.setItem('refresh_token', this.refreshToken);
    if (this.sessionId) {
      localStorage.setItem('session_id', this.sessionId);
    }
    if (this.user) {
      localStorage.setItem('user', JSON.stringify(this.user));
    }
  }

  isAuthenticated() {
    return !!this.accessToken;
  }

  getToken() {
    return this.accessToken;
  }

  getUser() {
    if (this.user) {
      return this.user;
    }
    const stored = localStorage.getItem('user');
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch (e) {
        return null;
      }
    }
    return null;
  }

  getDeviceId() {
    let deviceId = localStorage.getItem('device_id');
    if (!deviceId) {
      deviceId = 'device_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('device_id', deviceId);
    }
    return deviceId;
  }

  getDeviceName() {
    const browser = this.detectBrowser();
    const os = this.detectOS();
    return `${browser} on ${os}`;
  }

  detectBrowser() {
    const ua = navigator.userAgent;
    if (ua.includes('Firefox')) return 'Firefox';
    if (ua.includes('Chrome')) return 'Chrome';
    if (ua.includes('Safari')) return 'Safari';
    if (ua.includes('Edge')) return 'Edge';
    return 'Browser';
  }

  detectOS() {
    const ua = navigator.userAgent;
    if (ua.includes('Windows')) return 'Windows';
    if (ua.includes('Mac')) return 'macOS';
    if (ua.includes('Linux')) return 'Linux';
    if (ua.includes('Android')) return 'Android';
    if (ua.includes('iPhone') || ua.includes('iPad')) return 'iOS';
    return 'Unknown';
  }

  async _fetch(url, options = {}, autoRefresh = true) {
    const headers = options.headers || {};
    
    if (this.accessToken && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }
    
    let response = await fetch(url, {
      ...options,
      headers,
    });
    
    if (autoRefresh && response.status === 401) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.accessToken}`;
        response = await fetch(url, {
          ...options,
          headers,
        });
      } else {
        this.logout();
        throw new Error('Authentication failed');
      }
    }
    
    return response;
  }

  async fetchJson(url, options = {}, autoRefresh = true) {
    const response = await this._fetch(url, options, autoRefresh);
    
    let data;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      try {
        data = JSON.parse(text);
      } catch (e) {
        data = { code: -1, message: '响应格式错误', data: null };
      }
    }
    
    if (typeof data === 'object' && data !== null) {
      data.success = data.code === 0;
    }
    
    return data;
  }
}

const authService = new AuthService();
