const REFRESH_MS = 30000;
let lastPayload = null;

function formatNumber(value) {
  return new Intl.NumberFormat('en-US').format(value ?? 0);
}

function formatDate(value) {
  if (!value) return '-';
  return new Date(value).toLocaleString('en-US');
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderMetrics(data) {
  setText('metricCommits', formatNumber(data?.totals?.commits));
  setText('metricBranches', formatNumber(data?.totals?.branches));
  setText('metricAuthors', formatNumber(data?.totals?.authors));
  setText('metricAdditions', formatNumber(data?.totals?.additions));
  setText('metricDeletions', formatNumber(data?.totals?.deletions));
}

function renderBranches(data) {
  const host = document.getElementById('branchesStatus');
  host.innerHTML = '';
  (data.branches || []).forEach(branch => {
    const div = document.createElement('div');
    div.className = 'border rounded p-3';
    div.innerHTML = `
      <div class="d-flex justify-content-between align-items-center">
        <strong>${branch.name}</strong>
        <span class="badge text-bg-primary">${formatNumber(branch.commit_count)} commits</span>
      </div>
      <div class="small text-secondary mt-2">Last head: ${branch.last_head_sha || '-'}</div>
      <div class="small text-secondary">Last commit: ${formatDate(branch.last_commit_date)}</div>
      <div class="small text-secondary">Last sync: ${formatDate(branch.synced_at)}</div>
    `;
    host.appendChild(div);
  });
}

function renderComparisons(data) {
  const host = document.getElementById('comparisons');
  host.innerHTML = '';
  const comparisons = data.comparisons || {};
  Object.keys(comparisons).forEach(key => {
    const item = comparisons[key];
    const div = document.createElement('div');
    div.className = 'border rounded p-3';
    if (item.error) {
      div.innerHTML = `<strong>${key}</strong><div class="text-danger small mt-2">${item.error}</div>`;
    } else {
      const link = item.html_url ? `<a href="${item.html_url}" target="_blank" rel="noreferrer">Open on GitHub</a>` : '';
      div.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
          <strong>${item.base_branch} → ${item.head_branch}</strong>
          <span class="badge text-bg-secondary">${item.status || '-'}</span>
        </div>
        <div class="small mt-2">Ahead: <strong>${formatNumber(item.ahead_by)}</strong> | Behind: <strong>${formatNumber(item.behind_by)}</strong></div>
        <div class="small">Commits in comparison: <strong>${formatNumber(item.total_commits)}</strong></div>
        <div class="small mt-2">${link}</div>
      `;
    }
    host.appendChild(div);
  });
}

function renderRateLimit(data) {
  const rate = data.rate_limit || {};
  setText('rateLimit', rate.limit ?? '-');
  setText('rateRemaining', rate.remaining ?? '-');
  setText('rateUsed', rate.used ?? '-');
  setText('rateResource', rate.resource ?? '-');
  if (rate.reset) {
    setText('rateReset', new Date(Number(rate.reset) * 1000).toLocaleString('en-US'));
  } else {
    setText('rateReset', '-');
  }
}

function isMergeCommit(commit) {
  if (Number(commit.is_merge) === 1) return true;

  const msg = (commit.short_message || commit.message || '').toLowerCase().trim();

  return (
    msg.startsWith('merge branch ') ||
    msg.startsWith('merge pull request ') ||
    msg.startsWith('merge remote-tracking branch ')
  );
}

function renderCommits(data) {
  const host = document.getElementById('commitsTable');
  const filter = (document.getElementById('searchInput').value || '').toLowerCase().trim();
  const typeFilter = document.getElementById('commitTypeFilter')?.value || 'normal';

  host.innerHTML = '';

  (data.recent_commits || [])
    .filter(commit => {
      const isMerge = isMergeCommit(commit);

      if (typeFilter === 'normal' && isMerge) {
        return false;
      }

      if (typeFilter === 'merge' && !isMerge) {
        return false;
      }

      if (!filter) {
        return true;
      }

      const text = `${commit.branch || ''} ${commit.author_name || ''} ${commit.short_message || ''} ${commit.message || ''}`.toLowerCase();
      return text.includes(filter);
    })
    .forEach(commit => {
      const isMerge = isMergeCommit(commit);
      const typeBadge = isMerge
        ? '<span class="badge text-bg-warning ms-2">merge</span>'
        : '<span class="badge text-bg-success ms-2">commit</span>';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${formatDate(commit.commit_date)}</td>
        <td><span class="badge text-bg-dark">${commit.branch}</span></td>
        <td>${commit.author_name || '-'}</td>
        <td>
          <a href="${commit.html_url || '#'}" target="_blank" rel="noreferrer">
            ${commit.short_message || '-'}
          </a>
          ${typeBadge}
        </td>
        <td>${formatNumber(commit.changed_files_count)}</td>
        <td>+${formatNumber(commit.additions)} / -${formatNumber(commit.deletions)}</td>
      `;
      host.appendChild(tr);
    });
}

function renderTopFiles(data) {
  const host = document.getElementById('topFiles');
  host.innerHTML = '';
  (data.top_files || []).forEach(file => {
    const div = document.createElement('div');
    div.className = 'border rounded p-2';
    div.innerHTML = `
      <div class="fw-semibold text-break">${file.filename}</div>
      <div class="small text-secondary">${formatNumber(file.times_changed)} changes</div>
      <div class="small text-secondary">+${formatNumber(file.additions)} / -${formatNumber(file.deletions)}</div>
    `;
    host.appendChild(div);
  });
}

function renderDaily(data) {
  const host = document.getElementById('dailyStatsTable');
  host.innerHTML = '';
  (data.daily_stats || []).forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.day}</td>
      <td>${row.branch}</td>
      <td>${formatNumber(row.commits)}</td>
      <td>${formatNumber(row.authors)}</td>
      <td>${formatNumber(row.additions)}</td>
      <td>${formatNumber(row.deletions)}</td>
    `;
    host.appendChild(tr);
  });
}

function renderAll(data) {
  lastPayload = data;
  renderMetrics(data);
  renderBranches(data);
  renderComparisons(data);
  renderRateLimit(data);
  renderCommits(data);
  renderTopFiles(data);
  renderDaily(data);
  setText('lastUpdated', `Updated: ${formatDate(data.generated_at)}`);
}

async function fetchDashboard() {
  const response = await fetch('/api/dashboard');
  const data = await response.json();
  renderAll(data);
}

async function triggerSync() {
  const btn = document.getElementById('syncBtn');
  btn.disabled = true;
  btn.textContent = 'Syncing...';
  try {
    await fetch('/api/sync', { method: 'POST' });
    await fetchDashboard();
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sync now';
  }
}

document.getElementById('syncBtn').addEventListener('click', triggerSync);
document.getElementById('searchInput').addEventListener('input', () => {
  if (lastPayload) renderCommits(lastPayload);
});
document.getElementById('commitTypeFilter').addEventListener('change', () => {
  if (lastPayload) renderCommits(lastPayload);
});
fetchDashboard();
setInterval(fetchDashboard, REFRESH_MS);