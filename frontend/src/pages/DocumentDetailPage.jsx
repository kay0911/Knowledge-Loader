import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, FileText, Calendar, CheckCircle2, RefreshCw, 
  AlertTriangle, Clock, Layers, Hash, BookOpen, MapPin, Power
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export default function DocumentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [documentToReprocess, setDocumentToReprocess] = useState(null);
  const [reprocessing, setReprocessing] = useState(false);
  const [activatingVersionId, setActivatingVersionId] = useState(null);
  const [notification, setNotification] = useState(null);

  const handleToggleEnablement = async () => {
    try {
      const res = await axios.post(`${API_BASE_URL}/documents/${id}/toggle`);
      await fetchDetails(false);
      setNotification({
        type: 'success',
        text: res.data.is_enabled !== false 
          ? "Đã BẬT trạng thái RAG cho tài liệu này!" 
          : "Đã TẮT trạng thái RAG cho tài liệu này (AI sẽ không hỏi từ tệp này nữa)."
      });
      setTimeout(() => setNotification(null), 4000);
    } catch (err) {
      console.error("Toggle error:", err);
      setNotification({ type: 'error', text: "Không thể thay đổi trạng thái RAG." });
      setTimeout(() => setNotification(null), 4000);
    }
  };

  const handleActivateVersion = async (versionId, versionNumber) => {
    try {
      setActivatingVersionId(versionId);
      await axios.post(`${API_BASE_URL}/documents/${id}/versions/${versionId}/activate`);
      await fetchDetails(false);
      setNotification({
        type: 'success',
        text: `Đã kích hoạt thành công Version ${versionNumber}! Dữ liệu Search & Graph RAG đã được cập nhật.`
      });
      setTimeout(() => setNotification(null), 4000);
    } catch (err) {
      console.error("Activate version error:", err);
      const errMsg = err.response?.data?.detail || "Không thể kích hoạt phiên bản.";
      setNotification({ type: 'error', text: errMsg });
      setTimeout(() => setNotification(null), 4000);
    } finally {
      setActivatingVersionId(null);
    }
  };

  const fetchDetails = async (showLoading = false) => {
    if (showLoading) setLoading(true);
    try {
      // Fetch doc details
      const docRes = await axios.get(`${API_BASE_URL}/documents/${id}`);
      setDoc(docRes.data);
      
      // Fetch chunks
      const chunksRes = await axios.get(`${API_BASE_URL}/documents/${id}/chunks`);
      setChunks(chunksRes.data);
      
      setError(null);
    } catch (err) {
      console.error("Error fetching document details:", err);
      setError("Không thể tải chi tiết tài liệu. Vui lòng kiểm tra lại dịch vụ backend.");
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  const triggerReprocessConfirm = (docId, fileName) => {
    setDocumentToReprocess({ id: docId, fileName });
  };

  const executeReprocessDocument = async () => {
    if (!documentToReprocess) return;
    setReprocessing(true);
    try {
      await axios.post(`${API_BASE_URL}/documents/${documentToReprocess.id}/reprocess`);
      setDocumentToReprocess(null);
      fetchDetails(false);
    } catch (err) {
      console.error("Reprocess error:", err);
      alert(err.response?.data?.detail || "Không thể yêu cầu xử lý lại.");
    } finally {
      setReprocessing(false);
    }
  };

  useEffect(() => {
    fetchDetails(true);
  }, [id]);

  useEffect(() => {
    if (!doc) return;
    const isProcessing = doc.status === 'PENDING' || doc.status === 'PROCESSING';
    if (isProcessing) {
      const timer = setTimeout(() => {
        fetchDetails(false);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [doc]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'READY': return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'PROCESSING': return <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'PENDING': return <Clock className="w-4 h-4 text-amber-400" />;
      case 'FAILED': return <AlertTriangle className="w-4 h-4 text-rose-400" />;
      default: return <Clock className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'READY': return 'badge-ready';
      case 'PROCESSING': return 'badge-processing';
      case 'PENDING': return 'badge-pending';
      case 'FAILED': return 'badge-failed';
      default: return 'badge-skipped';
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '80vh', gap: '16px' }}>
        <RefreshCw className="w-10 h-10 text-emerald-400 animate-spin" />
        <p style={{ color: '#8e8e8e', fontSize: '0.9rem' }}>Đang tải thông tin chi tiết tài liệu...</p>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div style={{ maxWidth: '600px', margin: '80px auto', textAlign: 'center', padding: '24px' }} className="glass-panel">
        <AlertTriangle className="w-12 h-12 text-rose-500" style={{ margin: '0 auto 16px auto' }} />
        <h3 style={{ fontSize: '1.2rem', color: '#f9f9f9', margin: '0 0 8px 0' }}>Có lỗi xảy ra</h3>
        <p style={{ color: '#8e8e8e', fontSize: '0.9rem', margin: '0 0 24px 0' }}>{error || "Không tìm thấy tài liệu yêu cầu."}</p>
        <button onClick={() => navigate('/')} className="btn-secondary">Quay lại Dashboard</button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: '24px' }} className="fade-in">
      
      {/* Toast Notification Popup */}
      {notification && (
        <div style={{
          position: 'fixed',
          top: '24px',
          right: '24px',
          zIndex: 9999,
          background: notification.type === 'success' ? '#10b981' : '#ef4444',
          color: '#ffffff',
          padding: '14px 22px',
          borderRadius: '12px',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          fontSize: '0.9rem',
          fontWeight: 600,
          transition: 'all 0.3s ease'
        }}>
          {notification.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
          <span>{notification.text}</span>
        </div>
      )}

      {/* Back button */}
      <button 
        onClick={() => navigate('/')} 
        className="btn-secondary" 
        style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', width: 'fit-content', padding: '8px 14px' }}
      >
        <ArrowLeft className="w-4 h-4" />
        Quay lại Dashboard
      </button>

      {/* Main Document Details Summary Panel */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
        <div style={{ 
          background: 'rgba(16, 185, 129, 0.1)', 
          borderRadius: '12px', 
          padding: '20px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          alignSelf: 'flex-start'
        }}>
          <FileText className="w-12 h-12 text-emerald-400" />
        </div>

        <div style={{ flex: 1, minWidth: '280px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-color)' }}>
                {doc.original_file_name}
              </h1>
              <span style={{ 
                textTransform: 'uppercase', 
                fontSize: '0.7rem', 
                fontWeight: 700, 
                color: doc.file_type === 'pdf' ? '#f43f5e' : doc.file_type === 'docx' ? '#3b82f6' : '#10b981',
                background: doc.file_type === 'pdf' ? 'rgba(244, 63, 94, 0.1)' : doc.file_type === 'docx' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                padding: '2px 8px',
                borderRadius: '4px'
              }}>
                {doc.file_type}
              </span>
            </div>
            
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button 
                onClick={handleToggleEnablement}
                className="btn-secondary" 
                style={{ 
                  padding: '8px 16px', 
                  fontSize: '0.8rem', 
                  display: 'inline-flex', 
                  alignItems: 'center', 
                  gap: '6px',
                  background: doc.is_enabled !== false ? 'rgba(16, 185, 129, 0.12)' : 'rgba(148, 163, 184, 0.12)',
                  border: doc.is_enabled !== false ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(148, 163, 184, 0.3)',
                  color: doc.is_enabled !== false ? '#34d399' : '#94a3b8',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                title={doc.is_enabled !== false ? "Tạm ngưng không cho AI truy vấn từ tệp này" : "Kích hoạt cho phép AI truy vấn từ tệp này"}
              >
                <Power className="w-4 h-4" />
                {doc.is_enabled !== false ? "Đang Bật RAG" : "Đã Tắt RAG"}
              </button>

              <button 
                onClick={() => triggerReprocessConfirm(doc.id, doc.original_file_name)}
                disabled={doc.status === 'PENDING' || doc.status === 'PROCESSING'}
                className="btn-secondary" 
                style={{ 
                  padding: '8px 16px', 
                  fontSize: '0.8rem', 
                  display: 'inline-flex', 
                  alignItems: 'center', 
                  gap: '6px',
                  background: doc.status === 'PENDING' || doc.status === 'PROCESSING' 
                    ? 'rgba(99, 102, 241, 0.03)' 
                    : 'rgba(99, 102, 241, 0.1)',
                  border: doc.status === 'PENDING' || doc.status === 'PROCESSING'
                    ? '1px solid rgba(99, 102, 241, 0.03)'
                    : '1px solid rgba(99, 102, 241, 0.2)',
                  color: doc.status === 'PENDING' || doc.status === 'PROCESSING' ? '#555' : '#818cf8',
                  borderRadius: '10px',
                  cursor: doc.status === 'PENDING' || doc.status === 'PROCESSING' ? 'not-allowed' : 'pointer'
                }}
              >
                <RefreshCw className={`w-4 h-4 ${doc.status === 'PROCESSING' ? 'animate-spin' : ''}`} />
                Reprocess Document
              </button>
            </div>
          </div>

          <p style={{ fontSize: '0.8rem', color: 'var(--text-light)', margin: '4px 0 16px 0' }}>
            ID Tài liệu: {doc.id}
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-light)', textTransform: 'uppercase', fontWeight: 600 }}>Trạng thái</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', fontWeight: 600 }}>
                {getStatusIcon(doc.status)}
                <span style={{ fontSize: '0.85rem' }}>{doc.status}</span>
              </div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-light)', textTransform: 'uppercase', fontWeight: 600 }}>Mã băm MD5</span>
              <div style={{ fontSize: '0.85rem', marginTop: '4px', fontFamily: 'monospace', color: 'var(--text-color)' }} title={doc.file_hash}>
                {doc.file_hash.substring(0, 16)}...
              </div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-light)', textTransform: 'uppercase', fontWeight: 600 }}>Nạp lần cuối</span>
              <div style={{ fontSize: '0.85rem', marginTop: '4px', color: 'var(--text-color)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>{new Date(doc.created_at).toLocaleString()}</span>
              </div>
            </div>
          </div>

          {doc.error_message && (
            <div style={{ marginTop: '20px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', padding: '12px 16px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
              <AlertTriangle className="w-4 h-4 text-rose-400" style={{ marginTop: '2px' }} />
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f87171' }}>Lỗi xử lý tài liệu</div>
                <div style={{ fontSize: '0.8rem', color: '#fca5a5', marginTop: '2px', wordBreak: 'break-all' }}>{doc.error_message}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Grid: Versions History (Left) & Document Chunks List (Right) */}
      <div style={{ display: 'grid', gridTemplateColumns: '4fr 8fr', gap: '24px' }}>
        
        {/* Left Column: Version Log */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--table-border)', paddingBottom: '12px', color: 'var(--text-color)' }}>
              <Layers className="w-4 h-4 text-indigo-400" />
              Lịch sử phiên bản
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {doc.versions.map((ver) => (
                <div 
                  key={ver.id}
                  style={{ 
                    background: ver.is_active ? 'rgba(16, 185, 129, 0.08)' : 'var(--sub-box-bg)',
                    border: ver.is_active ? '1px solid rgba(16, 185, 129, 0.2)' : '1px solid var(--table-border)',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    position: 'relative'
                  }}
                >
                  {ver.is_active ? (
                    <span style={{ 
                      position: 'absolute', 
                      top: '12px', 
                      right: '16px', 
                      background: 'rgba(16, 185, 129, 0.2)', 
                      color: '#34d399', 
                      fontSize: '0.65rem', 
                      fontWeight: 700, 
                      padding: '2px 6px',
                      borderRadius: '4px',
                      textTransform: 'uppercase'
                    }}>
                      Active
                    </span>
                  ) : ver.status === 'READY' && (
                    <button
                      onClick={() => handleActivateVersion(ver.id, ver.version_number)}
                      disabled={activatingVersionId === ver.id}
                      style={{
                        position: 'absolute',
                        top: '10px',
                        right: '12px',
                        background: 'rgba(99, 102, 241, 0.15)',
                        border: '1px solid rgba(99, 102, 241, 0.3)',
                        color: '#818cf8',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        padding: '4px 10px',
                        borderRadius: '6px',
                        cursor: activatingVersionId === ver.id ? 'not-allowed' : 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        transition: 'all 0.2s'
                      }}
                      title="Kích hoạt phiên bản này cho RAG & Vector Search"
                    >
                      {activatingVersionId === ver.id ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <CheckCircle2 className="w-3 h-3" />
                      )}
                      Kích hoạt
                    </button>
                  )}
                  
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', color: ver.is_active ? '#34d399' : 'var(--text-color)' }}>
                    Version {ver.version_number}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginTop: '6px', fontFamily: 'monospace' }}>
                    Hash: {ver.file_hash.substring(0, 16)}...
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginTop: '4px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>Parser: {ver.parser_version} | Chunk: {ver.chunking_version}</span>
                    <span>{new Date(ver.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Chunks View */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--table-border)', paddingBottom: '12px', color: 'var(--text-color)' }}>
            <Hash className="w-4 h-4 text-emerald-400" />
            Đoạn văn bản trích xuất (Active Chunks) ({chunks.length})
          </h3>
          
          {chunks.length === 0 ? (
            <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-light)' }}>
              Không có đoạn văn bản (chunks) nào được trích xuất cho phiên bản hoạt động này.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto', maxHeight: '600px', paddingRight: '4px' }}>
              {chunks.map((chunk) => (
                <div 
                  key={chunk.id} 
                  style={{ 
                    background: 'var(--sub-box-bg)', 
                    border: '1px solid var(--table-border)', 
                    borderRadius: '12px', 
                    padding: '16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', fontWeight: 600, color: '#818cf8' }}>
                      <BookOpen className="w-3.5 h-3.5" />
                      <span>Thứ tự Chunk #{chunk.chunk_order}</span>
                    </div>

                    <div style={{ display: 'flex', gap: '8px' }}>
                      {chunk.page_number && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: 'var(--text-light)', background: 'var(--card-hover-bg)', padding: '2px 8px', borderRadius: '4px' }}>
                          <MapPin className="w-3 h-3" />
                          Trang {chunk.page_number}
                        </div>
                      )}
                      {chunk.heading && (
                        <div style={{ fontSize: '0.75rem', color: '#34d399', background: 'rgba(16, 185, 129, 0.1)', padding: '2px 8px', borderRadius: '4px' }} title={chunk.heading}>
                          Mục: {chunk.heading}
                        </div>
                      )}
                      {chunk.sheet_name && (
                        <div style={{ fontSize: '0.75rem', color: '#10b981', background: 'rgba(16,185,129,0.1)', padding: '2px 8px', borderRadius: '4px' }}>
                          Excel Sheet: {chunk.sheet_name} (Dòng {chunk.row_start} - {chunk.row_end})
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Chunk content preview */}
                  <div style={{ 
                    fontSize: '0.85rem', 
                    color: 'var(--text-color)', 
                    lineHeight: '1.6', 
                    whiteSpace: 'pre-wrap',
                    background: 'var(--card-bg)',
                    padding: '12px',
                    borderRadius: '6px',
                    border: '1px solid var(--table-border)',
                    fontFamily: chunk.sheet_name ? 'monospace' : 'inherit'
                  }}>
                    {chunk.content}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Custom Reprocess Confirmation Modal */}
      {documentToReprocess && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          animation: 'fadeIn 0.2s ease-out'
        }}>
          <div className="glass-panel" style={{
            width: '100%',
            maxWidth: '500px',
            padding: '32px',
            borderRadius: '20px',
            border: '1px solid rgba(99, 102, 241, 0.2)',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
            background: 'var(--modal-bg)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '48px', height: '48px', borderRadius: '12px',
                background: 'rgba(99, 102, 241, 0.1)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#6366f1'
              }}>
                <RefreshCw className="w-6 h-6" />
              </div>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#818cf8' }}>
                  Xử lý lại tài liệu
                </h3>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>Tạo phiên bản mới cho tài liệu này</span>
              </div>
            </div>

            <div style={{ color: 'var(--text-color)', fontSize: '0.95rem', lineHeight: '1.6', background: 'var(--sub-box-bg)', padding: '16px', borderRadius: '12px', border: '1px solid var(--table-border)' }}>
              Bạn có chắc chắn muốn xử lý lại tài liệu <strong style={{ color: '#10b981' }}>"{documentToReprocess.fileName}"</strong> không? 
              <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem', color: 'var(--text-light)' }}>
                <div>• Tạo phiên bản mới (`DocumentVersion`) chạy ngầm.</div>
                <div>• Chạy lại toàn bộ pipeline trích xuất tri thức (RAG).</div>
                <div>• Tự động kích hoạt khi thành công, giữ nguyên bản cũ nếu lỗi.</div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button 
                onClick={() => setDocumentToReprocess(null)}
                disabled={reprocessing}
                className="btn-secondary"
                style={{ padding: '10px 20px', borderRadius: '10px' }}
              >
                Hủy
              </button>
              <button 
                onClick={executeReprocessDocument}
                disabled={reprocessing}
                className="btn-primary"
                style={{ 
                  padding: '10px 20px', 
                  borderRadius: '10px',
                  background: reprocessing ? 'rgba(99, 102, 241, 0.5)' : '#6366f1',
                  border: 'none',
                  color: '#fff',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: 'none'
                }}
              >
                {reprocessing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Đang xử lý...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Bắt đầu xử lý
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
