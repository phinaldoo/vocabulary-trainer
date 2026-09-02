import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuth } from './auth/AuthContext';
import { AppLayout } from './components/AppLayout';
import { AuthPage } from './pages/AuthPage';
import { AdminPage } from './pages/AdminPage';
import { DashboardPage } from './pages/DashboardPage';
import { LandingPage } from './pages/LandingPage';
import { LearnPage } from './pages/LearnPage';
import { ProgressPage } from './pages/ProgressPage';
import { SettingsPage } from './pages/SettingsPage';
import { VocabularyPage } from './pages/VocabularyPage';
import { useI18n } from './i18n';

function LoadingScreen() {
  const { t } = useI18n();
  return (
    <main className="center-screen" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{t('common.preparing')}</p>
    </main>
  );
}

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <LoadingScreen />;
  if (!user) {
    const from = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to="/anmelden" replace state={{ from }} />;
  }
  return <AppLayout>{children}</AppLayout>;
}

export function App() {
  return (
    <Routes>
      <Route path="/willkommen" element={<LandingPage />} />
      <Route path="/anmelden" element={<AuthPage />} />
      <Route path="/registrieren" element={<AuthPage register />} />
      <Route path="/" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/lernen" element={<Protected><LearnPage /></Protected>} />
      <Route path="/vokabeln" element={<Protected><VocabularyPage /></Protected>} />
      <Route path="/fortschritt" element={<Protected><ProgressPage /></Protected>} />
      <Route path="/einstellungen" element={<Protected><SettingsPage /></Protected>} />
      <Route path="/admin" element={<Protected><AdminPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
