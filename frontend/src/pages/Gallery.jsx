import { useState, useEffect, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getCrawlScreenshots, getCrawlStatus, screenshotUrl } from '../api'

export default function Gallery() {
  const { crawlId } = useParams()
  const [screenshots, setScreenshots] = useState([])
  const [status, setStatus] = useState(null)
  const [filter, setFilter] = useState('all')
  const [lightbox, setLightbox] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getCrawlScreenshots(crawlId),
      getCrawlStatus(crawlId),
    ]).then(([ssData, statusData]) => {
      setScreenshots(ssData.screenshots || [])
      setStatus(statusData)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [crawlId])

  // Extract unique screen labels for filtering
  const screenLabels = useMemo(() => {
    const labels = screenshots
      .map((s) => s.screen_label)
      .filter((l) => l && l !== 'Unknown Screen')
    return ['all', ...new Set(labels)]
  }, [screenshots])

  const filteredScreenshots = useMemo(() => {
    if (filter === 'all') return screenshots
    return screenshots.filter((s) => s.screen_label === filter)
  }, [screenshots, filter])

  const handleDownloadAll = () => {
    // Open all screenshots in new tabs as a simple "download"
    filteredScreenshots.forEach((s) => {
      window.open(screenshotUrl(crawlId, s.filename), '_blank')
    })
  }

  if (loading) {
    return (
      <div className="page">
        <div className="container" style={{ display: 'flex', justifyContent: 'center', paddingTop: '30vh' }}>
          <div className="spinner" />
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="container">
        {/* ── Header ────────────────────────────────────── */}
        <div className="gallery-header">
          <div>
            <h1>📸 Screenshot Gallery</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
              {status?.package_name || crawlId} · {screenshots.length} screenshots · {status?.unique_screens || 0} unique screens
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {screenshots.length > 0 && (
              <button className="btn btn-secondary btn-sm" onClick={handleDownloadAll}>
                ⬇️ Download All
              </button>
            )}
            <Link to={`/crawl/${crawlId}`} className="btn btn-secondary btn-sm">
              📊 Session
            </Link>
            <Link to="/" className="btn btn-secondary btn-sm">← Home</Link>
          </div>
        </div>

        {/* ── Stats Bar ────────────────────────────────── */}
        <div className="stats-bar" style={{ marginBottom: 24 }}>
          <div className="stat-card glass-card">
            <div className="stat-value">{screenshots.length}</div>
            <div className="stat-label">Total Shots</div>
          </div>
          <div className="stat-card glass-card">
            <div className="stat-value">{status?.unique_screens || 0}</div>
            <div className="stat-label">Unique Screens</div>
          </div>
          <div className="stat-card glass-card">
            <div className="stat-value">{status?.steps_taken || 0}</div>
            <div className="stat-label">Steps Taken</div>
          </div>
        </div>

        {/* ── Filters ──────────────────────────────────── */}
        {screenLabels.length > 2 && (
          <div className="gallery-filters">
            {screenLabels.map((label) => (
              <button
                key={label}
                className={`filter-chip ${filter === label ? 'active' : ''}`}
                onClick={() => setFilter(label)}
              >
                {label === 'all' ? '🖼️ All' : label}
              </button>
            ))}
          </div>
        )}

        {/* ── Grid ─────────────────────────────────────── */}
        {filteredScreenshots.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📭</div>
            <h3>No Screenshots Yet</h3>
            <p>Start a crawl session to capture app screenshots automatically.</p>
          </div>
        ) : (
          <div className="gallery-grid">
            {filteredScreenshots.map((ss, i) => (
              <div
                className="screenshot-card"
                key={ss.filename}
                onClick={() => setLightbox(ss)}
              >
                <img
                  src={screenshotUrl(crawlId, ss.filename)}
                  alt={ss.screen_label || `Step ${ss.step_number}`}
                  loading="lazy"
                />
                <div className="card-overlay">
                  <div className="label">{ss.screen_label || 'Unknown'}</div>
                  <div className="step">Step {ss.step_number} · {ss.action_taken}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Lightbox ─────────────────────────────────── */}
        {lightbox && (
          <div className="lightbox" onClick={() => setLightbox(null)}>
            <button className="lightbox-close" onClick={() => setLightbox(null)}>✕</button>
            <img
              src={screenshotUrl(crawlId, lightbox.filename)}
              alt={lightbox.screen_label}
              onClick={(e) => e.stopPropagation()}
            />
            <div className="lightbox-info" onClick={(e) => e.stopPropagation()}>
              <div className="label">{lightbox.screen_label || 'Unknown Screen'}</div>
              {lightbox.ai_reasoning && (
                <div className="reasoning">🧠 {lightbox.ai_reasoning}</div>
              )}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                Step {lightbox.step_number} · Action: {lightbox.action_taken}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
