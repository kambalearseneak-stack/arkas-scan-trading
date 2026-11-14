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

// Effet Scan
function toggleScanEffect(active) {
  const scanLine = $('scanLine');
  if (scanLine) active ? scanLine.classList.add('active') : scanLine.classList.remove('active');
}

// --- LOGIQUE DE COLLAGE (PRESSE-PAPIERS) ---
$('pasteZone')?.addEventListener('click', () => $('chartFile')?.click());

// Intercepter le Ctrl+V n'importe où sur la page
document.addEventListener('paste', (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;

  for (let i = 0; i < items.length; i++) {
    if (items[i].type.indexOf('image') !== -1) {
      const blob = items[i].getAsFile();
      handleImageUpload(blob);
      break;
    }
  }
});

// Gérer l'upload via le bouton classique
$('chartFile')?.addEventListener('change', (e) => {
  if (e.target.files.length > 0) handleImageUpload(e.target.files[0]);
});

function handleImageUpload(file) {
  if (!file) return;
  
  // Basculer sur l'onglet Scanner
  document.querySelector('[data-tab="scanner"]')?.click();
  
  // Afficher l'aperçu
  $('preview').src = URL.createObjectURL(file);
  $('previewWrap').classList.remove('hidden');
  
  // Lancer l'analyse automatiquement
  setTimeout(() => $('analyzeBtn')?.click(), 500);
}

// Bouton depuis TradingView
$('goToScannerBtn')?.addEventListener('click', () => {
  document.querySelector('[data-tab="scanner"]')?.click();
  alert("📸 Cliquez sur l'appareil photo du graphique, choisissez 'Copier l'image', puis revenez sur cette page : l'analyse se fera automatiquement !");
});

// Lancer l'analyse
$('analyzeBtn')?.addEventListener('click', async () => {
  // Récupérer le fichier depuis l'input ou depuis l'aperçu
  const file = $('chartFile').files[0];
  
  // Si le fichier vient du presse-papiers, on le recrée
  let fileToSend = file;
  if (!fileToSend && $('preview').src.startsWith('blob:')) {
    const blob = await (await fetch($('preview').src)).blob();
    fileToSend = new File([blob], "capture.png", { type: "image/png" });
  }
  
  if (!fileToSend) { alert('Veuillez coller ou sélectionner une image.'); return; }
  
  const mode = document.querySelector('input[name="mode"]:checked')?.value || 'scan';
  const asset = $('assetSelect').value;
  const timeframe = $('timeframeSelect').value;

  const body = new FormData();
  body.append('file', fileToSend);
  body.append('mode', mode);
  body.append('asset', asset);
  body.append('timeframe', timeframe);
  
  $('emptyResult')?.classList.add('hidden');
  $('loadingState')?.classList.remove('hidden');
  $('analysisResult')?.classList.add('hidden');
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
    $('loadingState')?.classList.add('hidden');
    $('errorState').textContent = error.message;
    $('errorState').classList.remove('hidden');
  }
});

// Affichage
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
      <div class="scenario-box"><strong>🚀 Principal :</strong><br>${r.scenarios.principal}</div>
      <div class="scenario-box" style="border-left-color: var(--blue);"><strong>🔄 Alternatif :</strong><br>${r.scenarios.alternatif}</div>
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
      <div class="history-item"><div><strong>#${item.id} · ${item.signal}</strong><br><small>${item.asset} (${item.timeframe})</small></div></div>
    `).join('');
  } catch (e) { target.textContent = "Erreur historique"; }
}
