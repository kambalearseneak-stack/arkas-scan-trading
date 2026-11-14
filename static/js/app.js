const $ = (id) => document.getElementById(id);
let currentReport = null;

// Navigation
document.querySelectorAll('.tab').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === button));
    document.querySelectorAll('.tab-panel').forEach(panel =>
      panel.classList.toggle('active', panel.id === `panel-${button.dataset.tab}`)
    );
    if (button.dataset.tab === 'history') loadHistory();
  });
});

// Image et Effet Scan
$('chartFile')?.addEventListener('change', () => {
  const file = $('chartFile').files?.[0];
  if (!file) return;
  $('preview').src = URL.createObjectURL(file);
  $('previewWrap').classList.remove('hidden');
});

function toggleScanEffect(active) {
  const scanLine = $('scanLine');
  if (scanLine) active ? scanLine.classList.add('active') : scanLine.classList.remove('active');
}

// Lancer l'analyse
$('analyzeBtn')?.addEventListener('click', async () => {
  const file = $('chartFile').files?.[0];
  if (!file) { alert('Sélectionne une capture.'); return; }
  
  const mode = document.querySelector('input[name="mode"]:checked')?.value || 'scan';
  const asset = $('assetSelect').value;
  const timeframe = $('timeframeSelect').value;

  const body = new FormData();
  body.append('file', file);
  body.append('mode', mode);
  body.append('asset', asset);
  body.append('timeframe', timeframe);
  
  $('emptyResult').classList.add('hidden');
  $('loadingState').classList.remove('hidden');
  $('analysisResult').classList.add('hidden');
  $('errorState').classList.add('hidden');
  toggleScanEffect(true);

  try {
    const response = await fetch('/api/analyze', { method: 'POST', body });
    const data = await response.json();
    toggleScanEffect(false);

    if (!response.ok) throw new Error(data.error || 'Erreur.');
    currentReport = data.result;
    renderReport(currentReport, mode);
  } catch (error) {
    toggleScanEffect(false);
    $('loadingState').classList.add('hidden');
    $('errorState').textContent = error.message;
    $('errorState').classList.remove('hidden');
  }
});

// Affichage des Cartes
function renderReport(r, mode) {
  $('loadingState')?.classList.add('hidden');
  $('analysisResult')?.classList.remove('hidden');
  $('resultMode').textContent = mode === 'audit' ? 'AUDIT' : 'SCANNER';
  
  const signal = (r.signal || 'WAIT').toUpperCase();
  $('signalText').textContent = signal;
  $('signalBanner').className = 'signal-banner ' + (signal.includes('BUY') ? 'buy' : signal.includes('SELL') ? 'sell' : 'wait');
  
  $('confidence').textContent = `${r.confidence || 0}/100`;
  $('asset').textContent = r.asset || '—';
  $('timeframe').textContent = r.timeframe || '—';
  $('trend').textContent = r.trend || '—';
  $('entry').textContent = r.entry || '—';
  $('stopLoss').textContent = r.stop_loss || '—';
  $('structure').textContent = r.structure || '—';
  
  $('targets').innerHTML = (r.take_profits || []).map(tp => `<span>${tp}</span>`).join('');
  $('zones').innerHTML = (r.zones || []).map(z => `<span>${z}</span>`).join('');
  $('reasons').innerHTML = (r.reasons || []).map(reason => `<li>${reason}</li>`).join('');
  
  if (r.scenarios) {
    $('scenarios').innerHTML = `
      <div class="scenario-box"><strong>🚀 Scénario Principal</strong>${r.scenarios.principal}</div>
      <div class="scenario-box" style="border-left-color: #0ea5e9;"><strong>🔄 Scénario Alternatif</strong>${r.scenarios.alternatif}</div>
    `;
  }
  
  $('invalidation').textContent = r.invalidation || '—';
  $('riskWarning').textContent = r.risk_warning || '';
}

// Historique
async function loadHistory() {
  const target = $('historyList');
  if (!target) return;
  target.innerHTML = '<p class="muted">Chargement…</p>';
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    if (!data.items.length) { target.innerHTML = '<p>Aucune analyse.</p>'; return; }
    target.innerHTML = data.items.map(item => `
      <div class="history-item">
        <div><strong>#${item.id} · ${item.signal}</strong><br><small>${item.asset} (${item.timeframe})</small></div>
      </div>
    `).join('');
  } catch (e) { target.textContent = "Erreur historique"; }
}
