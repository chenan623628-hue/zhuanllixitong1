/**
 * 专利-标准比对系统 V1.0
 * M04 文件上传与安全网关模块 - 前端文件服务
 */

const fileService = {
  async upload(file, options = {}) {
    const formData = new FormData();
    formData.append('file', file);
    
    if (options.fileType) {
      formData.append('file_type', options.fileType);
    }
    if (options.taskId) {
      formData.append('task_id', options.taskId);
    }
    
    const response = await authService.fetchJson('/api/v1/files/upload', {
      method: 'POST',
      body: formData,
    }, false);
    
    return response;
  },
  
  async uploadBatch(files, options = {}) {
    const formData = new FormData();
    
    files.forEach((file, index) => {
      formData.append('files', file);
    });
    
    if (options.fileType) {
      formData.append('file_type', options.fileType);
    }
    if (options.taskId) {
      formData.append('task_id', options.taskId);
    }
    
    const response = await authService.fetchJson('/api/v1/files/upload/batch', {
      method: 'POST',
      body: formData,
    }, false);
    
    return response;
  },
  
  async getFiles(params = {}) {
    const query = new URLSearchParams();
    
    if (params.fileType) query.append('file_type', params.fileType);
    if (params.status) query.append('status', params.status);
    if (params.offset !== undefined) query.append('offset', params.offset);
    if (params.limit !== undefined) query.append('limit', params.limit);
    
    const queryString = query.toString();
    const url = queryString ? `/api/v1/files?${queryString}` : '/api/v1/files';
    
    const response = await authService.fetchJson(url, {
      method: 'GET',
    });
    
    return response;
  },
  
  async getFile(fileId) {
    const response = await authService.fetchJson(`/api/v1/files/${fileId}`, {
      method: 'GET',
    });
    
    return response;
  },
  
  async deleteFile(fileId) {
    const response = await authService.fetchJson(`/api/v1/files/${fileId}`, {
      method: 'DELETE',
    });
    
    return response;
  },
  
  async getUploadLimits() {
    const response = await authService.fetchJson('/api/v1/files/config/limits', {
      method: 'GET',
    });
    
    return response;
  },
  
  async previewExcel(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await authService.fetchJson('/api/v1/files/excel/preview', {
      method: 'POST',
      body: formData,
    }, false);
    
    return response;
  },
  
  async getSecurityEvents(params = {}) {
    const query = new URLSearchParams();
    
    if (params.eventType) query.append('event_type', params.eventType);
    if (params.severity) query.append('severity', params.severity);
    if (params.offset !== undefined) query.append('offset', params.offset);
    if (params.limit !== undefined) query.append('limit', params.limit);
    
    const queryString = query.toString();
    const url = queryString ? `/api/v1/files/security/events?${queryString}` : '/api/v1/files/security/events';
    
    const response = await authService.fetchJson(url, {
      method: 'GET',
    });
    
    return response;
  },
  
  formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },
  
  getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    
    const icons = {
      pdf: '📄',
      doc: '📝',
      docx: '📝',
      xls: '📊',
      xlsx: '📊',
      txt: '📃',
      zip: '📦',
      rar: '📦',
    };
    
    return icons[ext] || '📁';
  },
  
  getStatusBadge(status) {
    const statusMap = {
      pending: { text: '等待中', class: 'badge-info' },
      uploading: { text: '上传中', class: 'badge-info' },
      uploaded: { text: '已上传', class: 'badge-info' },
      processing: { text: '处理中', class: 'badge-warning' },
      ready: { text: '就绪', class: 'badge-success' },
      failed: { text: '失败', class: 'badge-error' },
      blocked: { text: '已阻断', class: 'badge-error' },
    };
    
    return statusMap[status] || { text: status, class: 'badge-info' };
  },
  
  getScanStatusBadge(scanStatus) {
    const statusMap = {
      pending: { text: '待扫描', class: 'badge-info' },
      scanning: { text: '扫描中', class: 'badge-warning' },
      passed: { text: '通过', class: 'badge-success' },
      failed: { text: '失败', class: 'badge-error' },
      blocked: { text: '阻断', class: 'badge-error' },
    };
    
    return statusMap[scanStatus] || { text: scanStatus, class: 'badge-info' };
  },
};


