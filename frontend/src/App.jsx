import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import AdminDocumentsPage from './pages/AdminDocumentsPage';
import DocumentDetailPage from './pages/DocumentDetailPage';
import ChatPage from './pages/ChatPage';

function App() {
  return (
    <Router>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        {/* Glassmorphic Navigation Bar */}
        <header className="glass-panel" style={{
          position: 'sticky',
          top: 0,
          zIndex: 1000,
          margin: '16px 24px 8px 24px',
          padding: '12px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderRadius: '16px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.2)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              color: '#fff',
              boxShadow: '0 0 12px rgba(99, 102, 241, 0.4)'
            }}>G</div>
            <span style={{ fontWeight: 700, fontSize: '1.2rem', letterSpacing: '-0.025em' }} className="gradient-text">
              GraphRAG Loader
            </span>
          </div>
          
          <nav style={{ display: 'flex', gap: '8px' }}>
            <NavLink
              to="/"
              end
              style={({ isActive }) => ({
                padding: '8px 16px',
                borderRadius: '8px',
                textDecoration: 'none',
                fontSize: '0.9rem',
                fontWeight: 500,
                color: isActive ? '#fff' : '#94a3b8',
                background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                border: isActive ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid transparent',
                transition: 'all 0.2s ease-in-out'
              })}
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/chat"
              style={({ isActive }) => ({
                padding: '8px 16px',
                borderRadius: '8px',
                textDecoration: 'none',
                fontSize: '0.9rem',
                fontWeight: 500,
                color: isActive ? '#fff' : '#94a3b8',
                background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                border: isActive ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid transparent',
                transition: 'all 0.2s ease-in-out'
              })}
            >
              Trợ lý AI Chat
            </NavLink>
          </nav>
        </header>

        {/* Content Wrapper */}
        <main style={{ flex: 1, padding: '8px 24px 24px 24px', display: 'flex', flexDirection: 'column' }}>
          <Routes>
            <Route path="/" element={<AdminDocumentsPage />} />
            <Route path="/documents/:id" element={<DocumentDetailPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
