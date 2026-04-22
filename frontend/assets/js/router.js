/**
 * 专利-标准比对系统 V1.0
 * M01 工程基线模块 - 路由系统
 */

class Router {
  constructor() {
    this.routes = {};
    this.currentRoute = null;
    this.init();
  }

  init() {
    window.addEventListener('hashchange', () => this.handleRoute());
    window.addEventListener('load', () => this.handleRoute());
  }

  addRoute(path, handler) {
    this.routes[path] = handler;
  }

  handleRoute() {
    const hash = window.location.hash.slice(1) || '/';
    const route = this.routes[hash];
    
    if (route) {
      this.currentRoute = hash;
      route();
      this.updateNavigation();
    } else {
      this.routes['/'] && this.routes['/']();
      this.updateNavigation();
    }
  }

  updateNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
      const href = item.getAttribute('href');
      if (href === window.location.hash || 
          (window.location.hash === '' && href === '#/')) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
  }
}
