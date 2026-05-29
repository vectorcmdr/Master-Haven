import { useEffect, useRef } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Nav from './components/Nav.jsx'
import Footer from './components/Footer.jsx'
import Main from './pages/Main.jsx'
import About from './pages/About.jsx'
import Lore from './pages/Lore.jsx'
import WhosGoing from './pages/WhosGoing.jsx'
import SubmitCiv from './pages/SubmitCiv.jsx'
import SignUp from './pages/SignUp.jsx'
import Admin from './pages/Admin.jsx'
import Splash from './components/Splash.jsx'

// Smooth scroll-to-top on every route change (mockup did this in showPage()),
// plus a GA4 page_view for SPA navigations. The initial page_view is sent by
// gtag('config') in index.html, so we skip the first run here to avoid a double.
function ScrollToTop() {
  const { pathname } = useLocation()
  const firstRun = useRef(true)
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    if (firstRun.current) {
      firstRun.current = false
      return
    }
    if (typeof window.gtag === 'function') {
      window.gtag('event', 'page_view', {
        page_path: pathname + window.location.search,
        page_location: window.location.href,
        page_title: document.title,
      })
    }
  }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <Splash />
      <Nav />
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<Main />} />
        <Route path="/about" element={<About />} />
        <Route path="/lore" element={<Lore />} />
        <Route path="/whos-going" element={<WhosGoing />} />
        <Route path="/whos-going/submit" element={<SubmitCiv />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<Main />} />
      </Routes>
      <Footer />
    </>
  )
}