class DragDropUploader {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      maxFiles: options.maxFiles || 10,
      maxSize: options.maxSize || 10 * 1024 * 1024,
      allowedExtensions: options.allowedExtensions || ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt'],
      multiple: options.multiple !== false,
      fileType: options.fileType || 'other',
      onUploadStart: options.onUploadStart || (() => {}),
      onUploadProgress: options.onUploadProgress || (() => {}),
      onUploadComplete: options.onUploadComplete || (() => {}),
      onUploadError: options.onUploadError || (() => {}),
      onFileSelect: options.onFileSelect || (() => {}),
      onFileRemove: options.onFileRemove || (() => {}),
    };
    
    this.files = [];
    this.init();
  }
  
  init() {
    this.createUploadArea();
    this.bindEvents();
  }
  
  createUploadArea() {
    const html = `
      <div class="upload-container">
        <div class="dropzone" id="dropzone">
          <div class="dropzone-icon">📤</div>
          <div class="dropzone-text">
            <p class="dropzone-title">拖拽文件到这里，或</p>
            <p class="dropzone-subtitle">
              <label class="browse-btn">
                <span>选择文件</span>
                <input type="file" id="file-input" ${this.options.multiple ? 'multiple' : ''} style="display: none;">
              </label>
            </p>
          </div>
          <div class="dropzone-hint">
            支持：${this.options.allowedExtensions.join(', ')}
            <span class="separator">|</span>
            最大：${fileService.formatFileSize(this.options.maxSize)}
            <span class="separator">|</span>
            最多：${this.options.maxFiles} 个文件
          </div>
        </div>
        
        <div class="file-list" id="file-list" style="display: none;"></div>
        
        <div class="upload-actions" id="upload-actions" style="display: none;">
          <button type="button" class="btn btn-secondary" id="clear-btn">清空</button>
          <button type="button" class="btn btn-primary" id="upload-btn">
            <span>上传文件</span>
            <span class="upload-spinner" style="display: none;">
              <span class="spinner"></span>
            </span>
          </button>
        </div>
      </div>
    `;
    
    this.element.innerHTML = html;
    
    this.dropzone = this.element.querySelector('#dropzone');
    this.fileInput = this.element.querySelector('#file-input');
    this.fileList = this.element.querySelector('#file-list');
    this.uploadActions = this.element.querySelector('#upload-actions');
    this.clearBtn = this.element.querySelector('#clear-btn');
    this.uploadBtn = this.element.querySelector('#upload-btn');
  }
  
  bindEvents() {
    this.dropzone.addEventListener('dragenter', (e) => this.handleDragEnter(e));
    this.dropzone.addEventListener('dragleave', (e) => this.handleDragLeave(e));
    this.dropzone.addEventListener('dragover', (e) => this.handleDragOver(e));
    this.dropzone.addEventListener('drop', (e) => this.handleDrop(e));
    
    this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
    
    this.clearBtn.addEventListener('click', () => this.clearFiles());
    this.uploadBtn.addEventListener('click', () => this.uploadFiles());
  }
  
  handleDragEnter(e) {
    e.preventDefault();
    e.stopPropagation();
    this.dropzone.classList.add('drag-over');
  }
  
  handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!this.dropzone.contains(e.relatedTarget)) {
      this.dropzone.classList.remove('drag-over');
    }
  }
  
  handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    this.dropzone.classList.add('drag-over');
  }
  
  handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    this.dropzone.classList.remove('drag-over');
    
    const files = Array.from(e.dataTransfer.files);
    this.addFiles(files);
  }
  
  handleFileSelect(e) {
    const files = Array.from(e.target.files);
    this.addFiles(files);
    this.fileInput.value = '';
  }
  
  addFiles(newFiles) {
    const remainingSlots = this.options.maxFiles - this.files.length;
    
    if (remainingSlots <= 0) {
      this.showError(`最多只能上传 ${this.options.maxFiles} 个文件`);
      return;
    }
    
    const filesToAdd = newFiles.slice(0, remainingSlots);
    
    for (const file of filesToAdd) {
      const validation = this.validateFile(file);
      
      if (!validation.valid) {
        this.showError(`${file.name}: ${validation.error}`);
        continue;
      }
      
      this.files.push(file);
      this.options.onFileSelect(file);
    }
    
    this.renderFileList();
    this.updateActions();
  }
  
  validateFile(file) {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!this.options.allowedExtensions.includes(ext)) {
      return {
        valid: false,
        error: `不支持的文件格式，仅支持: ${this.options.allowedExtensions.join(', ')}`
      };
    }
    
    if (file.size > this.options.maxSize) {
      return {
        valid: false,
        error: `文件大小超过限制（最大 ${fileService.formatFileSize(this.options.maxSize)}）`
      };
    }
    
    return { valid: true };
  }
  
  renderFileList() {
    if (this.files.length === 0) {
      this.fileList.style.display = 'none';
      return;
    }
    
    this.fileList.style.display = 'block';
    
    const html = this.files.map((file, index) => `
      <div class="file-item" data-index="${index}">
        <div class="file-icon">${fileService.getFileIcon(file.name)}</div>
        <div class="file-info">
          <div class="file-name">${file.name}</div>
          <div class="file-meta">
            <span class="file-size">${fileService.formatFileSize(file.size)}</span>
            <span class="file-status" id="file-status-${index}">待上传</span>
          </div>
          <div class="file-progress" id="file-progress-${index}" style="display: none;">
            <div class="progress-bar">
              <div class="progress-fill" id="progress-fill-${index}" style="width: 0%"></div>
            </div>
          </div>
        </div>
        <button type="button" class="file-remove-btn" data-index="${index}" title="移除">✕</button>
      </div>
    `).join('');
    
    this.fileList.innerHTML = html;
    
    this.fileList.querySelectorAll('.file-remove-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const index = parseInt(e.currentTarget.dataset.index);
        this.removeFile(index);
      });
    });
  }
  
  removeFile(index) {
    const file = this.files[index];
    this.files.splice(index, 1);
    this.options.onFileRemove(file, index);
    this.renderFileList();
    this.updateActions();
  }
  
  clearFiles() {
    this.files = [];
    this.renderFileList();
    this.updateActions();
  }
  
  updateActions() {
    if (this.files.length > 0) {
      this.uploadActions.style.display = 'flex';
    } else {
      this.uploadActions.style.display = 'none';
    }
  }
  
  async uploadFiles() {
    if (this.files.length === 0) return;
    
    this.setUploading(true);
    this.options.onUploadStart(this.files);
    
    const results = [];
    const errors = [];
    
    for (let i = 0; i < this.files.length; i++) {
      const file = this.files[i];
      
      try {
        this.updateFileStatus(i, '上传中...');
        this.showProgress(i);
        this.updateProgress(i, 30);
        
        const result = await fileService.upload(file, {
          fileType: this.options.fileType,
        });
        
        this.updateProgress(i, 100);
        this.updateFileStatus(i, '上传成功', 'success');
        
        if (result.success) {
          results.push(result.data);
        } else {
          errors.push({ file: file.name, error: result.message || '上传失败' });
        }
        
        this.options.onUploadComplete(file, result);
        
      } catch (error) {
        this.updateFileStatus(i, '上传失败', 'error');
        errors.push({ file: file.name, error: error.message || '上传失败' });
        this.options.onUploadError(file, error);
      }
    }
    
    this.setUploading(false);
    
    if (errors.length === 0) {
      this.options.onUploadComplete(null, { success: true, files: results });
    } else {
      this.options.onUploadError(null, { success: false, files: results, errors });
    }
  }
  
  updateFileStatus(index, text, type = 'info') {
    const statusEl = this.element.querySelector(`#file-status-${index}`);
    if (statusEl) {
      statusEl.textContent = text;
      statusEl.className = `file-status file-status-${type}`;
    }
  }
  
  showProgress(index) {
    const progressEl = this.element.querySelector(`#file-progress-${index}`);
    if (progressEl) {
      progressEl.style.display = 'block';
    }
  }
  
  updateProgress(index, percent) {
    const fillEl = this.element.querySelector(`#progress-fill-${index}`);
    if (fillEl) {
      fillEl.style.width = `${percent}%`;
    }
  }
  
  setUploading(uploading) {
    const btn = this.uploadBtn;
    const text = btn.querySelector('span:first-child');
    const spinner = btn.querySelector('.upload-spinner');
    
    btn.disabled = uploading;
    text.style.display = uploading ? 'none' : 'inline';
    spinner.style.display = uploading ? 'inline-flex' : 'none';
    this.clearBtn.disabled = uploading;
  }
  
  showError(message) {
    console.error('Upload error:', message);
    
    const toast = document.createElement('div');
    toast.className = 'toast toast-error';
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      background: var(--color-error-bg);
      color: var(--color-error);
      border: 1px solid var(--color-error-border);
      border-radius: var(--radius-md);
      z-index: var(--z-tooltip);
      animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.remove();
    }, 5000);
  }
}


