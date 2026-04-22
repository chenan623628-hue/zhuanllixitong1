/**
 * 专利-标准比对系统 V1.0
 * M01 工程基线模块 - 应用入口
 */

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
