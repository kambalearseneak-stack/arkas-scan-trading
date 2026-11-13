const $ = (id) => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
let currentReport = null;

// 1. GESTION DES ONGLETS
document.querySelectorAll('.tab').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === button));
    document.querySelectorAll('.tab-panel').forEach(panel =>
      panel.classList.toggle('active', panel.id === `panel-${button.dataset.tab}`)
    );
    if (button.dataset.tab === 'history') loadHistory();
  });
});

// 2. GESTION DE L'IMAGE ET EFFET DE SCAN
const fileInput = $('chartFile');
fileInput?.addEventListener('change', () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  $('preview').src = URL.createObjectURL(file);
  $('previewWrap').classList.remove('hidden');
});

$('removeImage')?.addEventListener('click', () => {
  fileInput.value = '';
  $('preview').removeAttribute('src');
  $('previewWrap').classList.add('hidden');
});

function toggleScanEffect(active) {
  const scanLine = $('scanLine');
  if (scanLine) active ? scanLine.classList.add('active') : scanLine.classList.remove('active');
}

function setLoading(on) {
  $('emptyResult')?.classList.toggle('hidden', on || !!currentReport);
  $('loadingState')?.classList.toggle('hidden', !on);
  $('analysisResult')?.classList.add('hidden');
  $('errorState')?.classList.add('hidden');
  if ($('analyzeBtn')) {
    $('analyzeBtn').disabled = on;
    $('analyzeBtn').textContent = on ? 'Analyse en cours…' : "Lancer l'analyse →";
  }
  toggleScanEffect(on);
}

// 3. LANCER L'ANALYSE
$('analyzeBtn')?.addEventListener('click', async () => {
  const file = fileInput.files?.[0];
  if (!file) { alert('Sélectionne une capture.'); return; }
  
  const body = new FormData();
  body.append('file', file);
  body.append('mode', 'scan');
  
  setLoading(true);
  
  try {
    const response = await fetch('/api/analyze', { method: 'POST', body });
    const data = await response.json();
    toggleScanEffect(false);

    if (!response.ok) throw new Error(data.error || 'Erreur.');
    currentReport = data.result;
    renderReport(currentReport);
  } catch (error) {
    toggleScanEffect(false);
    $('loadingState')?.classList.add('hidden');
    $('errorState').textContent = error.message;
    $('errorState').classList.remove('hidden');
  } finally {
    if ($('analyzeBtn')) {
      $('analyzeBtn').disabled = false;
      $('analyzeBtn').textContent = "Lancer l'analyse →";
    }
  }
});

// 4. AFFICHAGE DES BELLES CARTES
function renderReport(r) {
  $('emptyResult')?.classList.add('hidden');
  $('loadingState')?.classList.add('hidden');
  $('analysisResult')?.classList.remove('hidden');
  
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
  $('invalidation').textContent = r.invalidation || '—';
  $('riskWarning').textContent = r.risk_warning || '';
}

// 5. HISTORIQUE (Simplifié)
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
        <div><strong>#${item.id} · ${item.signal}</strong><br><small>${item.asset}</small></div>
      </div>
    `).join('');
  } catch (e) { target.textContent = "Erreur historique"; }
}
