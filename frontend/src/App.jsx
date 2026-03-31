import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import Home from './pages/Home'
import CrawlSession from './pages/CrawlSession'
import Gallery from './pages/Gallery'

function Navbar() {
  const location = useLocation()

  return (
    <nav className="navbar">
      <div className="container">
        <Link to="/" className="navbar-brand">
          AppCrawlr
        </Link>
        <div className="navbar-links">
          <Link to="/" className={`btn btn-sm ${location.pathname === '/' ? 'btn-primary' : 'btn-secondary'}`}>
            Home
          </Link>
        </div>
      </div>
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/crawl/:crawlId" element={<CrawlSession />} />
        <Route path="/gallery/:crawlId" element={<Gallery />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