class FileListManager {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      fileType: options.fileType,
      onFileSelect: options.onFileSelect || (() => {}),
      onFileDelete: options.onFileDelete || (() => {}),
      onRefresh: options.onRefresh || (() => {}),
    };
    
    this.files = [];
    this.total = 0;
    this.offset = 0;
    this.limit = 50;
  }
  
  async loadFiles(params = {}) {
    const response = await fileService.getFiles({
      fileType: this.options.fileType,
      offset: this.offset,
      limit: this.limit,
      ...params,
    });
    
    if (response.success) {
      this.files = response.data.files || [];
      this.total = response.data.total || 0;
      this.options.onRefresh(this.files, this.total);
    }
    
    return response;
  }
  
  render() {
    if (this.files.length === 0) {
      this.element.innerHTML = this.renderEmpty();
      return;
    }
    
    this.element.innerHTML = `
      <div class="file-table-container">
        <table class="file-table">
          <thead>
            <tr>
              <th style="width: 50px;"></th>
              <th>文件名</th>
              <th style="width: 120px;">大小</th>
              <th style="width: 100px;">状态</th>
              <th style="width: 100px;">扫描</th>
              <th style="width: 180px;">上传时间</th>
              <th style="width: 120px;">操作</th>
            </tr>
          </thead>
          <tbody>
            ${this.files.map(file => this.renderFileRow(file)).join('')}
          </tbody>
        </table>
      </div>
      
      ${this.renderPagination()}
    `;
    
    this.bindTableEvents();
  }
  
  renderFileRow(file) {
    const statusBadge = fileService.getStatusBadge(file.status);
    const scanBadge = file.scan_status ? fileService.getScanStatusBadge(file.scan_status) : null;
    
    return `
      <tr class="file-row" data-file-id="${file.file_id}">
        <td><span class="file-icon-large">${fileService.getFileIcon(file.original_name)}</span></td>
        <td>
          <div class="file-name-cell">
            <span class="file-name-text">${file.original_name}</span>
            ${file.page_count ? `<span class="file-page-count">${file.page_count} 页</span>` : ''}
          </div>
        </td>
        <td>${fileService.formatFileSize(file.file_size)}</td>
        <td><span class="badge ${statusBadge.class}">${statusBadge.text}</span></td>
        <td>${scanBadge ? `<span class="badge ${scanBadge.class}">${scanBadge.text}</span>` : '-'}</td>
        <td>${this.formatDateTime(file.created_at)}</td>
        <td>
          <div class="file-actions-cell">
            <button type="button" class="btn btn-sm btn-text action-download" data-file-id="${file.file_id}" title="下载">
              📥
            </button>
            <button type="button" class="btn btn-sm btn-text action-delete" data-file-id="${file.file_id}" title="删除">
              🗑️
            </button>
          </div>
        </td>
      </tr>
    `;
  }
  
  renderEmpty() {
    return `
      <div class="empty-state">
        <div class="empty-icon">📁</div>
        <h3 class="empty-title">暂无文件</h3>
        <p class="empty-text">您还没有上传任何文件，点击上方按钮开始上传</p>
      </div>
    `;
  }
  
  renderPagination() {
    if (this.total <= this.limit) return '';
    
    const totalPages = Math.ceil(this.total / this.limit);
    const currentPage = Math.floor(this.offset / this.limit) + 1;
    
    return `
      <div class="pagination">
        <button type="button" class="btn btn-sm btn-secondary" data-page="prev" ${currentPage <= 1 ? 'disabled' : ''}>
          上一页
        </button>
        <span class="pagination-info">第 ${currentPage} 页 / 共 ${totalPages} 页</span>
        <button type="button" class="btn btn-sm btn-secondary" data-page="next" ${currentPage >= totalPages ? 'disabled' : ''}>
          下一页
        </button>
      </div>
    `;
  }
  
  bindTableEvents() {
    this.element.querySelectorAll('.action-download').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const fileId = e.currentTarget.dataset.fileId;
        await this.downloadFile(fileId);
      });
    });
    
    this.element.querySelectorAll('.action-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const fileId = e.currentTarget.dataset.fileId;
        if (confirm('确定要删除这个文件吗？')) {
          await this.deleteFile(fileId);
        }
      });
    });
    
    this.element.querySelectorAll('.pagination button[data-page]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const page = e.currentTarget.dataset.page;
        if (page === 'prev') {
          this.offset = Math.max(0, this.offset - this.limit);
        } else if (page === 'next') {
          this.offset += this.limit;
        }
        await this.loadFiles();
        this.render();
      });
    });
  }
  
  async downloadFile(fileId) {
    try {
      const response = await authService._fetch(`/api/v1/files/${fileId}/download`, {
        method: 'GET',
      });
      
      if (!response.ok) {
        throw new Error(`下载失败 (${response.status})`);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `download_${fileId}`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/i);
        if (filenameMatch) {
          try {
            filename = decodeURIComponent(filenameMatch[1]);
          } catch (e) {
            filename = filenameMatch[1];
          }
        } else {
          const simpleMatch = contentDisposition.match(/filename=["']?([^"';\n]+)["']?/i);
          if (simpleMatch) {
            filename = simpleMatch[1];
          }
        }
      }
      
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
      }, 1000);
      
    } catch (error) {
      console.error('文件下载失败:', error);
      alert('下载失败: ' + error.message);
    }
  }
  
  async deleteFile(fileId) {
    const response = await fileService.deleteFile(fileId);
    
    if (response.success) {
      this.options.onFileDelete(fileId);
      await this.loadFiles();
      this.render();
    }
    
    return response;
  }
  
  formatDateTime(dt) {
    if (!dt) return '-';
    
    const date = new Date(dt);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
}
