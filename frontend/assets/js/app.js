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

const router = new Router();

router.addRoute('/', () => {
  console.log('Home route');
});

router.addRoute('/tasks', () => {
  console.log('Tasks route');
  showPlaceholder('任务管理');
});

router.addRoute('/files', () => {
  console.log('Files route');
  showPlaceholder('文件管理');
});

router.addRoute('/reports', () => {
  console.log('Reports route');
  showPlaceholder('报告中心');
});

router.addRoute('/rules', () => {
  console.log('Rules route');
  showPlaceholder('规则模板');
});

router.addRoute('/terms', () => {
  console.log('Terms route');
  showPlaceholder('术语库');
});

router.addRoute('/admin', () => {
  console.log('Admin route');
  showPlaceholder('系统管理');
});

function showPlaceholder(title) {
  const content = document.getElementById('page-content');
  if (content) {
    content.innerHTML = `
      <div class="placeholder-section">
        <div class="placeholder-icon">🚧</div>
        <h2 class="placeholder-title">${title}</h2>
        <p class="placeholder-text">此模块正在开发中，请稍后查看。</p>
        <div class="placeholder-actions">
          <button class="btn btn-secondary" onclick="window.location.hash='/'">
            返回首页
          </button>
        </div>
      </div>
    `;
  }
}
