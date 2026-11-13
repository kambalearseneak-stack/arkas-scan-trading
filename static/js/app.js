const $ = (id) => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
let currentReport = null;

document.querySelectorAll('.tab').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === button));
    document.querySelectorAll('.tab-panel').forEach(panel =>
      panel.classList.toggle('active', panel.id === `panel-${button.dataset.tab}`)
    );
    if (button.dataset.tab === 'history') loadHistory();
  });
});

const fileInput = $('chartFile');
fileInput?.addEventListener('change', () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) {
    alert('Image trop volumineuse : maximum 8 Mo.');
    fileInput.value = '';
    return;
  }
  $('preview').src = URL.createObjectURL(file);
  $('previewWrap').classList.remove('hidden');
});
$('removeImage')?.addEventListener('click', () => {
  fileInput.value = '';
  $('preview').removeAttribute('src');
  $('previewWrap').classList.add('hidden');
});

function setLoading(on) {
  $('emptyResult').classList.toggle('hidden', on || !!currentReport);
  $('loadingState').classList.toggle('hidden', !on);
  $('analysisResult').classList.add('hidden');
  $('errorState').classList.add('hidden');
  $('analyzeBtn').disabled = on;
  $('analyzeBtn').textContent = on ? 'Analyse en cours…' : "Lancer l'analyse →";
}

