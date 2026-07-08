let highlightFile = decodeURIComponent(location.hash.slice(1));

async function pollJobs() {
  try {
    const res = await fetch('/ui/jobs/data');
    const data = await res.json();
    const jobs = data.jobs || [];

    const body = document.getElementById('jobs-body');

    if (jobs.length === 0) {
      body.innerHTML = '<div class="text-center py-5"><p class="text-muted mb-2">No jobs yet.</p><a href="/ui/upload" class="btn btn-outline-primary btn-sm">Upload a file</a></div>';
      return;
    }

    const counts = { completed: 0, processing: 0, error: 0, unknown: 0 };
    const rows = jobs.map(j => {
      const pct = j.total > 0 ? Math.round((j.current / j.total) * 100) : 0;
      const badge = statusClass(j.status);
      counts[badge.key] = (counts[badge.key] || 0) + 1;
      const time = j.mtime ? new Date(j.mtime * 1000).toLocaleString() : '—';
      const anim = j.status === 'processing' ? ' progress-bar-striped progress-bar-animated' : '';
      const highlight = j.file === highlightFile ? ' table-primary' : '';
      return `<tr class="${highlight}">
        <td><span class="fw-medium small">${escHtml(j.file)}</span></td>
        <td><span class="badge rounded-pill bg-${badge.color}">${badge.label}</span></td>
        <td class="text-nowrap small text-muted">${j.current.toLocaleString()} / ${j.total.toLocaleString()}</td>
        <td style="min-width:140px;">
          <div class="progress" style="height:6px;">
            <div class="progress-bar${anim}" role="progressbar" style="width:${j.status === 'completed' ? 100 : pct}%; background-color:${badge.bar}" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
        </td>
        <td class="small text-muted">${j.message || ''}</td>
        <td class="small text-muted text-nowrap">${time}</td>
      </tr>`;
    }).join('');

    const total = jobs.length;
    const summary = `<div class="d-flex gap-3 mb-3 small">
      <span><span class="badge bg-success rounded-pill">${counts.completed}</span> completed</span>
      <span><span class="badge bg-primary rounded-pill">${counts.processing}</span> processing</span>
      <span><span class="badge bg-danger rounded-pill">${counts.error}</span> failed</span>
      <span class="text-muted ms-auto">${total} total</span>
    </div>`;

    body.innerHTML = summary + `<div class="table-responsive"><table class="table table-hover align-middle mb-0">
      <thead class="table-light"><tr>
        <th>File</th><th>Status</th><th>Rows</th><th>Progress</th><th>Message</th><th>Updated</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;

    if (highlightFile) {
      const highlighted = body.querySelector('.table-primary');
      if (highlighted) highlighted.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  } catch (_) {
  }
}

const STATUS = {
  processing: { color: 'primary',  bar: '#0d6efd', label: 'Processing', key: 'processing' },
  completed:  { color: 'success',  bar: '#198754', label: 'Completed',  key: 'completed' },
  error:      { color: 'danger',   bar: '#dc3545', label: 'Failed',     key: 'error' },
  unknown:    { color: 'secondary', bar: '#6c757d', label: 'Pending',   key: 'unknown' },
};

function statusClass(s) {
  return STATUS[s] || STATUS.unknown;
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

pollJobs();
setInterval(pollJobs, 3000);
