import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom';
import AdminDocumentsPage from './pages/AdminDocumentsPage';
import DocumentDetailPage from './pages/DocumentDetailPage';
import ChatPage from './pages/ChatPage';
import axios from 'axios';
import { 
  MessageSquare, Layers, Menu, Plus, ChevronLeft, 
  Trash2, HelpCircle, FileText, CheckCircle2,
  AlertTriangle, Clock, RefreshCw, Sparkles, FolderKanban
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 768);
  const [chatHistory, setChatHistory] = useState([]);
  const [historyLimit, setHistoryLimit] = useState(10);
  const [activeLogId, setActiveLogId] = useState(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const navigate = useNavigate();
  const location = useLocation();

  // Watch screen resize for mobile threshold
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Track the currently active log ID from the search query params
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const logId = params.get('log_id');
    if (logId) {
      setActiveLogId(logId);
    }
  }, [location]);

  const fetchChatHistory = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/chat/`);
      setChatHistory(res.data);
    } catch (err) {
      console.error("Error fetching chat logs:", err);
    }
  };

  useEffect(() => {
    fetchChatHistory();
    const interval = setInterval(fetchChatHistory, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleNewChat = () => {
    setActiveLogId(null);
    navigate('/chat');
    if (isMobile) setSidebarOpen(false);
    // Dispatch a custom event to tell ChatPage to clear state if it's already on /chat
    window.dispatchEvent(new Event('new-chat-triggered'));
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#212121', color: '#e3e3e3', position: 'relative' }}>
      
      {/* Mobile Backdrop Overlay */}
      {isMobile && sidebarOpen && (
        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Collapsible Sidebar */}
      <aside className={`chatgpt-sidebar ${sidebarOpen ? '' : 'closed'}`} style={{ 
        width: sidebarOpen ? '260px' : '0px', 
        minWidth: sidebarOpen ? '260px' : '0px', 
        overflowX: 'hidden'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '12px', width: '236px' }}>
          
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', padding: '0 4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }} onClick={() => navigate('/chat')}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 'bold',
                color: '#fff',
                fontSize: '0.85rem'
              }}>G</div>
              <span style={{ fontWeight: 600, fontSize: '0.95rem', color: '#eceecf' }}>GraphRAG AI</span>
            </div>
            
            <button className="chatgpt-btn-icon" onClick={() => setSidebarOpen(false)}>
              <ChevronLeft className="w-4 h-4" />
            </button>
          </div>

          {/* New Chat Button */}
          <button 
            onClick={handleNewChat}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              padding: '10px 14px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              background: 'transparent',
              color: '#f9f9f9',
              fontSize: '0.9rem',
              fontWeight: 500,
              cursor: 'pointer',
              marginBottom: '20px',
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Plus className="w-4 h-4" />
              Đoạn chat mới
            </span>
          </button>

          {/* Navigation Links */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '24px' }}>
            <NavLink 
              to={activeLogId ? `/chat?log_id=${activeLogId}` : "/chat"} 
              className={({ isActive }) => `chatgpt-sidebar-item ${isActive ? 'active' : ''}`}
              style={{ textDecoration: 'none' }}
              onClick={() => { if (isMobile) setSidebarOpen(false); }}
            >
              <MessageSquare className="w-4 h-4" />
              Trợ lý AI
            </NavLink>
            <NavLink 
              to="/" 
              className={({ isActive }) => `chatgpt-sidebar-item ${isActive ? 'active' : ''}`}
              style={{ textDecoration: 'none' }}
              onClick={() => { if (isMobile) setSidebarOpen(false); }}
            >
              <FolderKanban className="w-4 h-4" />
              Quản lý tài liệu
            </NavLink>
          </div>

          {/* Recent Chats Section */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto', gap: '4px', minHeight: 0 }}>
            <div style={{ 
              fontSize: '0.75rem', 
              fontWeight: 600, 
              color: '#8e8e8e', 
              padding: '0 8px 8px 8px', 
              borderBottom: '1px solid rgba(255, 255, 255, 0.05)', 
              marginBottom: '8px' 
            }}>
              Lịch sử đối thoại
            </div>
            
            {chatHistory.length === 0 ? (
              <div style={{ padding: '16px 8px', fontSize: '0.8rem', color: '#666', textAlign: 'center' }}>
                Chưa có đoạn chat nào
              </div>
            ) : (
              <>
                {chatHistory.slice(0, historyLimit).map((chat) => {
                  const isActive = location.search.includes(`log_id=${chat.id}`);
                  return (
                    <div 
                      key={chat.id} 
                      onClick={() => {
                        navigate(`/chat?log_id=${chat.id}`);
                        if (isMobile) setSidebarOpen(false);
                      }}
                      className={`chatgpt-sidebar-item ${isActive ? 'active' : ''}`}
                      style={{ 
                        whiteSpace: 'nowrap', 
                        overflow: 'hidden', 
                        textOverflow: 'ellipsis',
                        fontSize: '0.85rem',
                        display: 'block',
                        padding: '10px 12px',
                        flexShrink: 0
                      }}
                      title={chat.question}
                    >
                      {chat.question}
                    </div>
                  );
                })}
                {chatHistory.length > historyLimit && (
                  <button
                    onClick={() => setHistoryLimit(prev => prev + 10)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#10b981',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      padding: '8px',
                      textAlign: 'center',
                      width: '100%',
                      marginTop: '4px',
                      borderRadius: '6px',
                      transition: 'background-color 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.03)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    Xem thêm...
                  </button>
                )}
              </>
            )}
          </div>

          {/* User profile / Footer */}
          <div style={{ 
            marginTop: 'auto', 
            paddingTop: '12px', 
            borderTop: '1px solid rgba(255, 255, 255, 0.05)', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '10px' 
          }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              color: '#fff',
              fontSize: '0.9rem'
            }}>D</div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f9f9f9' }}>Dion Plus</span>
              <span style={{ fontSize: '0.7rem', color: '#8e8e8e' }}>Chế độ Trợ lý RAG</span>
            </div>
          </div>

        </div>
      </aside>

      {/* Toggle Button when Sidebar is closed */}
      {!sidebarOpen && (
        <button 
          className="chatgpt-btn-icon" 
          onClick={() => setSidebarOpen(true)}
          style={{ 
            position: 'fixed', 
            top: '12px', 
            left: '12px', 
            zIndex: 100, 
            backgroundColor: '#2f2f2f', 
            border: '1px solid rgba(255, 255, 255, 0.05)' 
          }}
        >
          <Menu className="w-4 h-4" />
        </button>
      )}

      {/* Main Content Area */}
      <main className="chatgpt-main" style={{ flex: 1, paddingLeft: !sidebarOpen ? '12px' : '0px' }}>

        {/* Dynamic Route views */}
        <div style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
          <Routes>
            <Route path="/" element={<AdminDocumentsPage />} />
            <Route path="/documents/:id" element={<DocumentDetailPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </div>

      </main>

    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}
