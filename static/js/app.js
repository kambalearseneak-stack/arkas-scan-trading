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

// --- FONCTION POUR L'EFFET DE SCAN ---
function toggleScanEffect(active) {
  const scanLine = $('scanLine');
  if (scanLine) {
    if (active) scanLine.classList.add('active');
    else scanLine.classList.remove('active');
  }
}

function setLoading(on) {
  $('emptyResult').classList.toggle('hidden', on || !!currentReport);
  $('loadingState').classList.toggle('hidden', !on);
  $('analysisResult').classList.add('hidden');
  $('errorState').classList.add('hidden');
  $('analyzeBtn').disabled = on;
  $('analyzeBtn').textContent = on ? 'Analyse en cours…' : "Lancer l'analyse →";
  
  // Activation/Désactivation de l'effet visuel
  toggleScanEffect(on);
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
    
    // On coupe l'effet de scan une fois la réponse reçue
    toggleScanEffect(false);

    if (!response.ok) throw new Error(data.error || 'Erreur pendant l’analyse.');
    currentReport = data.result;
    renderReport(currentReport, mode);
  } catch (error) {
    toggleScanEffect(false);
    $('loadingState').classList.add('hidden');
    $('emptyResult').classList.add('hidden');
    $('errorState').textContent = error.message;
    $('errorState').classList.remove('hidden');
  } finally {
    $('analyzeBtn').disabled = false;
    $('analyzeBtn').textContent = "Lancer l'analyse →";
  }
});

// ... (Le reste des fonctions renderReport, loadHistory, calculateRisk, etc. reste inchangé)
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

// [Le reste du code JS (copyResult, loadHistory, calculateRisk) est identique à celui que vous avez déjà]
