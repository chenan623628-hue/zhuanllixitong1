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
  renderFilesPage();
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

let fileListManager = null;

async function renderFilesPage() {
  const content = document.getElementById('page-content');
  if (!content) return;
  
  content.innerHTML = `
    <div class="files-page">
      <div class="page-header">
        <h1 class="page-title">文件管理</h1>
        <div class="page-actions">
          <button class="btn btn-primary" id="refresh-files-btn">
            <span class="btn-icon">🔄</span>
            刷新
          </button>
        </div>
      </div>
      
      <div class="upload-section">
        <div class="card">
          <h3 class="card-title">上传文件</h3>
          <div id="upload-container"></div>
        </div>
      </div>
      
      <div class="file-list-section">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">已上传文件</h3>
            <div class="card-actions">
              <select class="form-select" id="file-type-filter" style="width: auto; min-width: 120px;">
                <option value="">全部类型</option>
                <option value="patent">专利文件</option>
                <option value="standard">标准文件</option>
                <option value="excel_import">Excel导入</option>
              </select>
            </div>
          </div>
          <div id="file-list-container">
            <div class="loading-state">
              <div class="spinner"></div>
              <span>加载中...</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
  
  const uploadContainer = document.getElementById('upload-container');
  const fileListContainer = document.getElementById('file-list-container');
  
  const uploader = new DragDropUploader(uploadContainer, {
    fileType: 'other',
    onUploadComplete: async (file, result) => {
      if (fileListManager) {
        await fileListManager.loadFiles();
        fileListManager.render();
      }
    },
  });
  
  fileListManager = new FileListManager(fileListContainer, {
    onRefresh: () => {},
    onFileDelete: async (fileId) => {
      console.log('File deleted:', fileId);
    },
  });
  
  await fileListManager.loadFiles();
  fileListManager.render();
  
  const refreshBtn = document.getElementById('refresh-files-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = '<span class="spinner"></span> 刷新中...';
      
      await fileListManager.loadFiles();
      fileListManager.render();
      
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = '<span class="btn-icon">🔄</span> 刷新';
    });
  }
  
  const typeFilter = document.getElementById('file-type-filter');
  if (typeFilter) {
    typeFilter.addEventListener('change', async () => {
      const value = typeFilter.value;
      fileListManager.offset = 0;
      fileListManager.options.fileType = value || undefined;
      await fileListManager.loadFiles();
      fileListManager.render();
    });
  }
}
