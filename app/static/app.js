const $ = (selector) => document.querySelector(selector);
const today = new Date().toISOString().slice(0, 10);
const toolRules = {
  db_delete: {
    description: 'Number of records to delete. More than 100 is blocked; 100 or fewer is allowed and audited.',
  },
  send_email: {
    description: 'Destination email domain. Internal domain: internal.company.com. Any other domain requires human approval.',
  },
  read_file: {
    description: 'File path being accessed. Paths containing confidential are allowed and recorded in the audit trail.',
  },
};

function updateToolHelp() {
  const details = toolRules[$('#tool').value];
  $('#tool-help').innerHTML = `<strong>Policy</strong><p>${details.description}</p>`;
}

function setBusy(button, status, busyText, isBusy) {
  button.disabled = isBusy;
  button.setAttribute('aria-busy', String(isBusy));
  status.textContent = isBusy ? busyText : '';
}

function showDecision(data) {
  const box = $('#decision');
  const icon = data.outcome === 'block' ? '!' : data.outcome === 'require_hitl' ? '!' : '+';
  box.className = `decision ${data.outcome}`;
  box.innerHTML = `<span class="decision-icon">${icon}</span><div><strong>${data.outcome.replaceAll('_', ' ')}</strong><p>${data.reason}${data.review_id ? ` Review ID: ${data.review_id}` : ''}</p></div>`;
  if (data.outcome === 'require_hitl' && data.review_id) {
    $('#review-list').innerHTML = `<article class="review-item"><strong>External action requires approval</strong><p>${data.reason}</p><div class="review-actions"><button type="button" data-review="${data.review_id}" data-action="approve">Approve</button><button type="button" data-review="${data.review_id}" data-action="deny">Deny</button></div><span class="action-status" aria-live="polite"></span></article>`;
    $('#review-count').textContent = '1';
    document.querySelectorAll('[data-review]').forEach((button) => button.addEventListener('click', () => resolveReview(button)));
  }
}

function showProposal(action) {
  $('#proposal').className = 'proposal';
  $('#proposal').innerHTML = `<strong>Gemini proposed</strong><pre>${JSON.stringify(action, null, 2)}</pre><p>Review the proposal, then evaluate it against the active policies.</p>`;
  $('#tool').value = action.tool;
  $('#params').value = JSON.stringify(action.params, null, 2);
  $('#tool-help').innerHTML = '';
}

async function propose(event) {
  event.preventDefault();
  const button = $('#propose-button');
  const status = $('#propose-status');
  setBusy(button, status, 'Gemini is thinking. Please wait...', true);
  try {
    const response = await fetch('/agent/propose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario: $('#scenario').value }),
    });
    const data = await response.json();
    if (!response.ok) {
      $('#proposal').className = 'proposal error';
      $('#proposal').innerHTML = `<strong>Proposal unavailable</strong><p>${data.detail || 'Gemini could not propose an action.'}</p>`;
      return;
    }
    showProposal(data);
  } catch {
    $('#proposal').className = 'proposal error';
    $('#proposal').innerHTML = '<strong>Proposal unavailable</strong><p>Could not reach the server.</p>';
  } finally {
    setBusy(button, status, '', false);
  }
}

async function evaluate(event) {
  event.preventDefault();
  let params;
  try { params = JSON.parse($('#params').value); } catch { showDecision({ outcome: 'block', reason: 'Parameters must be valid JSON.' }); return; }
  const button = $('#evaluate-button');
  const status = $('#evaluate-status');
  setBusy(button, status, 'Checking policies. Please wait...', true);
  try {
    const response = await fetch('/guardrail/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tool: $('#tool').value, params }) });
    const data = await response.json();
    if (!response.ok) { showDecision({ outcome: 'block', reason: data.detail || 'The API could not evaluate this action.' }); return; }
    showDecision(data);
    loadAudit();
  } catch {
    showDecision({ outcome: 'block', reason: 'Could not reach the server.' });
  } finally {
    setBusy(button, status, '', false);
  }
}

async function resolveReview(button) {
  const reviewItem = button.closest('.review-item');
  const status = reviewItem.querySelector('.action-status');
  const buttons = reviewItem.querySelectorAll('button');
  buttons.forEach((item) => { item.disabled = true; });
  button.setAttribute('aria-busy', 'true');
  status.textContent = 'Saving your decision. Please wait...';
  try {
    const response = await fetch(`/guardrail/reviews/${button.dataset.review}/${button.dataset.action}`, { method: 'POST' });
    if (response.ok) {
      reviewItem.remove();
      loadReviews();
      loadAudit();
    } else {
      status.textContent = 'Could not save the decision. Please try again.';
      buttons.forEach((item) => { item.disabled = false; });
    }
  } finally {
    button.removeAttribute('aria-busy');
    if (document.body.contains(reviewItem)) {
      buttons.forEach((item) => { item.disabled = false; });
    }
  }
}

async function loadReviews() {
  // Reviews are returned by the audit API only after an action is evaluated.
  // Keep the console focused on the review created by the latest HITL result.
  const existing = document.querySelector('.review-item');
  $('#review-count').textContent = existing ? '1' : '0';
  if (!existing) {
    $('#review-list').innerHTML = '<div class="blank-state">No pending reviews.</div>';
  }
}

async function loadAudit() {
  const button = $('#refresh-audit');
  button.disabled = true;
  button.textContent = 'Refreshing...';
  const response = await fetch(`/guardrail/audit?date=${today}`);
  if (response.ok) {
    const records = await response.json();
    $('#audit-body').innerHTML = records.length ? records.map((record) => `<tr><td>${new Date(record.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td><td>${record.tool}</td><td class="outcome ${record.outcome}">${record.outcome.replaceAll('_', ' ')}</td><td>${record.matched_rule || '-'}</td><td>${record.executed ? 'yes' : 'no'}</td></tr>`).join('') : '<tr><td colspan="5" class="blank-state">No events loaded.</td></tr>';
  }
  button.disabled = false;
  button.textContent = 'Refresh ->';
}

async function checkHealth() {
  const response = await fetch('/health');
  const data = await response.json();
  $('#status-dot').style.background = data.status === 'ok' ? '#89a936' : '#e0a249';
  $('#status-text').textContent = data.status === 'ok' ? 'Supabase connected' : 'Supabase degraded';
}

$('#evaluate-form').addEventListener('submit', evaluate);
$('#scenario-form').addEventListener('submit', propose);
$('#refresh-audit').addEventListener('click', loadAudit);
$('#tool').addEventListener('change', updateToolHelp);
updateToolHelp();
checkHealth();
loadAudit();