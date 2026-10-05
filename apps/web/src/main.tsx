import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './i18n';
import './index.css';
import { NavProvider } from './nav';
import { SessionProvider } from './session';
import { LandingPage } from './pages/LandingPage';
import { StudioPage } from './pages/StudioPage';

function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/:lang" element={<LandingPage />} />
        <Route path="/:lang/studio" element={<StudioPage />} />
        <Route path="/" element={<Navigate to="/en" replace />} />
        <Route path="*" element={<Navigate to="/en" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <NavProvider>
      <SessionProvider>
        <AppRouter />
      </SessionProvider>
    </NavProvider>
  </StrictMode>,
);
