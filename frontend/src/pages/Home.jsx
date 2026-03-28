import { useState, useEffect, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { startCrawl, getCrawls, getDevices } from '../api'

const FEATURES = [
  {
    icon: '🤖',
    color: 'cyan',
    title: 'AI-Powered Exploration',
    desc: 'Gemini Vision AI analyzes each screen and intelligently navigates through every feature and flow.',
  },
  {
    icon: '📱',
    color: 'purple',
    title: 'Automatic Screenshots',
    desc: 'Captures high-resolution screenshots of every unique screen with smart deduplication.',
  },
  {
    icon: '🧠',
    color: 'green',
    title: 'UX Analysis Ready',
    desc: 'Build your own Mobbin-style library for competitor research, UX audits, and product design.',
  },
  {
    icon: '⚡',
    color: 'pink',
    title: 'Real-Time Monitoring',
    desc: 'Watch the AI explore in real-time with live screen preview and action logging.',
  },
]

export default function Home() {
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [maxSteps, setMaxSteps] = useState(40)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sessions, setSessions] = useState([])
  const [devices, setDevices] = useState([])
  const [dragOver, setDragOver] = useState(false)

  // Load existing sessions and devices
  useEffect(() => {
    getCrawls()
      .then((data) => setSessions(data.crawls || []))
      .catch(() => {})
    getDevices()
      .then((data) => setDevices(data.devices || []))
      .catch(() => {})
    // Poll device status every 10s
    const devicePoll = setInterval(() => {
      getDevices()
        .then((data) => setDevices(data.devices || []))
        .catch(() => {})
    }, 10000)
    return () => clearInterval(devicePoll)
  }, [])

  const handleStart = useCallback(async () => {
    if (!input.trim()) return
    setLoading(true)
    setError('')

    try {
      const isUrl = input.includes('play.google.com') || input.includes('http')
      const result = await startCrawl(
        isUrl ? null : input.trim(),
        isUrl ? input.trim() : null,
        maxSteps
      )
      navigate(`/crawl/${result.crawl_id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [input, maxSteps, navigate])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleStart()
  }

  const handleDrop = useCallback(async (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer?.files?.[0]
    if (!file || !file.name.endsWith('.apk')) {
      setError('Please drop a valid .apk file')
      return
    }

    setLoading(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('http://localhost:8000/api/upload-apk', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error('Upload failed')
      const data = await res.json()
      setInput(data.path || '')
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const statusColor = (s) => {
    const map = { running: 'running', completed: 'completed', failed: 'failed', stopped: 'stopped' }
    return map[s] || 'pending'
  }

  return (
    <div className="page">
      <div className="container">
        {/* ── Hero ──────────────────────────────────────────── */}
        <section className="hero">
          <div className="hero-badge">⚡ AI-Powered Mobile Crawler</div>
          <h1>
            Capture Every Screen<br />
            <span className="gradient-text">of Any Mobile App</span>
          </h1>
          <p>
            Enter an app's package name or Play Store link. Our AI agent will
            install, explore, and screenshot every screen — automatically.
          </p>

          {/* ── Search ─────────────────────────────────────── */}
          <div className="search-box">
            <div className="search-input-wrapper">
              <input
                id="search-input"
                className="input-field"
                type="text"
                placeholder="com.spotify.music or Play Store URL..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
              />
              <button
                id="start-crawl-btn"
                className="btn btn-primary"
                onClick={handleStart}
                disabled={loading || !input.trim()}
              >
                {loading ? (
                  <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }}></span>
                ) : (
                  '🚀 Start Crawl'
                )}
              </button>
            </div>
            {error && (
              <p style={{ color: '#ef4444', fontSize: '0.85rem', marginTop: 12, textAlign: 'left' }}>
                ⚠️ {error}
              </p>
            )}
            {!loading && devices.length === 0 && (
              <p style={{ color: 'var(--accent-orange)', fontSize: '0.82rem', marginTop: 8, textAlign: 'left' }}>
                💡 No emulator detected. Launch one via Android Studio → Virtual Device Manager.
              </p>
            )}
          </div>

          <div className="divider">or</div>

          {/* ── Upload Zone ────────────────────────────────── */}
          <div
            className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div className="upload-icon">📦</div>
            <p>Drag & drop an APK file here to install and crawl</p>
          </div>

          {/* ── Config ─────────────────────────────────────── */}
          <div className="config-panel glass-card" style={{ maxWidth: 480, margin: '20px auto 0' }}>
            <h3>⚙️ Settings</h3>
            <div className="config-row">
              <label htmlFor="max-steps">Max Steps</label>
              <input
                id="max-steps"
                className="input-field"
                type="number"
                min={5}
                max={200}
                value={maxSteps}
                onChange={(e) => setMaxSteps(Number(e.target.value))}
              />
            </div>
            <div className="config-row">
              <label>Connected Devices</label>
              <span style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', display: 'inline-block',
                  background: devices.length > 0 ? 'var(--accent-green)' : '#ef4444',
                  boxShadow: devices.length > 0 ? '0 0 6px var(--accent-green)' : '0 0 6px #ef4444',
                }} />
                <span style={{ color: devices.length > 0 ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                  {devices.length > 0 ? `${devices.length} device(s) online` : 'No devices'}
                </span>
              </span>
            </div>
          </div>
        </section>

        {/* ── Features ─────────────────────────────────────── */}
        <div className="features-grid">
          {FEATURES.map((f, i) => (
            <div className="feature-card glass-card" key={i}>
              <div className={`feature-icon ${f.color}`}>{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>

        {/* ── Recent Sessions ──────────────────────────────── */}
        {sessions.length > 0 && (
          <section className="sessions-section">
            <h2>📋 Recent Crawl Sessions</h2>
            <div className="session-list">
              {sessions.map((s) => (
                <Link
                  key={s.crawl_id}
                  to={s.status === 'completed' ? `/gallery/${s.crawl_id}` : `/crawl/${s.crawl_id}`}
                  className="session-item glass-card"
                >
                  <div className={`session-status ${statusColor(s.status)}`} />
                  <div className="session-info">
                    <div className="session-name">{s.package_name || 'Unknown App'}</div>
                    <div className="session-meta">
                      {s.status} · {s.steps_taken}/{s.max_steps} steps
                    </div>
                  </div>
                  <div className="session-screens">
                    📸 {s.unique_screens}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
