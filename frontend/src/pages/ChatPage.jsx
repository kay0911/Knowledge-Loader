import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { 
  Send, BookOpen, Clock, AlertTriangle, Layers, 
  Database, HelpCircle, ArrowRight, Sparkles, Plus, ArrowUp, RefreshCw
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const logId = searchParams.get('log_id');

  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeCitation, setActiveCitation] = useState(null);
  
  const messagesEndRef = useRef(null);

  // Load chat session if logId changes
  useEffect(() => {
    if (logId) {
      const loadLog = async () => {
        setLoading(true);
        try {
          const res = await axios.get(`${API_BASE_URL}/chat/${logId}`);
          setMessages([
            { sender: 'user', text: res.data.question },
            { sender: 'ai', text: res.data.answer, citations: res.data.citations || [] }
          ]);
        } catch (err) {
          console.error("Error loading chat detail:", err);
        } finally {
          setLoading(false);
        }
      };
      loadLog();
    } else {
      setMessages([]);
    }
    setActiveCitation(null);
  }, [logId]);

  // Listen to the custom event for "New Chat"
  useEffect(() => {
    const handleNewChat = () => {
      setSearchParams({});
      setMessages([]);
      setActiveCitation(null);
    };
    window.addEventListener('new-chat-triggered', handleNewChat);
    return () => window.removeEventListener('new-chat-triggered', handleNewChat);
  }, [setSearchParams]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!question.trim() || loading) return;

    const userQuestion = question.trim();
    setQuestion('');
    
    // Add User Message
    const userMsg = { sender: 'user', text: userQuestion };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userQuestion })
      });

      if (response.ok) {
        const data = await response.json();
        // Add AI Message with citations
        const aiMsg = {
          sender: 'ai',
          text: data.answer,
          citations: data.citations
        };
        setMessages(prev => [...prev, aiMsg]);
        // Update URL to match this new session log id
        if (data.chat_id) {
          setSearchParams({ log_id: data.chat_id });
        }
      } else {
        const errData = await response.json();
        const errorMsg = { sender: 'ai', text: `Lỗi: ${errData.detail || 'Không thể lấy phản hồi từ server.'}` };
        setMessages(prev => [...prev, errorMsg]);
      }
    } catch (err) {
      console.error(err);
      const errorMsg = { sender: 'ai', text: 'Lỗi kết nối tới máy chủ. Vui lòng kiểm tra lại dịch vụ backend.' };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestionClick = (desc) => {
    setQuestion(desc);
    // Submit query next tick to allow state update
    setTimeout(() => {
      const btn = document.getElementById('chatgpt-send-btn');
      if (btn) btn.click();
    }, 50);
  };

  const suggestions = [
    { title: "Quy định trang phục", desc: "Đi làm có được mặc quần đùi dép lê không?" },
    { title: "Cấp phát laptop", desc: "Nhân viên mới được cấp dòng máy gì?" },
    { title: "Thời gian bảo hành", desc: "Bảo hành xe VF9 là bao nhiêu năm?" },
    { title: "Quy trình hỗ trợ IT", desc: "Cài đặt phần mềm nội bộ liên hệ ai?" }
  ];

  // Helper function to render text and make citations [S1], [S2] clickable
  const renderMessageText = (text, citations = []) => {
    if (!text) return null;
    const parts = text.split(/(\[S\d+\])/g);
    
    return parts.map((part, idx) => {
      const match = part.match(/^\[S(\d+)\]$/);
      if (match) {
        const num = match[1];
        const citation = citations.find(c => c.source_id === `S${num}`);
        
        return (
          <button
            key={idx}
            onClick={() => setActiveCitation(citation || null)}
            style={{
              background: 'rgba(16, 185, 129, 0.2)',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              color: '#34d399',
              borderRadius: '6px',
              padding: '1px 6px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              margin: '0 3px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              verticalAlign: 'middle',
              transition: 'all 0.2s',
            }}
            title={citation ? `Xem nguồn: ${citation.file_name}` : 'Không tìm thấy thông tin nguồn'}
          >
            S{num}
          </button>
        );
      }
      return part;
    });
  };

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', position: 'relative' }}>
      
      {/* Main Chat Column */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, position: 'relative' }}>
        
        {/* Messages Stream */}
        <div style={{ 
          flex: 1, 
          overflowY: 'auto', 
          padding: '24px 0 160px 0', 
          display: 'flex', 
          flexDirection: 'column', 
          minHeight: 0 
        }}>
          {messages.length === 0 ? (
            // Welcome Page (ChatGPT Style Empty State)
            <div className="fade-in" style={{
              maxWidth: '720px',
              width: '90%',
              margin: 'auto',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '40px',
              padding: '40px 0'
            }}>
              
              {/* Bot Avatar Icon */}
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 8px 24px rgba(16, 185, 129, 0.3)',
                color: '#fff'
              }}>
                <Sparkles className="w-8 h-8" />
              </div>

              <h2 style={{ fontSize: '1.8rem', fontWeight: 600, color: '#f9f9f9', margin: 0, textAlign: 'center' }}>
                Hôm nay tôi có thể giúp gì cho bạn?
              </h2>

              {/* Suggestions Cards Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                gap: '12px',
                width: '100%'
              }}>
                {suggestions.map((card, idx) => (
                  <div 
                    key={idx}
                    className="chatgpt-suggestion-card"
                    onClick={() => handleSuggestionClick(card.desc)}
                  >
                    <div className="chatgpt-suggestion-title">{card.title}</div>
                    <div className="chatgpt-suggestion-desc">{card.desc}</div>
                  </div>
                ))}
              </div>

            </div>
          ) : (
            // Messages Rows list
            messages.map((msg, index) => (
              <div 
                key={index}
                className={`chatgpt-message-row ${msg.sender === 'user' ? 'user' : 'assistant'} fade-in`}
              >
                <div className="chatgpt-message-content">
                  <div className={`chatgpt-avatar ${msg.sender === 'user' ? 'user' : 'assistant'}`}>
                    {msg.sender === 'user' ? 'U' : 'AI'}
                  </div>
                  <div className="chatgpt-text">
                    <div style={{ whiteSpace: 'pre-wrap' }}>
                      {msg.sender === 'user' ? msg.text : renderMessageText(msg.text, msg.citations)}
                    </div>

                    {/* Inline lists of citations under AI Response */}
                    {msg.sender === 'ai' && msg.citations && msg.citations.length > 0 && (
                      <div style={{
                        marginTop: '16px',
                        paddingTop: '12px',
                        borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '6px',
                        alignItems: 'center'
                      }}>
                        <span style={{ fontSize: '0.75rem', color: '#64748b', marginRight: '4px' }}>Nguồn tài liệu:</span>
                        {msg.citations.map((cit, idx) => (
                          <button
                            key={idx}
                            onClick={() => setActiveCitation(cit)}
                            className="chatgpt-citation-tag"
                          >
                            <BookOpen className="w-3 h-3" />
                            [{cit.source_id}] {cit.file_name}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
          
          {/* Loading Indicator */}
          {loading && (
            <div className="chatgpt-message-row assistant fade-in">
              <div className="chatgpt-message-content">
                <div className="chatgpt-avatar assistant">AI</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#8e8e8e', fontSize: '0.9rem' }}>
                  <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
                  Đang truy xuất kiến thức & tổng hợp câu trả lời...
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar Section */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          background: 'linear-gradient(to top, #212121 70%, transparent 100%)',
          padding: '24px 0',
          zIndex: 10
        }}>
          <form onSubmit={handleSubmit} className="chatgpt-input-container">
            {/* Direct Upload button styled into input bar */}
            <button 
              type="button" 
              className="chatgpt-btn-icon"
              title="Tải tài liệu trực tiếp"
              onClick={() => navigate('/')}
            >
              <Plus className="w-4 h-4" />
            </button>

            <input 
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Nhập câu hỏi của bạn tại đây... (Ví dụ: Bảo hành VF9)"
              disabled={loading}
              className="chatgpt-input"
            />

            <button 
              type="submit" 
              id="chatgpt-send-btn"
              disabled={loading || !question.trim()}
              className="chatgpt-btn-icon"
              style={{
                backgroundColor: loading || !question.trim() ? 'transparent' : '#10b981',
                color: loading || !question.trim() ? '#4b4b4b' : '#fff'
              }}
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </form>
          
          <div style={{ fontSize: '0.7rem', color: '#555', textAlign: 'center', marginTop: '8px' }}>
            Hệ thống GraphRAG sử dụng lai ghép vectơ (Hybrid Search) kết hợp trích xuất thực thể đồ thị Neo4j.
          </div>
        </div>

      </div>

      {/* Citations Side Drawer (Collapsible right panel) */}
      {activeCitation && (
        <div className="glass-panel" style={{
          width: '320px',
          padding: '24px',
          borderLeft: '1px solid rgba(255, 255, 255, 0.05)',
          background: '#171717',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          height: '100%',
          position: 'relative',
          animation: 'fadeIn 0.2s ease-out',
          zIndex: 20
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: '#f1f5f9' }}>
              Trích dẫn [{activeCitation.source_id}]
            </h4>
            <button
              onClick={() => setActiveCitation(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#8e8e8e',
                fontSize: '1.1rem',
                cursor: 'pointer',
                padding: '4px'
              }}
            >
              ✕
            </button>
          </div>
          
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '4px' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#8e8e8e', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Tài liệu nguồn</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 500, color: '#cbd5e1' }}>{activeCitation.file_name}</div>
            </div>

            {activeCitation.page_number && (
              <div>
                <div style={{ fontSize: '0.75rem', color: '#8e8e8e', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Trang số</div>
                <div style={{ fontSize: '0.9rem', color: '#cbd5e1' }}>Trang {activeCitation.page_number}</div>
              </div>
            )}

            {activeCitation.heading && (
              <div>
                <div style={{ fontSize: '0.75rem', color: '#8e8e8e', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Mục tiêu đề</div>
                <div style={{ fontSize: '0.85rem', color: '#a5b4fc', fontFamily: 'monospace', background: 'rgba(99, 102, 241, 0.1)', padding: '4px 8px', borderRadius: '4px', display: 'inline-block' }}>{activeCitation.heading}</div>
              </div>
            )}

            {activeCitation.sheet_name && (
              <div>
                <div style={{ fontSize: '0.75rem', color: '#8e8e8e', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Bảng tính Excel</div>
                <div style={{ fontSize: '0.9rem', color: '#cbd5e1' }}>
                  Sheet: <strong>{activeCitation.sheet_name}</strong> (Dòng {activeCitation.row_start} - {activeCitation.row_end})
                </div>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: '150px' }}>
              <div style={{ fontSize: '0.75rem', color: '#8e8e8e', marginBottom: '6px', textTransform: 'uppercase', fontWeight: 600 }}>Nội dung đoạn trích</div>
              <div style={{
                flex: 1,
                fontSize: '0.825rem',
                lineHeight: '1.6',
                color: '#94a3b8',
                background: 'rgba(0, 0, 0, 0.3)',
                padding: '16px',
                borderRadius: '12px',
                border: '1px solid rgba(255, 255, 255, 0.03)',
                whiteSpace: 'pre-wrap',
                overflowY: 'auto'
              }}>
                "{activeCitation.snippet}"
              </div>
            </div>
          </div>
        </div>
      )}
      
    </div>
  );
}

export default ChatPage;
