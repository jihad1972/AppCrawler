const API_BASE = 'http://localhost:8000'
const WS_BASE  = 'ws://localhost:8000'

export async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export function startCrawl(packageName, playStoreUrl, maxSteps = 40) {
  return fetchJSON('/api/crawl/start', {
    method: 'POST',
    body: JSON.stringify({
      package_name: packageName || undefined,
      play_store_url: playStoreUrl || undefined,
      max_steps: maxSteps,
    }),
  })
}

export function stopCrawl(crawlId) {
  return fetchJSON(`/api/crawl/${crawlId}/stop`, { method: 'POST' })
}

export function pauseCrawl(crawlId) {
  return fetchJSON(`/api/crawl/${crawlId}/pause`, { method: 'POST' })
}

export function resumeCrawl(crawlId) {
  return fetchJSON(`/api/crawl/${crawlId}/resume`, { method: 'POST' })
}

export function getCrawlStatus(crawlId) {
  return fetchJSON(`/api/crawl/${crawlId}/status`)
}

export function getCrawlScreenshots(crawlId) {
  return fetchJSON(`/api/crawl/${crawlId}/screenshots`)
}

export function getDevices() {
  return fetchJSON('/api/devices')
}

export function getCrawls() {
  return fetchJSON('/api/crawls')
}

export function screenshotUrl(crawlId, filename) {
  return `${API_BASE}/api/crawl/${crawlId}/screenshot/${filename}`
}

export function createCrawlSocket(crawlId, onMessage) {
  const ws = new WebSocket(`${WS_BASE}/ws/crawl/${crawlId}`)

  ws.onopen = () => {
    console.log(`[WS] Connected to crawl ${crawlId}`)
  }

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data)
      onMessage(data)
    } catch (e) {
      console.warn('[WS] Parse error:', e)
    }
  }

  ws.onclose = () => {
    console.log(`[WS] Disconnected from crawl ${crawlId}`)
  }

  ws.onerror = (err) => {
    console.error('[WS] Error:', err)
  }

  // Keep alive
  const keepAlive = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send('ping')
    }
  }, 25000)

  return {
    close: () => {
      clearInterval(keepAlive)
      ws.close()
    },
  }
}
