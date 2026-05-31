const STORE_ID = 'ST1008'
const BASE = ''
const REFRESH_MS = 5000

function zoneColor(score) {
  if (score >= 80) return '#6366f1'
  if (score >= 50) return '#8b5cf6'
  if (score >= 25) return '#a78bfa'
  return '#4c1d95'
}

async function fetchJSON(url) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}

async function updateMetrics() {
  const data = await fetchJSON(`${BASE}/stores/${STORE_ID}/metrics`)
  document.getElementById('visitors').textContent = data.unique_visitors
  document.getElementById('conversion').textContent =
    (data.conversion_rate * 100).toFixed(1) + '%'

  const queueElement = document.getElementById('queue')
  queueElement.textContent = data.queue_depth
  queueElement.className = 'card-value' + (data.queue_depth >= 5 ? ' warn' : data.queue_depth === 0 ? ' good' : '')

  document.getElementById('abandonment').textContent =
    (data.abandonment_rate * 100).toFixed(1) + '%'
}

async function updateFunnel() {
  const data = await fetchJSON(`${BASE}/stores/${STORE_ID}/funnel`)
  const max = data.stages[0]?.visitors || 1
  const html = data.stages.map((stage) => {
    const pct = max > 0 ? (stage.visitors / max) * 100 : 0
    const drop = stage.drop_off_pct > 0 ? `-${(stage.drop_off_pct * 100).toFixed(0)}%` : ''
    return `
      <div class="funnel-stage">
        <div>
          <div class="funnel-label">${stage.label}</div>
          <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:${pct}%"></div></div>
        </div>
        <div class="funnel-right">
          <div class="funnel-count">${stage.visitors}</div>
          <div class="funnel-drop">${drop}</div>
        </div>
      </div>`
  }).join('')
  document.getElementById('funnel-container').innerHTML = html
}

async function updateHeatmap() {
  const data = await fetchJSON(`${BASE}/stores/${STORE_ID}/heatmap`)
  if (!data.zones.length) {
    document.getElementById('heatmap-container').innerHTML =
      '<span class="loading">No zone data yet</span>'
    return
  }
  const html = data.zones.map((zone) => `
    <div class="zone-row">
      <div class="zone-name">${zone.zone_id.replace(/_/g, ' ')}</div>
      <div class="zone-bar-wrap">
        <div class="zone-bar" style="width:${zone.score}%;background:${zoneColor(zone.score)}"></div>
      </div>
      <div class="zone-score">${zone.score}</div>
    </div>`
  ).join('')
  document.getElementById('heatmap-container').innerHTML = html
}

async function updateAnomalies() {
  const data = await fetchJSON(`${BASE}/stores/${STORE_ID}/anomalies`)
  if (!data.anomalies.length) {
    document.getElementById('anomalies-container').innerHTML =
      '<div class="no-anomalies">No active anomalies</div>'
    return
  }
  const html = data.anomalies.map((anomaly) => `
    <div class="anomaly">
      <span class="badge ${anomaly.severity}">${anomaly.severity}</span>
      <div>
        <div class="anomaly-text">${anomaly.detail}</div>
        <div class="anomaly-action">${anomaly.suggested_action}</div>
      </div>
    </div>`
  ).join('')
  document.getElementById('anomalies-container').innerHTML = html
}

async function updateHealth() {
  const data = await fetchJSON(`${BASE}/health`)
  const dot = document.getElementById('status-dot')
  const text = document.getElementById('status-text')
  const store = data.stores.find((item) => item.store_id === STORE_ID)

  if (!data.db_connected) {
    dot.className = 'dot error'
    text.textContent = 'DB unavailable'
  } else if (store?.status === 'STALE_FEED') {
    dot.className = 'dot stale'
    text.textContent = 'Stale feed'
  } else {
    dot.className = 'dot'
    text.textContent = 'Live'
  }
}

async function refresh() {
  try {
    await Promise.all([
      updateMetrics(),
      updateFunnel(),
      updateHeatmap(),
      updateAnomalies(),
      updateHealth(),
    ])
    const now = new Date()
    document.getElementById('last-updated').textContent =
      'Updated ' + now.toLocaleTimeString()
  } catch (error) {
    console.error('Refresh error:', error)
    document.getElementById('status-dot').className = 'dot error'
    document.getElementById('status-text').textContent = 'API error'
  }
}

refresh()
setInterval(refresh, REFRESH_MS)
