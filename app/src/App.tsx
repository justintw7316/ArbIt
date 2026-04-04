import { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import TabBar from './components/TabBar';
import StatusBar from './components/StatusBar';
import SignalsPage from './pages/SignalsPage';
import MarketsPage from './pages/MarketsPage';
import PipelinePage from './pages/PipelinePage';
import SimulationPage from './pages/SimulationPage';
import { api } from './lib/api';
import type { AppConfig } from './lib/types';

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState(false);
  const [candidateCount, setCandidateCount] = useState(0);

  useEffect(() => {
    api.getConfig()
      .then(setConfig)
      .catch(() => setConfigError(true));

    api.getCandidates()
      .then((c) => setCandidateCount(c.length))
      .catch(() => {});
  }, []);

  return (
    <div className="flex flex-col h-screen bg-bg">
      <TabBar candidateCount={candidateCount} isLive={config?.db_status === 'connected'} />
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/signals" replace />} />
          <Route path="/signals" element={<SignalsPage />} />
          <Route path="/markets" element={<MarketsPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/simulation" element={<SimulationPage />} />
        </Routes>
      </main>
      <StatusBar config={config} error={configError} />
    </div>
  );
}
