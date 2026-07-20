import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import AdminDocumentsPage from './pages/AdminDocumentsPage';
import DocumentDetailPage from './pages/DocumentDetailPage';

function App() {
  return (
    <Router>
      <div style={{ minHeight: '100vh', background: 'transparent' }}>
        <Routes>
          <Route path="/" element={<AdminDocumentsPage />} />
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
