import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import CampaignPage from './pages/Campaign/CampaignPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/campaign" replace />} />
        <Route path="/campaign" element={<CampaignPage />} />
        <Route path="*" element={<Navigate to="/campaign" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
