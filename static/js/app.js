const $ = (id) => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
let currentReport = null;

// Onglets
document.querySelectorAll('.tab').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === button));
    document.querySelectorAll('.tab-panel').forEach(panel =>
      panel.classList.toggle('active', panel.id === `panel-${button.dataset.tab}`)
    );
    if (button.dataset.tab === 'history') loadHistory();
  });
});

// Image classique
const fileInput = $('chartFile');
fileInput?.addEventListener('change', () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  $('preview').src = URL.createObjectURL(file);
  $('previewWrap').classList.remove('hidden');
});

function toggleScanEffect(active) {
  const scanLine = $('scanLine');
  if (scanLine) active ? scanLine.classList.add('active') : scanLine.classList.remove('active');
}

// Analyse via capture classique
$('analyzeBtn')?.addEventListener('click', async () => {
  const file = fileInput.files?.[0];
  if (!file) { alert('Sélectionne une capture.'); return; }
  
  const mode = document.querySelector('input[name="mode"]:checked')?.value || 'scan';
  const asset = $('assetSelect').value;
  const timeframe = $('timeframeSelect').value;

  const body = new FormData();
  body.append('file', file);
  body.append('mode', mode);
  body.append('asset', asset);
  body.append('timeframe', timeframe);
  
  startAnalysis(body, mode);
});

// Analyse directe du graphique TradingView
$('scanTvBtn')?.addEventListener('click', async () => {
  const chartDiv = $('tradingview_chart');
  if (!chartDiv) return;

  // On change d'onglet pour afficher le résultat
  document.querySelector('[data-tab="scanner"]')?.click();
  
  // On affiche l'effet de scan
  toggleScanEffect(true);
  $('emptyResult')?.classList.add('hidden');
  $('loadingState')?.classList.remove('hidden');
  $('analysisResult')?.classList.add('hidden');

  // Tentative de capture via html2canvas
  try {
    const canvas = await html2canvas(chartDiv, {
      useCORS: true, // Important pour TradingView
      allowTaint: true,
      scale: 2 // Haute résolution pour que l'IA lise bien
    });
    
    canvas.toBlob(async (blob) => {
      if (!blob) {
        alert("La capture a échoué. Utilisez le bouton 'Appareil photo' de TradingView.");
        return;
      }
      
      const file = new File([blob], "tradingview_capture.png", { type: "image/png" });
      
      // On affiche l'aperçu de la capture
      $('preview').src = URL.createObjectURL(file);
      $('previewWrap').classList.remove('hidden');

      const body = new FormData();
      body.append('file', file);
      body.append('mode', 'scan');
      body.append('asset', "Déduire de l'image");
      body.append('timeframe', "Déduire de l'image");
      
      // On lance l'analyse avec l'image capturée
      await startAnalysis(body, 'scan');
      
    }, 'image/png');
  } catch (error) {
    console.error(error);
    toggleScanEffect(false);
    alert("Impossible de capturer TradingView directement. Cliquez sur l'icône Appareil Photo en haut à droite du graphique.");
  }
});

// Fonction d'analyse centrale
async function startAnalysis(body, mode) {
  toggleScanEffect(true);
  $('emptyResult')?.classList.add('hidden');
  $('loadingState')?.classList.remove('hidden');
  $('analysisResult')?.classList.add('hidden');
  $('errorState')?.classList.add('hidden');

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
}

// Affichage des résultats
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
  
  // Affichage des scénarios détaillés
  if (r.scenarios) {
    $('scenarios').innerHTML = `
      <div class="scenario-box">
        <strong>🚀 Scénario Principal (Plan A) :</strong><br>
        ${r.scenarios.principal}
      </div>
      <div class="scenario-box" style="border-left-color: var(--blue);">
        <strong>🔄 Scénario Alternatif (Plan B) :</strong><br>
        ${r.scenarios.alternatif}
      </div>
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