$('analyzeBtn')?.addEventListener('click', async () => {
  const file = fileInput.files?.[0];
  if (!file) { alert('Sélectionne une capture de graphique.'); return; }
  const mode = document.querySelector('input[name="mode"]:checked')?.value || 'scan';
  const body = new FormData();
  body.append('file', file);
  body.append('mode', mode);
  setLoading(true);
  try {
    const response = await fetch('/api/analyze', {
      method: 'POST', headers: {'X-CSRF-Token': csrf}, body
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Erreur pendant l’analyse.');
    currentReport = data.result;
    renderReport(currentReport, mode);
  } catch (error) {
    $('loadingState').classList.add('hidden');
    $('emptyResult').classList.add('hidden');
    $('errorState').textContent = error.message;
    $('errorState').classList.remove('hidden');
  } finally {
    $('analyzeBtn').disabled = false;
    $('analyzeBtn').textContent = "Lancer l'analyse →";
  }
});

function safeText(value, fallback='Non déterminable') {
  if (value === null || value === undefined || value === '') return fallback;
  if (Array.isArray(value)) return value.join(', ') || fallback;
  return String(value);
}
function renderReport(r, mode) {
  $('emptyResult').classList.add('hidden');
  $('loadingState').classList.add('hidden');
  $('analysisResult').classList.remove('hidden');
  $('resultMode').textContent = mode === 'audit' ? 'AUDIT' : 'SCANNER';
  const signal = safeText(r.signal, 'WAIT').toUpperCase();
  $('signalText').textContent = signal;
  $('signalBanner').className = 'signal-banner ' + (signal.includes('BUY') ? 'buy' : signal.includes('SELL') ? 'sell' : 'wait');
  $('confidence').textContent = `${Math.max(0, Math.min(100, Number(r.confidence) || 0))}/100`;
  $('asset').textContent = safeText(r.asset);
  $('timeframe').textContent = safeText(r.timeframe);
  $('trend').textContent = safeText(r.trend);
  $('entry').textContent = safeText(r.entry);
  $('stopLoss').textContent = safeText(r.stop_loss);
  $('structure').textContent = safeText(r.structure);
  $('targets').replaceChildren();
  (Array.isArray(r.take_profits) ? r.take_profits : [r.take_profits || 'Non déterminables']).forEach((x, i) => {
    const el = document.createElement('span'); el.textContent = `TP${i+1} · ${safeText(x)}`; $('targets').append(el);
  });
  $('zones').replaceChildren();
  (Array.isArray(r.zones) ? r.zones : [r.zones]).filter(Boolean).forEach(x => {
    const el = document.createElement('span'); el.textContent = safeText(x); $('zones').append(el);
  });
  $('reasons').replaceChildren();
  (Array.isArray(r.reasons) ? r.reasons : [r.reasons || 'Aucune justification fournie.']).forEach(x => {
    const li = document.createElement('li'); li.textContent = safeText(x); $('reasons').append(li);
  });
  $('invalidation').textContent = safeText(r.invalidation);
  $('riskWarning').textContent = safeText(r.risk_warning, 'Vérifie les niveaux avant toute décision.');
}

$('copyResult')?.addEventListener('click', async () => {
  if (!currentReport) return;
  try {
    await navigator.clipboard.writeText(JSON.stringify(currentReport, null, 2));
    $('copyResult').textContent = 'Rapport copié ✓';
  } catch { $('copyResult').textContent = 'Copie non disponible'; }
});

async function loadHistory() {
  const target = $('historyList');
  target.innerHTML = '<p class="muted">Chargement…</p>';
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erreur historique');
    target.replaceChildren();
    if (!data.items.length) { target.innerHTML = '<p class="muted">Aucune analyse enregistrée.</p>'; return; }
    data.items.forEach(item => {
      const row = document.createElement('div'); row.className = 'history-item';
      const info = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = `#${item.id} · ${item.signal || 'WAIT'} · ${item.asset || 'Actif inconnu'}`;
      const sub = document.createElement('small');
      sub.textContent = `${new Date(item.created_at).toLocaleString()} · ${item.mode.toUpperCase()} · ${item.timeframe || 'TF ?'} · confiance ${item.confidence ?? 0}/100`;
      info.append(title, sub);
      const actions = document.createElement('div'); actions.className = 'history-actions';
      const view = document.createElement('button'); view.textContent = 'Voir';
      view.addEventListener('click', () => viewHistory(item.id));
      const del = document.createElement('button'); del.textContent = 'Supprimer'; del.className = 'delete';
      del.addEventListener('click', () => deleteHistory(item.id));
      actions.append(view, del); row.append(info, actions); target.append(row);
    });
  } catch (e) { target.textContent = e.message; }
}
async function viewHistory(id) {
  try {
    const res = await fetch(`/api/history/${id}`); const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Analyse introuvable');
    currentReport = data.result;
    document.querySelector('[data-tab="scanner"]').click();
    renderReport(currentReport, data.mode);
  } catch(e) { alert(e.message); }
}
async function deleteHistory(id) {
  if (!confirm(`Supprimer définitivement l'analyse #${id} ?`)) return;
  const res = await fetch(`/api/history/${id}`, {method:'DELETE', headers:{'X-CSRF-Token':csrf}});
  const data = await res.json();
  if (!res.ok) { alert(data.error || 'Suppression impossible'); return; }
  loadHistory();
}
$('refreshHistory')?.addEventListener('click', loadHistory);

$('calculateRisk')?.addEventListener('click', () => {
  const capital = Number($('capital').value);
  const pct = Number($('riskPercent').value);
  const entry = Number($('entryPrice').value);
  const stop = Number($('stopPrice').value);
  const pointValue = Number($('pointValue').value);
  const rr = Number($('rr').value);
  if (![capital,pct,entry,stop,pointValue,rr].every(Number.isFinite) ||
      capital <= 0 || pct <= 0 || pct > 100 || entry <= 0 || stop <= 0 ||
      pointValue <= 0 || rr <= 0 || entry === stop) {
    alert('Vérifie les valeurs : elles doivent être positives et entrée différente du stop.');
    return;
  }
  const riskMoney = capital * pct / 100;
  const distance = Math.abs(entry - stop);
  const lossPerLot = distance * pointValue;
  const lots = riskMoney / lossPerLot;
  const reward = riskMoney * rr;
  const direction = entry > stop ? 1 : -1;
  const target = entry + direction * distance * rr;
  $('riskMoney').textContent = `$${riskMoney.toFixed(2)}`;
  $('distance').textContent = distance.toFixed(5);
  $('lotSize').textContent = lots.toFixed(4) + ' lot(s) théorique(s)';
  $('rewardMoney').textContent = `$${reward.toFixed(2)}`;
  $('targetPrice').textContent = target.toFixed(5);
  $('riskEmpty').classList.add('hidden');
  $('riskResult').classList.remove('hidden');
});
