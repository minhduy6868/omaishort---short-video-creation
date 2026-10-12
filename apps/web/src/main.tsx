import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import App from "./App";
import { SUPPORTED_LANGS, type SupportedLang } from "./i18n";
import "./i18n";
import "./index.css";
import { useNav, NavProvider } from "./nav";
import { LandingPage } from "./pages/LandingPage";
import { SessionProvider } from "./session";
const STUDIO_PATHS = ["/login", "/register", "/work", "/drama", "/news", "/knowledge", "/account"];

function NavSync() {
  const location = useLocation();
  const { go } = useNav();
  useEffect(() => {
    go(`${location.pathname}${location.search}`);
  }, [go, location.pathname, location.search]);
  return null;
}

function LandingRoute() {
  const { lang } = useParams();
  if (!lang || !SUPPORTED_LANGS.includes(lang as SupportedLang)) {
    return <Navigate to="/work" replace />;
  }
  return <LandingPage />;
}

function AppRouter() {
  return (
    <BrowserRouter>
      <NavSync />
      <Routes>
        <Route path="/" element={<App />} />
        {STUDIO_PATHS.map((path) => (
          <Route key={path} path={path} element={<App />} />
        ))}
        <Route path="/watch/:id" element={<App />} />
        <Route path="/:lang/studio" element={<Navigate to="/work" replace />} />
        <Route path="/:lang" element={<LandingRoute />} />
        <Route path="*" element={<Navigate to="/work" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <NavProvider>
      <SessionProvider>
        <AppRouter />
      </SessionProvider>
    </NavProvider>
  </StrictMode>,
);
