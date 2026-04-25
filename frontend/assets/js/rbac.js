/**
 * 专利-标准比对系统 V1.0
 * M03 RBAC与权限域模块 - 前端权限服务
 */

const RBAC_API_BASE = '/api/v1/rbac';

class RbacService {
  constructor() {
    this.menus = [];
    this.permissions = [];
    this.userRole = null;
  }

  async getMyMenus() {
    if (!authService.isAuthenticated()) {
      return [];
    }

    try {
      const response = await fetch(`${RBAC_API_BASE}/menus/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authService.accessToken}`,
        },
      });

      if (response.status === 401) {
        const refreshed = await authService.refreshAccessToken();
        if (refreshed) {
          return this.getMyMenus();
        }
        return [];
      }

      const data = await response.json();

      if (data.code === 0 && data.data) {
        this.menus = data.data.menus || [];
        return this.menus;
      }
    } catch (e) {
      console.error('Get menus failed:', e);
    }

    return this.getDefaultMenus();
  }

  async getMyPermissions() {
    if (!authService.isAuthenticated()) {
      return [];
    }

    try {
      const response = await fetch(`${RBAC_API_BASE}/permissions/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authService.accessToken}`,
        },
      });

      if (response.status === 401) {
        const refreshed = await authService.refreshAccessToken();
        if (refreshed) {
          return this.getMyPermissions();
        }
        return [];
      }

      const data = await response.json();

      if (data.code === 0 && data.data) {
        this.permissions = data.data.permissions || [];
        this.userRole = data.data.role;
        return this.permissions;
      }
    } catch (e) {
      console.error('Get permissions failed:', e);
    }

    return [];
  }

  async loadRbacData() {
    const [menus, permissions] = await Promise.all([
      this.getMyMenus(),
      this.getMyPermissions(),
    ]);

    return { menus, permissions, role: this.userRole };
  }

  hasPermission(permissionCode) {
    return this.permissions.includes(permissionCode);
  }

  hasAnyPermission(permissionCodes) {
    return permissionCodes.some(code => this.permissions.includes(code));
  }

  hasAllPermissions(permissionCodes) {
    return permissionCodes.every(code => this.permissions.includes(code));
  }

  isSystemAdmin() {
    return this.userRole === 'system_admin';
  }

  isSecurityAdmin() {
    return this.userRole === 'security_admin';
  }

  isAuditor() {
    return this.userRole === 'auditor';
  }

  isAdmin() {
    return this.isSystemAdmin() || this.isSecurityAdmin();
  }

  canViewAudit() {
    return this.isAuditor();
  }

  canConfigSystem() {
    return this.isSystemAdmin();
  }

  canConfigSecurity() {
    return this.isSecurityAdmin();
  }

  getDefaultMenus() {
    return [
      {
        id: 1,
        name: '首页',
        code: 'dashboard',
        path: '/',
        icon: '🏠',
        sort: 1,
        level: 1,
        children: [],
      },
      {
        id: 2,
        name: '比对中心',
        code: 'compare',
        path: '/compare',
        icon: '🔍',
        sort: 2,
        level: 1,
        children: [],
      },
      {
        id: 3,
        name: '历史记录',
        code: 'history',
        path: '/history',
        icon: '📋',
        sort: 3,
        level: 1,
        children: [],
      },
    ];
  }

  renderMenuItems(menuData, containerElement) {
    if (!menuData || menuData.length === 0) {
      menuData = this.getDefaultMenus();
    }

    let html = '';

    for (const menu of menuData) {
      const hasChildren = menu.children && menu.children.length > 0;
      const isActive = this.isMenuActive(menu);

      if (hasChildren) {
        html += `
          <div class="menu-group">
            <div class="menu-item ${isActive ? 'active' : ''}" data-code="${menu.code}">
              <span class="menu-icon">${menu.icon || '📁'}</span>
              <span class="menu-text">${menu.name}</span>
              <span class="menu-arrow">▼</span>
            </div>
            <div class="menu-children" style="display: ${isActive ? 'block' : 'none'};">
              ${this.renderSubMenuItems(menu.children)}
            </div>
          </div>
        `;
      } else {
        html += `
          <a href="${menu.path || '#'}" class="menu-item ${isActive ? 'active' : ''}" 
             data-code="${menu.code}" data-path="${menu.path || ''}">
            <span class="menu-icon">${menu.icon || '📄'}</span>
            <span class="menu-text">${menu.name}</span>
          </a>
        `;
      }
    }

    containerElement.innerHTML = html;
    this.bindMenuEvents(containerElement);
  }

  renderSubMenuItems(children) {
    if (!children || children.length === 0) {
      return '';
    }

    let html = '';

    for (const menu of children) {
      const isActive = this.isMenuActive(menu);
      html += `
        <a href="${menu.path || '#'}" class="menu-item sub-menu ${isActive ? 'active' : ''}"
           data-code="${menu.code}" data-path="${menu.path || ''}">
          <span class="menu-text">${menu.name}</span>
        </a>
      `;
    }

    return html;
  }

  isMenuActive(menu) {
    const currentPath = window.location.pathname;
    if (menu.path === currentPath) {
      return true;
    }
    if (menu.children && menu.children.some(child => this.isMenuActive(child))) {
      return true;
    }
    return false;
  }

  bindMenuEvents(containerElement) {
    containerElement.querySelectorAll('.menu-group > .menu-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const group = item.closest('.menu-group');
        const children = group.querySelector('.menu-children');
        const arrow = item.querySelector('.menu-arrow');

        if (children.style.display === 'block') {
          children.style.display = 'none';
          arrow.textContent = '▼';
        } else {
          children.style.display = 'block';
          arrow.textContent = '▲';
        }
      });
    });

    containerElement.querySelectorAll('.menu-item[data-path]').forEach(item => {
      item.addEventListener('click', (e) => {
        const path = item.dataset.path;
        if (path && path !== '#') {
          e.preventDefault();
          window.location.href = path;
        }
      });
    });
  }

  renderButtonsWithPermissions(containerElement) {
    const permissionButtons = containerElement.querySelectorAll('[data-permission]');

    permissionButtons.forEach(button => {
      const requiredPermission = button.dataset.permission;
      const hasPermission = this.hasPermission(requiredPermission);

      if (!hasPermission) {
        if (button.dataset.permissionMode === 'disabled') {
          button.disabled = true;
          button.classList.add('disabled');
          button.title = `需要权限：${requiredPermission}`;
        } else {
          button.style.display = 'none';
        }
      }
    });
  }

  checkButtonPermission(buttonElement, permissionCode, mode = 'hide') {
    const hasPermission = this.hasPermission(permissionCode);

    if (!hasPermission) {
      if (mode === 'disabled') {
        buttonElement.disabled = true;
        buttonElement.classList.add('disabled');
        buttonElement.title = `需要权限：${permissionCode}`;
      } else {
        buttonElement.style.display = 'none';
      }
      return false;
    }

    return true;
  }

  clear() {
    this.menus = [];
    this.permissions = [];
    this.userRole = null;
  }
}

const rbacService = new RbacService();
