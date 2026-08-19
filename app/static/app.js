const $ = (selector) => document.querySelector(selector);
const today = new Date().toISOString().slice(0, 10);
const toolExamples = {
  db_delete: {
    example: { record_count: 500 },
    description: 'Number of records to delete. More than 100 is blocked; 100 or fewer is allowed and audited.',
  },
  send_email: {
    example: { to_domain: 'partner.com' },
    description: 'Destination email domain. Any domain except internal.company.com requires human approval.',
  },
  read_file: {
    example: { path: '/reports/confidential/quarterly.csv' },
    description: 'File path being accessed. Paths containing confidential are allowed and recorded in the audit trail.',
  },
};

function updateToolExample() {
  const details = toolExamples[$('#tool').value];
  $('#params').value = JSON.stringify(details.example, null, 2);
  $('#tool-help').innerHTML = `<strong>Example</strong><code>${JSON.stringify(details.example)}</code><p>${details.description}</p>`;
}

function showDecision(data) {
  const box = $('#decision');
  const icon = data.outcome === 'block' ? '!' : data.outcome === 'require_hitl' ? '!' : '+';
  box.className = `decision ${data.outcome}`;
  box.innerHTML = `<span class="decision-icon">${icon}</span><div><strong>${data.outcome.replaceAll('_', ' ')}</strong><p>${data.reason}${data.review_id ? ` Review ID: ${data.review_id}` : ''}</p></div>`;
  if (data.outcome === 'require_hitl' && data.review_id) {
    $('#review-list').innerHTML = `<article class="review-item"><strong>External action requires approval</strong><p>${data.reason}</p><div class="review-actions"><button type="button" data-review="${data.review_id}" data-action="approve">Approve</button><button type="button" data-review="${data.review_id}" data-action="deny">Deny</button></div></article>`;
    $('#review-count').textContent = '1';
    document.querySelectorAll('[data-review]').forEach((button) => button.addEventListener('click', () => resolveReview(button.dataset.review, button.dataset.action)));
  }
}

async function evaluate(event) {
  event.preventDefault();
  let params;
  try { params = JSON.parse($('#params').value); } catch { showDecision({ outcome: 'block', reason: 'Parameters must be valid JSON.' }); return; }
  const response = await fetch('/guardrail/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tool: $('#tool').value, params }) });
  const data = await response.json();
  if (!response.ok) { showDecision({ outcome: 'block', reason: data.detail || 'The API could not evaluate this action.' }); return; }
  showDecision(data);
  loadAudit();
}

async function resolveReview(id, action) {
  const response = await fetch(`/guardrail/reviews/${id}/${action}`, { method: 'POST' });
  if (response.ok) loadAudit();
  loadReviews();
}

async function loadReviews() {
  // Reviews are returned by the audit API only after an action is evaluated.
  // Keep the console focused on the review created by the latest HITL result.
  const existing = document.querySelector('.review-item');
  $('#review-count').textContent = existing ? '1' : '0';
}

async function loadAudit() {
  const response = await fetch(`/guardrail/audit?date=${today}`);
  if (!response.ok) return;
  const records = await response.json();
  $('#audit-body').innerHTML = records.length ? records.map((record) => `<tr><td>${new Date(record.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td><td>${record.tool}</td><td class="outcome ${record.outcome}">${record.outcome.replaceAll('_', ' ')}</td><td>${record.matched_rule || '-'}</td><td>${record.executed ? 'yes' : 'no'}</td></tr>`).join('') : '<tr><td colspan="5" class="blank-state">No events loaded.</td></tr>';
}

async function checkHealth() {
  const response = await fetch('/health');
  const data = await response.json();
  $('#status-dot').style.background = data.status === 'ok' ? '#89a936' : '#e0a249';
  $('#status-text').textContent = data.status === 'ok' ? 'Supabase connected' : 'Supabase degraded';
}

$('#evaluate-form').addEventListener('submit', evaluate);
$('#refresh-audit').addEventListener('click', loadAudit);
$('#tool').addEventListener('change', updateToolExample);
updateToolExample();
checkHealth();
loadAudit();