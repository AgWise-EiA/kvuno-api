var source = new EventSource('/ui/jobs/events');
source.addEventListener('message', function (e) {
  var data = JSON.parse(e.data);
  renderJobs(data.jobs || [], data.counts || {});
  highlightJob();
});

function renderJobs(jobs, counts) {
  var body = document.getElementById('jobs-body');
  if (!body) return;

  if (!jobs.length) {
    body.innerHTML = '<div class="text-center py-5"><p class="text-muted mb-2">No jobs yet.</p><a href="/ui/upload" class="btn btn-outline-primary btn-sm">Upload a file</a></div>';
    return;
  }

  var summary = '<div class="d-flex gap-3 mb-3 small">'
    + '<span><span class="badge bg-success rounded-pill">' + (counts.completed || 0) + '</span> completed</span>'
    + '<span><span class="badge bg-primary rounded-pill">' + (counts.processing || 0) + '</span> processing</span>'
    + '<span><span class="badge bg-danger rounded-pill">' + (counts.error || 0) + '</span> failed</span>'
    + '<span class="text-muted ms-auto">' + jobs.length + ' total</span>'
    + '</div>';

  var rows = jobs.map(function (j) {
    var total = j.total || 1;
    var pct = total > 0 ? Math.round((j.current || 0) / total * 100) : 0;

    var badge = STATUS[j.status] || STATUS.unknown;
    var anim = j.status === 'processing' ? ' progress-bar-striped progress-bar-animated' : '';
    var barW = j.status === 'completed' ? '100' : pct;
    var fmtCur = (j.current || 0).toLocaleString();
    var fmtTot = total.toLocaleString();
    var time = j.mtime ? new Date(j.mtime * 1000).toLocaleString() : '—';
    var name = j.original_name || j.file;

    return '<tr>'
      + '<td><span class="fw-medium small" title="' + escHtml(j.file) + '">' + escHtml(name) + '</span></td>'
      + '<td><span class="badge rounded-pill bg-' + badge.color + '">' + badge.label + '</span></td>'
      + '<td class="text-nowrap small text-muted">' + fmtCur + ' / ' + fmtTot + '</td>'
      + '<td style="min-width:140px;"><div class="progress" style="height:6px;"><div class="progress-bar' + anim + '" role="progressbar" style="width:' + barW + '%;background-color:' + badge.bar + '"></div></div></td>'
      + '<td class="small text-muted">' + escHtml(j.message || '') + '</td>'
      + '<td class="small text-muted text-nowrap">' + time + '</td>'
      + '</tr>';
  }).join('');

  body.innerHTML = summary
    + '<div class="table-responsive"><table class="table table-hover align-middle mb-0">'
    + '<thead class="table-light"><tr><th>File</th><th>Status</th><th>Rows</th><th>Progress</th><th>Message</th><th>Updated</th></tr></thead>'
    + '<tbody>' + rows + '</tbody>'
    + '</table></div>';
}

var STATUS = {
  processing: { color: 'primary',  bar: '#0d6efd', label: 'Processing' },
  completed:  { color: 'success',  bar: '#198754', label: 'Completed' },
  error:      { color: 'danger',   bar: '#dc3545', label: 'Failed' },
  unknown:    { color: 'secondary', bar: '#6c757d', label: 'Pending' },
};

function escHtml(s) {
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function highlightJob() {
  var file = decodeURIComponent(location.hash.slice(1));
  if (!file) return;
  var rows = document.querySelectorAll('#jobs-body tbody tr');
  for (var i = 0; i < rows.length; i++) {
    var first = rows[i].querySelector('td:first-child span');
    if (first && first.textContent.trim() === file) {
      rows[i].classList.add('table-primary');
      rows[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
      break;
    }
  }
}
