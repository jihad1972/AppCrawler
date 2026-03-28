import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { createCrawlSocket, stopCrawl, pauseCrawl, resumeCrawl, getCrawlStatus, screenshotUrl } from '../api'

const ACTION_ICONS = {
  tap: '👆',
  swipe_up: '⬆️',
  swipe_down: '⬇️',
  swipe_left: '⬅️',
  swipe_right: '➡️',
  back: '◀️',
  type_text: '⌨️',
  home: '🏠',
  wait: '⏳',
  none: '❓',
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function CrawlSession() {
  const { crawlId } = useParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState(null)
  const [steps, setSteps] = useState([])
  const [latestScreenshot, setLatestScreenshot] = useState(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const [etaSeconds, setEtaSeconds] = useState(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(null)
  const [avgStepDuration, setAvgStepDuration] = useState(null)
  const logRef = useRef(null)
  const wsRef = useRef(null)
  const elapsedTimerRef = useRef(null)

  // Fetch initial status
  useEffect(() => {
    getCrawlStatus(crawlId)
      .then(setStatus)
      .catch(() => {})
  }, [crawlId])

  // Live elapsed timer
  useEffect(() => {
    if (status?.status === 'running') {
      elapsedTimerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => (prev != null ? prev + 1 : null))
      }, 1000)
    } else {
      clearInterval(elapsedTimerRef.current)
    }
    return () => clearInterval(elapsedTimerRef.current)
  }, [status?.status])

  // WebSocket connection
  useEffect(() => {
    const ws = createCrawlSocket(crawlId, (msg) => {
      switch (msg.event) {
        case 'status':
          setStatus((prev) => ({ ...prev, ...msg.data }))
          setConnected(true)
          break
        case 'step':
          setSteps((prev) => [...prev, msg.data])
          setStatus((prev) => ({
            ...prev,
            steps_taken: msg.data.step + 1,
            unique_screens: msg.data.unique_screens,
            current_screen: msg.data.screen_label,
            status: 'running',
          }))
          // Update ETA & timing
          if (msg.data.eta_seconds != null) setEtaSeconds(msg.data.eta_seconds)
          if (msg.data.elapsed_seconds != null) setElapsedSeconds(msg.data.elapsed_seconds)
          if (msg.data.avg_step_duration != null) setAvgStepDuration(msg.data.avg_step_duration)
          break
        case 'screenshot':
          setLatestScreenshot(msg.data.filename)
          break
        case 'complete':
          setStatus((prev) => ({
            ...prev,
            ...msg.data,
            status: msg.data.status || 'completed',
          }))
          break
        case 'paused':
          setStatus((prev) => ({ ...prev, status: 'paused' }))
          break
        case 'resumed':
          setStatus((prev) => ({ ...prev, status: 'running' }))
          break
        case 'error':
          setStatus((prev) => ({
            ...prev,
            status: 'failed',
            error: msg.data.error,
          }))
          setError(msg.data.error)
          break
        case 'pong':
        case 'ping':
          break
        default:
          break
      }
    })
    wsRef.current = ws
    return () => ws.close()
  }, [crawlId])

  // Auto-scroll action log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [steps])

  const handleStop = useCallback(async () => {
    try {
      await stopCrawl(crawlId)
      setStatus((prev) => ({ ...prev, status: 'stopped' }))
    } catch (e) {
      setError(e.message)
    }
  }, [crawlId])

  const handlePause = useCallback(async () => {
    try {
      await pauseCrawl(crawlId)
      setStatus((prev) => ({ ...prev, status: 'paused' }))
    } catch (e) {
      setError(e.message)
    }
  }, [crawlId])

  const handleResume = useCallback(async () => {
    try {
      await resumeCrawl(crawlId)
      setStatus((prev) => ({ ...prev, status: 'running' }))
    } catch (e) {
      setError(e.message)
    }
  }, [crawlId])

  const dismissError = () => setError(null)

  const progress = status
    ? Math.round((status.steps_taken / status.max_steps) * 100)
    : 0

  const isActive = status?.status === 'running' || status?.status === 'starting'
  const isPaused = status?.status === 'paused'
  const isDone = status?.status === 'completed' || status?.status === 'stopped' || status?.status === 'failed'

  return (
    <div className="page">
      <div className="container">
        {/* ── Error Banner ──────────────────────────────────── */}
        {error && (
          <div className="error-banner">
            <div className="error-banner-content">
              <span className="error-banner-icon">⚠️</span>
              <span className="error-banner-text">{error}</span>
            </div>
            <button className="error-banner-close" onClick={dismissError}>✕</button>
          </div>
        )}

        {/* ── Header ────────────────────────────────────────── */}
        <div className="crawl-header">
          <div>
            <h1>
              {status?.status === 'running' && '🔄 '}
              {status?.status === 'paused' && '⏸️ '}
              {status?.status === 'completed' && '✅ '}
              {status?.status === 'failed' && '❌ '}
              {status?.status === 'stopped' && '⏹️ '}
              {status?.package_name || 'Crawl Session'}
            </h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
              Session: {crawlId}
            </p>
          </div>
          <div className="crawl-controls">
            {isDone && (
              <Link to={`/gallery/${crawlId}`} className="btn btn-primary btn-sm">
                📸 View Gallery
              </Link>
            )}
            {isActive && (
              <>
                <button className="btn btn-warning btn-sm" onClick={handlePause}>
                  ⏸ Pause
                </button>
                <button className="btn btn-danger btn-sm" onClick={handleStop}>
                  ⏹ Stop
                </button>
              </>
            )}
            {isPaused && (
              <>
                <button className="btn btn-success btn-sm" onClick={handleResume}>
                  ▶ Resume
                </button>
                <button className="btn btn-danger btn-sm" onClick={handleStop}>
                  ⏹ Stop
                </button>
              </>
            )}
            <Link to="/" className="btn btn-secondary btn-sm">← Back</Link>
          </div>
        </div>

        {/* ── Progress Bar ──────────────────────────────────── */}
        <div className="progress-bar-container" style={{ marginBottom: 24 }}>
          <div
            className={`progress-bar-fill ${isPaused ? 'paused' : ''}`}
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* ── ETA Bar ───────────────────────────────────────── */}
        {(isActive || isPaused) && (
          <div className="eta-bar">
            <div className="eta-item">
              <span className="eta-label">Elapsed</span>
              <span className="eta-value">{formatDuration(elapsedSeconds)}</span>
            </div>
            <div className="eta-item">
              <span className="eta-label">ETA</span>
              <span className="eta-value">{formatDuration(etaSeconds)}</span>
            </div>
            <div className="eta-item">
              <span className="eta-label">Avg/Step</span>
              <span className="eta-value">{avgStepDuration ? `${avgStepDuration}s` : '—'}</span>
            </div>
            <div className="eta-item">
              <span className="eta-label">Status</span>
              <span className={`eta-status ${status?.status}`}>
                {isPaused ? '⏸ Paused' : '● Running'}
              </span>
            </div>
          </div>
        )}

        {/* ── Main Layout ───────────────────────────────────── */}
        <div className="crawl-layout">
          {/* Left: Live Preview */}
          <div className="live-preview glass-card">
            {latestScreenshot ? (
              <img
                src={screenshotUrl(crawlId, latestScreenshot)}
                alt="Current screen"
                key={latestScreenshot}
                className="screenshot-animate"
              />
            ) : (
              <div className="empty-state" style={{ paddingTop: '40%' }}>
                <div className="spinner" style={{ margin: '0 auto 16px' }} />
                <h3>{isActive ? 'Waiting for first screenshot...' : 'No screenshots yet'}</h3>
              </div>
            )}
            {latestScreenshot && (
              <div className="step-badge">
                Step {status?.steps_taken || 0} / {status?.max_steps || '—'}
              </div>
            )}
          </div>

          {/* Right: Sidebar */}
          <div className="crawl-sidebar">
            {/* Stats */}
            <div className="stats-bar">
              <div className="stat-card glass-card">
                <div className="stat-value">{status?.steps_taken || 0}</div>
                <div className="stat-label">Steps</div>
              </div>
              <div className="stat-card glass-card">
                <div className="stat-value">{status?.unique_screens || 0}</div>
                <div className="stat-label">Screens</div>
              </div>
              <div className="stat-card glass-card">
                <div className="stat-value">{progress}%</div>
                <div className="stat-label">Progress</div>
              </div>
            </div>

            {/* Current screen */}
            {status?.current_screen && (
              <div className="glass-card" style={{ padding: 16, textAlign: 'center' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
                  Current Screen
                </div>
                <div style={{ fontSize: '1rem', fontWeight: 700, marginTop: 4, color: 'var(--accent-cyan)' }}>
                  {status.current_screen}
                </div>
              </div>
            )}

            {/* Action Log */}
            <div className="glass-card" style={{ flex: 1 }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
                <h3 style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
                  🧠 AI Action Log
                </h3>
              </div>
              <div className="action-log" ref={logRef}>
                {steps.length === 0 ? (
                  <div className="empty-state" style={{ padding: 30 }}>
                    <p>{isActive ? 'Waiting for actions...' : 'No actions recorded'}</p>
                  </div>
                ) : (
                  steps.map((s, i) => (
                    <div className="action-entry" key={i}>
                      <span className="action-step">#{s.step}</span>
                      <span className="action-icon">{ACTION_ICONS[s.action] || '❓'}</span>
                      <div className="action-detail">
                        <strong>{s.element || s.action}</strong>
                        {s.reasoning && (
                          <div style={{ marginTop: 2, fontSize: '0.78rem' }}>{s.reasoning}</div>
                        )}
                        {s.screen_label && (
                          <div style={{ marginTop: 2, color: 'var(--accent-cyan)', fontSize: '0.75rem' }}>
                            📍 {s.screen_label}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
