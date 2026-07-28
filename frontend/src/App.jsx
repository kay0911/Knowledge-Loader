import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom';
import AdminDocumentsPage from './pages/AdminDocumentsPage';
import DocumentDetailPage from './pages/DocumentDetailPage';
import ChatPage from './pages/ChatPage';
import axios from 'axios';
import { 
  MessageSquare, Layers, Menu, Plus, ChevronLeft, 
  Trash2, HelpCircle, FileText, CheckCircle2,
  AlertTriangle, Clock, RefreshCw, Sparkles, FolderKanban,
  Sun, Moon
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 768);
  const [chatHistory, setChatHistory] = useState([]);
  const [historyLimit, setHistoryLimit] = useState(10);
  const [activeLogId, setActiveLogId] = useState(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (theme === 'light') {
      document.body.classList.add('light-theme');
    } else {
      document.body.classList.remove('light-theme');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

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

  // Track the currently active session ID from the search query params
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const sessionId = params.get('session_id');
    if (sessionId) {
      setActiveLogId(sessionId);
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
    
    // Listen to custom event when a chat session is created or updated
    const handleHistoryUpdate = () => fetchChatHistory();
    window.addEventListener('chat-history-updated', handleHistoryUpdate);

    // Light fallback sync every 60 seconds (instead of 5 seconds) to reduce server load
    const interval = setInterval(fetchChatHistory, 60000);
    return () => {
      window.removeEventListener('chat-history-updated', handleHistoryUpdate);
      clearInterval(interval);
    };
  }, []);

  const handleNewChat = () => {
    setActiveLogId(null);
    navigate('/chat');
    if (isMobile) setSidebarOpen(false);
    // Dispatch a custom event to tell ChatPage to clear state if it's already on /chat
    window.dispatchEvent(new Event('new-chat-triggered'));
  };

  const handleDeleteSession = async (sessionId, e) => {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    if (!sessionId) return;
    if (!window.confirm("Bạn có chắc chắn muốn xóa đoạn đối thoại này khỏi lịch sử không?")) return;
    
    try {
      await axios.delete(`${API_BASE_URL}/chat/session/${sessionId}`);
      setChatHistory(prev => prev.filter(item => String(item.session_id) !== String(sessionId)));
      if (location.search.includes(`session_id=${sessionId}`)) {
        navigate('/chat');
        window.dispatchEvent(new Event('new-chat-triggered'));
      }
    } catch (err) {
      console.error("Delete chat session error:", err);
      alert(err.response?.data?.detail || "Không thể xóa đoạn đối thoại này.");
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--main-bg)', color: 'var(--text-color)', position: 'relative' }}>
      
      {/* Mobile Backdrop Overlay */}
      {isMobile && sidebarOpen && (
        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Collapsible Sidebar */}
      <aside className={`chatgpt-sidebar ${sidebarOpen ? '' : 'closed'}`} style={{ 
        width: sidebarOpen ? '260px' : '0px', 
        minWidth: sidebarOpen ? '260px' : '0px', 
        maxWidth: sidebarOpen ? '260px' : '0px',
        flexShrink: 0,
        boxSizing: 'border-box',
        overflow: 'hidden'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '12px', width: '260px', maxWidth: '260px', boxSizing: 'border-box', overflowX: 'hidden' }}>
          
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
              <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-color)' }}>GraphRAG AI</span>
            </div>
            
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                className="chatgpt-btn-icon" 
                onClick={toggleTheme}
                title={theme === 'dark' ? 'Chuyển sang Chế độ sáng' : 'Chuyển sang Chế độ tối'}
              >
                {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <button className="chatgpt-btn-icon" onClick={() => setSidebarOpen(false)}>
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>
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
              border: '1px solid var(--sidebar-border)',
              background: 'transparent',
              color: 'var(--text-color)',
              fontSize: '0.9rem',
              fontWeight: 500,
              cursor: 'pointer',
              marginBottom: '20px',
              transition: 'background-color 0.2s, border-color 0.2s, color 0.2s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--sidebar-item-hover)'}
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
              to={activeLogId ? `/chat?session_id=${activeLogId}` : "/chat"} 
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
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto', gap: '4px', minHeight: 0, width: '100%', boxSizing: 'border-box' }}>
            <div style={{ 
              fontSize: '0.75rem', 
              fontWeight: 600, 
              color: 'var(--text-light)', 
              padding: '0 8px 8px 8px', 
              borderBottom: '1px solid var(--sidebar-border)', 
              marginBottom: '8px' 
            }}>
              Lịch sử đối thoại
            </div>
            
            {chatHistory.length === 0 ? (
              <div style={{ padding: '16px 8px', fontSize: '0.8rem', color: 'var(--text-light)', textAlign: 'center' }}>
                Chưa có đoạn chat nào
              </div>
            ) : (
              <>
                {chatHistory.slice(0, historyLimit).map((chat) => {
                  const isActive = location.search.includes(`session_id=${chat.session_id}`);
                  return (
                    <div 
                      key={chat.id} 
                      onClick={() => {
                        navigate(`/chat?session_id=${chat.session_id}`);
                        if (isMobile) setSidebarOpen(false);
                      }}
                      className={`chatgpt-sidebar-item ${isActive ? 'active' : ''}`}
                      style={{ 
                        fontSize: '0.85rem',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 10px',
                        flexShrink: 0,
                        maxWidth: '100%',
                        boxSizing: 'border-box',
                        gap: '6px'
                      }}
                      title={chat.question}
                    >
                      <span style={{ 
                        flex: 1, 
                        whiteSpace: 'nowrap', 
                        overflow: 'hidden', 
                        textOverflow: 'ellipsis' 
                      }}>
                        {chat.question}
                      </span>
                      
                      <button
                        onClick={(e) => handleDeleteSession(chat.session_id, e)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--text-light)',
                          cursor: 'pointer',
                          padding: '4px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: '4px',
                          transition: 'all 0.2s',
                          opacity: 0.7,
                          flexShrink: 0
                        }}
                        title="Xóa đoạn chat này"
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = '#ef4444';
                          e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.15)';
                          e.currentTarget.style.opacity = '1';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = 'var(--text-light)';
                          e.currentTarget.style.backgroundColor = 'transparent';
                          e.currentTarget.style.opacity = '0.7';
                        }}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
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
            borderTop: '1px solid var(--sidebar-border)', 
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
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-color)' }}>Dion Plus</span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-light)' }}>Chế độ Trợ lý RAG</span>
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
            backgroundColor: 'var(--input-bg)', 
            border: '1px solid var(--sidebar-border)',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)'
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
