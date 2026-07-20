import React, { useState, useEffect, useRef } from 'react';

function ChatPage() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeCitation, setActiveCitation] = useState(null);
  
  const messagesEndRef = useRef(null);

  // Fetch chat logs history on mount
  useEffect(() => {
    fetchHistory();
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const fetchHistory = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat/');
      if (response.ok) {
        const data = await response.json();
        setHistory(data);
      }
    } catch (err) {
      console.error('Failed to fetch chat logs:', err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    const userQuestion = question.trim();
    setQuestion('');
    
    // Add User Message
    const userMsg = { sender: 'user', text: userQuestion };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat/', {
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
        fetchHistory(); // Refresh history panel
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

  const loadPastSession = (log) => {
    const userMsg = { sender: 'user', text: log.question };
    const aiMsg = {
      sender: 'ai',
      text: log.answer || 'Không có câu trả lời nào được ghi lại.',
      citations: log.citations || []
    };
    setMessages([userMsg, aiMsg]);
    setActiveCitation(null);
  };

  // Helper function to render text and make citations [S1], [S2] clickable
  const renderMessageText = (text, citations = []) => {
    if (!text) return null;
    
    // Regex matches [S1], [S2] etc.
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
              background: 'rgba(99, 102, 241, 0.25)',
              border: '1px solid rgba(99, 102, 241, 0.5)',
              color: '#a5b4fc',
              borderRadius: '4px',
              padding: '1px 6px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              margin: '0 2px',
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
    <div style={{ display: 'flex', gap: '20px', flex: 1, minHeight: 'calc(100vh - 120px)' }}>
      {/* History Panel */}
      <div className="glass-panel" style={{
        width: '280px',
        display: 'flex',
        flexDirection: 'column',
        padding: '16px',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        maxHeight: 'calc(100vh - 120px)'
      }}>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '1rem', fontWeight: 600, color: '#f1f5f9' }}>Lịch sử đối thoại</h3>
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {history.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', marginTop: '20px' }}>Chưa có cuộc trò chuyện nào</div>
          ) : (
            history.map((log) => (
              <button
                key={log.id}
                onClick={() => loadPastSession(log)}
                style={{
                  textAlign: 'left',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid rgba(255, 255, 255, 0.05)',
                  borderRadius: '8px',
                  padding: '10px 12px',
                  color: '#94a3b8',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  width: '100%',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.background = 'rgba(99, 102, 241, 0.1)';
                  e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.2)';
                  e.currentTarget.style.color = '#e2e8f0';
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)';
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.05)';
                  e.currentTarget.style.color = '#94a3b8';
                }}
              >
                {log.question}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Stream */}
      <div className="glass-panel" style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        padding: '20px',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        position: 'relative',
        maxHeight: 'calc(100vh - 120px)'
      }}>
        {/* Messages List */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          paddingRight: '8px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          marginBottom: '20px'
        }}>
          {messages.length === 0 ? (
            <div style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#64748b',
              textAlign: 'center',
              gap: '12px'
            }}>
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: 'rgba(99, 102, 241, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.8rem',
                color: '#6366f1'
              }}>🤖</div>
              <div>
                <h3 style={{ margin: '0 0 4px 0', color: '#cbd5e1' }}>Tôi có thể giúp gì cho bạn?</h3>
                <p style={{ margin: 0, fontSize: '0.85rem' }}>Hỏi tôi bất cứ câu hỏi nào liên quan đến các tài liệu chính sách bảo hành, hướng dẫn sửa chữa đã tải lên.</p>
              </div>
            </div>
          ) : (
            messages.map((msg, index) => (
              <div
                key={index}
                style={{
                  display: 'flex',
                  justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start'
                }}
              >
                <div style={{
                  maxWidth: '75%',
                  padding: '12px 16px',
                  borderRadius: '12px',
                  lineHeight: '1.6',
                  fontSize: '0.9rem',
                  background: msg.sender === 'user' ? '#4f46e5' : 'rgba(255, 255, 255, 0.03)',
                  border: msg.sender === 'user' ? 'none' : '1px solid rgba(255, 255, 255, 0.05)',
                  color: msg.sender === 'user' ? '#ffffff' : '#e2e8f0',
                  boxShadow: msg.sender === 'user' ? '0 4px 12px rgba(79, 70, 229, 0.3)' : 'none',
                  whiteSpace: 'pre-wrap'
                }}>
                  {msg.sender === 'user' ? msg.text : renderMessageText(msg.text, msg.citations)}
                  
                  {/* Inline list of citations under response */}
                  {msg.sender === 'ai' && msg.citations && msg.citations.length > 0 && (
                    <div style={{
                      marginTop: '12px',
                      paddingTop: '10px',
                      borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '8px'
                    }}>
                      <span style={{ fontSize: '0.75rem', color: '#64748b', alignSelf: 'center' }}>Trích dẫn:</span>
                      {msg.citations.map((cit, idx) => (
                        <button
                          key={idx}
                          onClick={() => setActiveCitation(cit)}
                          style={{
                            background: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid rgba(255, 255, 255, 0.1)',
                            borderRadius: '6px',
                            padding: '3px 8px',
                            fontSize: '0.75rem',
                            color: '#94a3b8',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                          }}
                          onMouseOver={(e) => {
                            e.currentTarget.style.background = 'rgba(99, 102, 241, 0.15)';
                            e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.3)';
                            e.currentTarget.style.color = '#a5b4fc';
                          }}
                          onMouseOut={(e) => {
                            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                            e.currentTarget.style.color = '#94a3b8';
                          }}
                        >
                          [{cit.source_id}] {cit.file_name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          
          {loading && (
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <div style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                padding: '12px 16px',
                borderRadius: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: '#64748b',
                fontSize: '0.85rem'
              }}>
                <span className="spinner" style={{
                  display: 'inline-block',
                  width: '12px',
                  height: '12px',
                  border: '2px solid rgba(99, 102, 241, 0.3)',
                  borderTopColor: '#6366f1',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite'
                }}></span>
                Đang tìm kiếm thông tin và tổng hợp câu trả lời...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px' }}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Nhập câu hỏi của bạn tại đây... (Ví dụ: Quy trình bảo hành pin xe VF5)"
            disabled={loading}
            style={{
              flex: 1,
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '10px',
              padding: '12px 16px',
              color: '#e2e8f0',
              fontSize: '0.9rem',
              outline: 'none',
              transition: 'all 0.2s',
            }}
            onFocus={(e) => e.target.style.borderColor = '#6366f1'}
            onBlur={(e) => e.target.style.borderColor = 'rgba(255, 255, 255, 0.08)'}
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            style={{
              background: loading || !question.trim() ? 'rgba(79, 70, 229, 0.5)' : '#4f46e5',
              color: '#ffffff',
              border: 'none',
              borderRadius: '10px',
              padding: '0 20px',
              fontWeight: 600,
              fontSize: '0.9rem',
              cursor: loading || !question.trim() ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              boxShadow: loading || !question.trim() ? 'none' : '0 4px 12px rgba(79, 70, 229, 0.3)'
            }}
          >
            Gửi
          </button>
        </form>
      </div>

      {/* Citations Drawer (Collapsible sidebar on the right) */}
      {activeCitation && (
        <div className="glass-panel" style={{
          width: '320px',
          padding: '20px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          maxHeight: 'calc(100vh - 120px)',
          position: 'relative'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9' }}>
              Nguồn trích dẫn [{activeCitation.source_id}]
            </h4>
            <button
              onClick={() => setActiveCitation(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#64748b',
                fontSize: '1.2rem',
                cursor: 'pointer',
                padding: '0'
              }}
            >
              ✕
            </button>
          </div>
          
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '2px' }}>Tập tin nguồn</div>
              <div style={{ fontSize: '0.85rem', fontWeight: 500, color: '#e2e8f0' }}>{activeCitation.file_name}</div>
            </div>

            {activeCitation.page_number && (
              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '2px' }}>Trang tài liệu</div>
                <div style={{ fontSize: '0.85rem', color: '#e2e8f0' }}>Trang {activeCitation.page_number}</div>
              </div>
            )}

            {activeCitation.heading && (
              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '2px' }}>Mục tiêu đề</div>
                <div style={{ fontSize: '0.85rem', color: '#e2e8f0', fontFamily: 'monospace' }}>{activeCitation.heading}</div>
              </div>
            )}

            {activeCitation.sheet_name && (
              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '2px' }}>Vị trí bảng tính</div>
                <div style={{ fontSize: '0.85rem', color: '#e2e8f0' }}>
                  Sheet: {activeCitation.sheet_name} (Dòng {activeCitation.row_start} - {activeCitation.row_end})
                </div>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
              <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '4px' }}>Đoạn văn trích dẫn gốc</div>
              <div style={{
                flex: 1,
                fontSize: '0.8rem',
                lineHeight: '1.5',
                color: '#cbd5e1',
                background: 'rgba(0, 0, 0, 0.2)',
                padding: '12px',
                borderRadius: '8px',
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
      
      {/* Keyframe animation for spinner */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default ChatPage;
