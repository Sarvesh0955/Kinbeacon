import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { Layout } from './components/layout/Layout';
import { OverviewPage } from './pages/OverviewPage';
import { ZonesPage } from './pages/ZonesPage';
import { AnchorsPage } from './pages/AnchorsPage';
import { DevicesPage } from './pages/DevicesPage';
import { SearchPage } from './pages/SearchPage';
import { HistoryPage } from './pages/HistoryPage';
import { FleetHealthPage } from './pages/FleetHealthPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 10000,
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<OverviewPage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="zones" element={<ZonesPage />} />
            <Route path="anchors" element={<AnchorsPage />} />
            <Route path="devices" element={<DevicesPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="fleet" element={<FleetHealthPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
    </QueryClientProvider>
  );
};

export default App;
