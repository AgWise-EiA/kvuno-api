let DB_COLUMNS = [{ value: '', label: '— skip —' }];
let COLUMN_ALIASES = {};
fetch('/ui/columns').then(r => r.json()).then(data => {
  (data.columns || []).forEach(c => DB_COLUMNS.push({ value: c, label: c }));
  COLUMN_ALIASES = data.aliases || {};
});

let currentFile = '';
let fileColumns = [];

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const progressWrap = document.getElementById('progress-wrap');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const uploadMsg = document.getElementById('upload-msg');
const mappingCard = document.getElementById('mapping-card');
const mappingRows = document.getElementById('mapping-rows');
const processBtn = document.getElementById('process-btn');
const processMsg = document.getElementById('process-msg');

const msgClasses = {
  error: 'alert alert-danger py-1 px-2 mb-0',
  success: 'alert alert-success py-1 px-2 mb-0',
};

function showMsg(el, text, type) {
  el.textContent = text;
  el.className = (msgClasses[type] || '') + ' mt-2';
  el.classList.remove('d-none');
}
function hideMsg(el) { el.classList.add('d-none'); }
function setLoading(btn, loading) {
  btn.disabled = loading;
  btn.innerHTML = loading
    ? '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Processing...'
    : 'Process file';
}

const maxFileSize = parseInt(document.body.dataset.maxFileSize) || 20 * 1024 * 1024;
const maxFileSizeMB = maxFileSize / (1024 * 1024);

const r = new Resumable({
  target: '/ui/upload/resumable',
  query: {},
  fileType: ['rds', 'parquet'],
  maxFileSize: maxFileSize,
  chunkSize: 2 * 1024 * 1024,
  simultaneousUploads: 3,
  testChunks: true,
  throttleProgressCallbacks: 1,
  maxFileSizeErrorCallback(file) {
    showMsg(uploadMsg, file.fileName + ' is too large — max ' + maxFileSizeMB + ' MB.', 'error');
  },
  fileTypeErrorCallback(file) {
    showMsg(uploadMsg, 'Only .rds and .parquet files are supported.', 'error');
  },
  maxFilesErrorCallback(files) {
    showMsg(uploadMsg, 'Only one file at a time.', 'error');
  },
});

r.assignDrop(dropZone);
r.assignBrowse(fileInput);

r.on('fileAdded', function (file) {
  hideMsg(uploadMsg);
  const ext = file.fileName.split('.').pop().toLowerCase();
  if (!['rds', 'parquet'].includes(ext)) {
    showMsg(uploadMsg, 'Only .rds and .parquet files are supported.', 'error');
    return;
  }
  dropZone.classList.remove('border-2', 'border-dashed', 'border-secondary');
  dropZone.classList.add('has-file');
  dropZone.querySelector('div:nth-child(2)').innerHTML =
    '<span class="fw-semibold">' + file.fileName + '</span>';
  progressWrap.classList.remove('d-none');
  progressFill.style.width = '0%';
  progressText.textContent = 'Starting upload…';
  r.upload();
});

r.on('progress', function () {
  const pct = Math.round(r.progress() * 100);
  progressFill.style.width = pct + '%';
  progressText.textContent = pct + '%';
});

r.on('fileSuccess', function (file) {
  progressText.textContent = 'Upload complete — reading columns…';
  fetch('/ui/upload/complete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      identifier: file.uniqueIdentifier,
      totalChunks: file.chunks.length,
      filename: file.fileName,
    }),
  })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        showMsg(uploadMsg, data.error, 'error');
        return;
      }
      currentFile = data.file;
      fileColumns = data.columns || [];
      showMsg(uploadMsg, 'Found ' + fileColumns.length + ' column(s).', 'success');
      renderMapping();
      mappingCard.classList.remove('d-none');
    })
    .catch(err => showMsg(uploadMsg, err.message, 'error'));
});

r.on('fileError', function (file, message) {
  showMsg(uploadMsg, 'Upload error: ' + message, 'error');
});

dropZone.addEventListener('click', () => fileInput.click());

function renderMapping() {
  mappingRows.innerHTML = '';
  fileColumns.forEach(col => {
    const match = DB_COLUMNS.find(c => c.value && c.value.toLowerCase() === col.toLowerCase())
      || (COLUMN_ALIASES[col.toLowerCase()] && DB_COLUMNS.find(c => c.value === COLUMN_ALIASES[col.toLowerCase()]));
    const row = document.createElement('div');
    row.className = 'row g-2 align-items-center mb-2';
    row.innerHTML = `
      <div class="col-auto"><span class="fw-semibold small">${escHtml(col)}</span></div>
      <div class="col-auto text-muted">&rarr;</div>
      <div class="col"><select data-file-col="${escHtml(col)}" class="form-select form-select-sm">
        ${DB_COLUMNS.map(c =>
          `<option value="${c.value}"${match && match.value === c.value ? ' selected' : ''}>${c.label}</option>`
        ).join('')}
      </select></div>
    `;
    mappingRows.appendChild(row);
  });
  processBtn.disabled = false;
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

processBtn.addEventListener('click', async () => {
  hideMsg(processMsg);
  const selects = mappingRows.querySelectorAll('select');
  const columnMap = {};
  selects.forEach(sel => {
    const fileCol = sel.dataset.fileCol;
    const dbCol = sel.value;
    if (dbCol) columnMap[fileCol] = dbCol;
  });

  setLoading(processBtn, true);

  try {
    const res = await fetch('/ui/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: currentFile, column_map: columnMap }),
    });
    const data = await res.json();
    if (!res.ok) {
      showMsg(processMsg, data.error || 'Processing failed', 'error');
      setLoading(processBtn, false);
      return;
    }
    window.location.href = '/ui/jobs#' + encodeURIComponent(data.id || currentFile);
  } catch (err) {
    showMsg(processMsg, err.message, 'error');
    setLoading(processBtn, false);
  }
});
