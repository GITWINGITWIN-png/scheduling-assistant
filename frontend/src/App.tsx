import { NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import Academic from './pages/Academic'
import Projects from './pages/Projects'
import Mail from './pages/Mail'
import { FloatingChat } from './components/Chat'

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded px-3 py-1.5 text-sm font-medium ${
          isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

// App shell: top nav + routed pages.
export default function App() {
  return (
    <div className="flex h-screen flex-col bg-gray-50 text-gray-900">
      <header className="flex items-center gap-4 border-b bg-white px-4 py-3">
        <span className="text-lg font-bold">my_secretary</span>
        <nav className="flex gap-1">
          <NavItem to="/" label="Home" />
          <NavItem to="/academic" label="Academic" />
          <NavItem to="/projects" label="Projects" />
          <NavItem to="/mail" label="Mail" />
        </nav>
      </header>
      <main className="min-h-0 flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/academic" element={<Academic />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/mail" element={<Mail />} />
        </Routes>
      </main>

      {/* One global chat for the whole app — mounted here so it persists across
          page navigation and is the same conversation everywhere. */}
      <FloatingChat />
    </div>
  )
}
