// The pages and their addresses. Every page sits inside the Shell (menu + top bar).
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Shell } from "./components/Shell";
import { PAGES } from "./nav";
import { Log } from "./pages/Log";
import { People } from "./pages/People";
import { Settings } from "./pages/Settings";
import { Soon } from "./pages/Soon";
import { Spinner } from "./components/ui";
import { StatusProvider } from "./status";

// The schedule page carries FullCalendar (~250 KB), so it loads only when you open it.
const Schedule = lazy(() => import("./pages/Schedule").then((m) => ({ default: m.Schedule })));

const READY: Record<string, () => React.ReactElement> = { "/people": () => <People />, "/schedule": () => <Suspense fallback={<Spinner />}><Schedule /></Suspense>, "/log": () => <Log />, "/settings": () => <Settings /> };

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
