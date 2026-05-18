let currentData = null;

const $ = (id) => document.getElementById(id);

function badge(text, cls) { return `<span class="badge ${cls}">${text || '-'}</span>`; }
function esc(v) { return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

async function loadData() {
  const res = await fetch('/api/gpt-analysis');
  currentData = await res.json();
  render(currentData);
}

async function runAnalysis() {
  const btn = $('runBtn');
  btn.disabled = true;
  btn.textContent = 'Analizuję...';
  $('statusBox').textContent = 'GPT analizuje mecze. To może potrwać zależnie od liczby typów.';
  try {
    const res = await fetch('/api/gpt-analysis/run', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})
    });
    currentData = await res.json();
    render(currentData);
  } catch (e) {
    $('statusBox').textContent = 'Błąd analizy GPT: ' + e;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Uruchom analizę GPT';
  }
}

function render(data) {
  const rows = data.analyses || [];
  $('generatedAt').textContent = data.generated_at ? `Wygenerowano: ${data.generated_at}` : '';
  $('statusBox').textContent = rows.length ? `Gotowe: ${rows.length} analiz.` : (data.message || 'Brak analiz.');
  const tbody = $('analysisRows');
  tbody.innerHTML = rows.map((r, i) => {
    const decision = String(r.decision || 'SKIP').toUpperCase();
    const risk = String(r.risk || '').toLowerCase();
    return `<tr onclick="showReport(${i})">
      <td><strong>${esc(r.match)}</strong><small>${esc(r.league || '')}</small></td>
      <td>${esc(r.bet)}</td>
      <td>${esc(r.odds || '-')}</td>
      <td>${esc(r.confidence || 0)}%</td>
      <td>${esc(r.value_score || 0)}/10</td>
      <td>${badge(esc(risk || '-'), 'risk-' + risk)}</td>
      <td>${badge(decision, decision === 'PLAY' ? 'play' : 'skip')}</td>
    </tr>`;
  }).join('');
  renderCoupons(data.coupons || []);
}

function renderCoupons(coupons) {
  $('couponsBox').innerHTML = coupons.length ? coupons.map(c => `
    <div class="coupon">
      <div class="coupon-title">${esc(c.name)} <span>${esc(c.total_odds || 0)}</span></div>
      <p>${esc(c.label || '')}</p>
      <p>Confidence: <b>${esc(c.avg_confidence || 0)}%</b> · Ryzyko: <b>${esc(c.risk || '-')}</b></p>
      <ul>${(c.picks || []).map(p => `<li>${esc(p.match)} — <b>${esc(p.bet)}</b> @ ${esc(p.odds || '-')}</li>`).join('')}</ul>
    </div>`).join('') : '<p class="muted">Brak kuponów AKO. GPT musi najpierw znaleźć typy PLAY.</p>';
}

function showReport(i) {
  const r = (currentData.analyses || [])[i];
  if (!r) return;
  const a = r.analysis || {};
  $('reportBox').innerHTML = `
    <div class="report-head">
      <h3>${esc(r.match)}</h3>
      <div>${badge(esc(r.decision), String(r.decision).toUpperCase() === 'PLAY' ? 'play' : 'skip')}</div>
    </div>
    <p class="summary"><b>Typ:</b> ${esc(r.bet)} · <b>Kurs:</b> ${esc(r.odds || '-')} · <b>Confidence:</b> ${esc(r.confidence || 0)}% · <b>Value:</b> ${esc(r.value_score || 0)}/10</p>
    <p class="summary">${esc(r.summary || '')}</p>
    ${section('Forma', a.forma)}
    ${section('Kontuzje i kadra', a.kontuzje_kadra)}
    ${section('Styl gry i matchup', a.styl_matchup)}
    ${section('Motywacja i atmosfera', a.motywacja_atmosfera)}
    ${section('Value kursu', a.value_kurs)}
    ${section('Ryzyka', a.ryzyka)}
    ${section('Rekomendacja GPT', a.rekomendacja)}
  `;
}

function section(title, text) {
  return `<article class="report-section"><h4>${esc(title)}</h4><p>${esc(text || 'Brak danych.')}</p></article>`;
}

$('runBtn').addEventListener('click', runAnalysis);
loadData();
setInterval(loadData, 60000);
