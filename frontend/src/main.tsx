import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import './index.css'
import App from './App'

// HashRouter (URLs like /#/academic) instead of BrowserRouter so the backend
// can serve this app from a single port. Page routes (/academic, /projects,
// /mail) overlap with API routes of the same name; keeping client routing in
// the URL hash means the server only ever serves "/" for HTML and never
// confuses a page refresh with an API call.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>,
)
