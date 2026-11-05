// The pages and their addresses. Every page sits inside the Shell (menu + top bar).
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Shell } from "./components/Shell";
import { PAGES } from "./nav";
import { Log } from "./pages/Log";
import { Settings } from "./pages/Settings";
import { Soon } from "./pages/Soon";
import { StatusProvider } from "./status";

const READY: Record<string, () => React.ReactElement> = { "/log": () => <Log />, "/settings": () => <Settings /> };

export default function App() {
  return (
    <StatusProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            {PAGES.map((p) => (
              <Route key={p.path} path={p.path} element={READY[p.path]?.() ?? <Soon page={p} />} />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StatusProvider>
  );
}
