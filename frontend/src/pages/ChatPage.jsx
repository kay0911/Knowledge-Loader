import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { 
  Send, BookOpen, Clock, AlertTriangle, Layers, 
  Database, HelpCircle, ArrowRight, Sparkles, Plus, ArrowUp, RefreshCw, X
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const sessionIdParam = searchParams.get('session_id');

  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeCitation, setActiveCitation] = useState(null);
  const [currentSessionId, setCurrentSessionId] = useState(sessionIdParam || null);
  const [historyMode, setHistoryMode] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [isSnippetExpanded, setIsSnippetExpanded] = useState(false);

  useEffect(() => {
    setIsSnippetExpanded(false);
  }, [activeCitation]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
  
  const messagesEndRef = useRef(null);

  // Load all messages of a session when session_id param changes
  useEffect(() => {
    if (sessionIdParam) {
      setCurrentSessionId(sessionIdParam);
      const loadSession = async () => {
        setLoading(true);
        try {
          const res = await axios.get(`${API_BASE_URL}/chat/session/${sessionIdParam}`);
          const msgs = [];
          for (const log of res.data) {
            msgs.push({ sender: 'user', text: log.question });
            if (log.answer) {
              msgs.push({ sender: 'ai', text: log.answer, citations: log.citations || [] });
            }
          }
          setMessages(msgs);
        } catch (err) {
          console.error("Error loading chat session:", err);
        } finally {
          setLoading(false);
        }
      };
      loadSession();
    } else {
      setMessages([]);
      setCurrentSessionId(null);
    }
    setActiveCitation(null);
  }, [sessionIdParam]);

  // Listen to the custom event for "New Chat"
  useEffect(() => {
    const handleNewChat = () => {
      setSearchParams({});
      setMessages([]);
      setActiveCitation(null);
      setCurrentSessionId(null);
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
      const payload = { question: userQuestion, history_mode: historyMode };
      // If we're in an existing session, include the session_id
      if (currentSessionId) {
        payload.session_id = currentSessionId;
      }

      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error("HTTP error " + response.status);
      }

      // Add a placeholder message for AI
      const aiMsg = {
        sender: 'ai',
        text: '',
        citations: []
      };
      setMessages(prev => [...prev, aiMsg]);

      // Read response stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let accumulatedAnswer = '';
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep partial line

        for (const line of lines) {
          const cleanLine = line.trim();
          if (cleanLine.startsWith('data: ')) {
            const dataStr = cleanLine.substring(6);
            try {
              const data = JSON.parse(dataStr);
              if (data.type === 'content') {
                accumulatedAnswer += data.content;
                setMessages(prev => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    ...updated[updated.length - 1],
                    text: accumulatedAnswer
                  };
                  return updated;
                });
              } else if (data.type === 'metadata') {
                setMessages(prev => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    ...updated[updated.length - 1],
                    citations: data.citations || []
                  };
                  return updated;
                });
                
                // Save session_id for follow-up questions
                if (data.session_id) {
                  setCurrentSessionId(data.session_id);
                  setSearchParams({ session_id: data.session_id });
                }
              }
            } catch (err) {
              console.error("Error parsing stream chunk:", err);
            }
          }
        }
      }

    } catch (err) {
      console.error(err);
      const errorMsg = { sender: 'ai', text: 'Lỗi kết nối tới máy chủ hoặc luồng dữ liệu bị ngắt.' };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
      window.dispatchEvent(new Event('chat-history-updated'));
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

  // Inline markdown parser for **bold** and [S1] citations
  const parseMarkdownInline = (inlineText, citations) => {
    if (!inlineText) return "";
    
    // Normalize grouped citations like [S1, S4] or [S1, S2, S3] into separate tags [S1][S4]
    const cleanText = inlineText.replace(/\[\s*S?(\d+)(?:\s*[\s,;&]\s*S?(\d+))+\s*\]/gi, (match) => {
      const nums = match.match(/\d+/g);
      return nums ? nums.map(n => `[S${n}]`).join('') : match;
    });

    // Split by bold patterns (**...**) and citations ([S1])
    const parts = cleanText.split(/(\*\*.*?\*\*|\[S\d+\])/g);
    
    return parts.map((part, idx) => {
      // Check if it is bold
      if (part.startsWith('**') && part.endsWith('**')) {
        const innerText = part.slice(2, -2);
        return <strong key={idx} style={{ color: 'var(--text-color)', fontWeight: 600 }}>{parseMarkdownInline(innerText, citations)}</strong>;
      }
      
      // Check if it is citation tag
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
              fontSize: '0.85rem',
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

  // Helper function to render text with markdown headings, lists, bullet points, and bolding
  const renderMessageText = (text, citations = []) => {
    if (!text) return null;
    const lines = text.split('\n');
    
    return lines.map((line, idx) => {
      let trimmed = line.trim();
      if (!trimmed) {
        return <div key={idx} style={{ height: '6px' }} />;
      }

      // Check for Headings (# H1, ## H2, ### H3, #### H4)
      const headingMatch = trimmed.match(/^(#{1,4})\s+(.*)$/);
      if (headingMatch) {
        const level = headingMatch[1].length;
        const headingText = headingMatch[2];
        
        const fontSizeMap = { 1: '1.3rem', 2: '1.15rem', 3: '1.05rem', 4: '0.95rem' };
        const fontColorMap = { 1: '#f3f4f6', 2: '#e5e7eb', 3: '#6ee7b7', 4: '#a7f3d0' };

        return (
          <div key={idx} style={{ 
            fontSize: fontSizeMap[level] || '1.05rem', 
            fontWeight: 600, 
            color: fontColorMap[level] || 'var(--text-color)',
            marginTop: level === 1 ? '18px' : '12px',
            marginBottom: '6px',
            lineHeight: '1.4'
          }}>
            {parseMarkdownInline(headingText, citations)}
          </div>
        );
      }
      
      // Check if bullet list item (* or -)
      if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
        const content = trimmed.substring(2);
        return (
          <div key={idx} style={{ 
            display: 'flex', 
            paddingLeft: '16px', 
            marginBottom: '6px',
            alignItems: 'flex-start',
            lineHeight: '1.6',
            color: 'var(--text-color)'
          }}>
            <span style={{ marginRight: '8px', color: '#10b981', flexShrink: 0 }}>•</span>
            <span style={{ flex: 1, color: 'var(--text-color)' }}>{parseMarkdownInline(content, citations)}</span>
          </div>
        );
      }

      // Check for Numbered list items (e.g. 1. , 2. )
      const numMatch = trimmed.match(/^(\d+\.)\s+(.*)$/);
      if (numMatch) {
        const numPrefix = numMatch[1];
        const content = numMatch[2];
        return (
          <div key={idx} style={{ 
            display: 'flex', 
            paddingLeft: '8px', 
            marginBottom: '6px',
            alignItems: 'flex-start',
            lineHeight: '1.6',
            color: 'var(--text-color)'
          }}>
            <span style={{ marginRight: '8px', color: '#10b981', fontWeight: 600, flexShrink: 0 }}>{numPrefix}</span>
            <span style={{ flex: 1, color: 'var(--text-color)' }}>{parseMarkdownInline(content, citations)}</span>
          </div>
        );
      }
      
      // Plain paragraph
      return (
        <p key={idx} style={{ 
          marginBottom: '8px', 
          lineHeight: '1.6',
          minHeight: '1em',
          color: 'var(--text-color)'
        }}>
          {parseMarkdownInline(line, citations)}
        </p>
      );
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

              <h2 style={{ fontSize: '1.8rem', fontWeight: 600, color: 'var(--text-color)', margin: 0, textAlign: 'center' }}>
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
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.9rem' }}>
                  <RefreshCw className="chatgpt-loading-spinner" />
                  <span className="chatgpt-loading-text">
                    Đang truy xuất kiến thức & tổng hợp câu trả lời...
                  </span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar Section */}
        <div className="chatgpt-input-wrapper">
          {/* History Mode Toggle Switch */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '10px'
          }}>
            <span style={{ fontSize: '0.8rem', color: historyMode ? '#10b981' : '#8e8e8e', fontWeight: 500, transition: 'color 0.2s' }}>
              Chế độ Lịch sử (History Mode)
            </span>
            <label className="chatgpt-switch" style={{ position: 'relative', display: 'inline-block', width: '34px', height: '20px' }}>
              <input 
                type="checkbox" 
                checked={historyMode} 
                onChange={(e) => setHistoryMode(e.target.checked)}
                style={{ opacity: 0, width: 0, height: 0 }}
              />
              <span style={{
                position: 'absolute',
                cursor: 'pointer',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: historyMode ? '#10b981' : '#3e3e3e',
                transition: '0.3s',
                borderRadius: '20px'
              }}>
                <span style={{
                  position: 'absolute',
                  content: '""',
                  height: '14px',
                  width: '14px',
                  left: historyMode ? '17px' : '3px',
                  bottom: '3px',
                  backgroundColor: 'white',
                  transition: '0.3s',
                  borderRadius: '50%'
                }} />
              </span>
            </label>
          </div>

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
          
          <div style={{ fontSize: '0.7rem', color: 'var(--text-light)', textAlign: 'center', marginTop: '8px' }}>
            Hệ thống GraphRAG sử dụng lai ghép vectơ (Hybrid Search) kết hợp trích xuất thực thể đồ thị Neo4j.
          </div>
        </div>

      </div>

      {/* Citations Side Drawer (Collapsible right panel on desktop, bottom sheet on mobile) */}
      {activeCitation && (
        <>
          {/* Backdrop for mobile */}
          {isMobile && (
            <div 
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.65)',
                backdropFilter: 'blur(4px)',
                zIndex: 99,
                animation: 'fadeIn 0.2s ease'
              }}
              onClick={() => setActiveCitation(null)}
            />
          )}

          <div className="glass-panel" style={{
            position: isMobile ? 'fixed' : 'relative',
            bottom: isMobile ? 0 : 'auto',
            left: isMobile ? 0 : 'auto',
            right: isMobile ? 0 : 'auto',
            top: isMobile ? 'auto' : 0,
            maxHeight: isMobile ? '85vh' : '100%',
            height: isMobile ? 'auto' : '100%',
            width: isMobile ? '100%' : '320px',
            padding: '20px 24px',
            borderLeft: isMobile ? 'none' : '1px solid var(--sidebar-border)',
            borderTop: isMobile ? '1px solid var(--sidebar-border)' : 'none',
            borderTopLeftRadius: isMobile ? '20px' : '0',
            borderTopRightRadius: isMobile ? '20px' : '0',
            background: 'var(--panel-bg)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: isMobile ? '0 -10px 40px rgba(0, 0, 0, 0.5)' : 'none',
            animation: isMobile ? 'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)' : 'fadeIn 0.2s ease-out',
            zIndex: 100,
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-color)' }}>
                Trích dẫn [{activeCitation.source_id}]
              </h4>
              <button
                onClick={() => setActiveCitation(null)}
                style={{
                  background: 'var(--input-bg)',
                  border: '1px solid var(--sidebar-border)',
                  color: 'var(--text-color)',
                  borderRadius: '50%',
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                title="Đóng trích dẫn"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '4px' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Tài liệu nguồn</div>
                <div style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-color)' }}>{activeCitation.file_name}</div>
              </div>

              {(activeCitation.page_start || activeCitation.page_number) && (
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Trang số</div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>
                    {activeCitation.page_start && activeCitation.page_end && activeCitation.page_start !== activeCitation.page_end
                      ? `Trang ${activeCitation.page_start} - ${activeCitation.page_end}`
                      : `Trang ${activeCitation.page_start || activeCitation.page_number}`}
                  </div>
                </div>
              )}

              {(activeCitation.heading_path && activeCitation.heading_path.length > 0) ? (
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Đường dẫn tiêu đề (Heading Path)</div>
                  <div style={{ fontSize: '0.85rem', color: '#a5b4fc', fontFamily: 'monospace', background: 'rgba(99, 102, 241, 0.1)', padding: '4px 8px', borderRadius: '4px', display: 'inline-block' }}>
                    {activeCitation.heading_path.join(' > ')}
                  </div>
                </div>
              ) : activeCitation.heading && (
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Mục tiêu đề</div>
                  <div style={{ fontSize: '0.85rem', color: '#a5b4fc', fontFamily: 'monospace', background: 'rgba(99, 102, 241, 0.1)', padding: '4px 8px', borderRadius: '4px', display: 'inline-block' }}>{activeCitation.heading}</div>
                </div>
              )}

              {activeCitation.sheet_name && (
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>Bảng tính Excel</div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>
                    Sheet: <strong>{activeCitation.sheet_name}</strong> (Dòng {activeCitation.row_start} - {activeCitation.row_end})
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: '150px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', textTransform: 'uppercase', fontWeight: 600 }}>Nội dung đoạn trích</div>
                  {activeCitation.snippet && (activeCitation.snippet.length > 120 || activeCitation.snippet.endsWith('...')) && (
                    <button
                      onClick={() => setIsSnippetExpanded(!isSnippetExpanded)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#818cf8',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        padding: '0 4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px'
                      }}
                    >
                      {isSnippetExpanded ? 'Thu gọn ▲' : 'Xem thêm ▼'}
                    </button>
                  )}
                </div>

                <div style={{
                  flex: 1,
                  fontSize: '0.825rem',
                  lineHeight: '1.6',
                  color: 'var(--text-color)',
                  background: 'var(--input-bg)',
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid var(--sidebar-border)',
                  whiteSpace: 'pre-wrap',
                  overflowY: 'auto',
                  maxHeight: isSnippetExpanded ? '450px' : '160px',
                  transition: 'max-height 0.3s ease'
                }}>
                  "{!isSnippetExpanded && activeCitation.snippet && activeCitation.snippet.length > 120
                    ? activeCitation.snippet.substring(0, 120) + "..."
                    : activeCitation.snippet}"
                </div>

                {activeCitation.snippet && (activeCitation.snippet.length > 120 || activeCitation.snippet.endsWith('...')) && (
                  <button
                    onClick={() => setIsSnippetExpanded(!isSnippetExpanded)}
                    style={{
                      background: 'rgba(99, 102, 241, 0.12)',
                      border: '1px solid rgba(99, 102, 241, 0.25)',
                      color: '#818cf8',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      padding: '8px 12px',
                      borderRadius: '8px',
                      marginTop: '8px',
                      textAlign: 'center',
                      transition: 'all 0.2s',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px'
                    }}
                  >
                    {isSnippetExpanded ? 'Thu gọn nội dung ▲' : 'Xem thêm toàn bộ nội dung ▼'}
                  </button>
                )}
              </div>

              {isMobile && (
                <button
                  onClick={() => setActiveCitation(null)}
                  className="btn-secondary"
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '10px',
                    fontWeight: 600,
                    fontSize: '0.9rem',
                    marginTop: '8px',
                    textAlign: 'center'
                  }}
                >
                  Đóng trích dẫn
                </button>
              )}
            </div>
          </div>
        </>
      )}
      
    </div>
  );
}

export default ChatPage;
