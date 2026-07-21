import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, FileText, Calendar, CheckCircle2, RefreshCw, 
  AlertTriangle, Clock, Layers, Hash, BookOpen, MapPin
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
      setError("Failed to load document details. Please ensure the backend is running.");
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
      alert(err.response?.data?.detail || "Failed to trigger reprocessing.");
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
      const interval = setInterval(() => {
        fetchDetails(false);
      }, 3000);
      return () => clearInterval(interval);
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

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', gap: '16px' }}>
        <RefreshCw className="w-10 h-10 text-indigo-400 animate-spin" />
        <p style={{ color: '#94a3b8' }}>Loading document details...</p>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div style={{ maxWidth: '800px', margin: '100px auto', padding: '0 20px', textAlign: 'center' }}>
        <div className="glass-panel" style={{ padding: '40px 20px' }}>
          <AlertTriangle className="w-12 h-12 text-rose-400" style={{ margin: '0 auto 16px auto' }} />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600, margin: '0 0 16px 0' }}>Error Loading Details</h2>
          <p style={{ color: '#94a3b8', margin: '0 0 24px 0' }}>{error || "Document not found."}</p>
          <button className="btn-primary" onClick={() => navigate('/')}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 20px' }}>
      
      {/* Back & Navigation Header */}
      <button 
        onClick={() => navigate('/')} 
        className="btn-secondary" 
        style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </button>

      {/* Main Document Details Summary Panel */}
      <div className="glass-panel" style={{ padding: '28px', marginBottom: '32px', display: 'flex', gap: '28px', flexWrap: 'wrap' }}>
        <div style={{ 
          background: 'rgba(99, 102, 241, 0.1)', 
          borderRadius: '12px', 
          padding: '24px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          border: '1px solid rgba(99, 102, 241, 0.2)',
          alignSelf: 'flex-start'
        }}>
          <FileText className="w-12 h-12 text-indigo-400" />
        </div>

        <div style={{ flex: 1, minWidth: '280px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h1 style={{ fontSize: '1.8rem', fontWeight: 700, margin: 0, color: '#f1f5f9' }}>
                {doc.original_file_name}
              </h1>
              <span style={{ 
                textTransform: 'uppercase', 
                fontSize: '0.75rem', 
                fontWeight: 700, 
                color: doc.file_type === 'pdf' ? '#f43f5e' : doc.file_type === 'docx' ? '#3b82f6' : '#10b981',
                background: 'rgba(31, 41, 55, 0.6)',
                padding: '2px 8px',
                borderRadius: '4px'
              }}>
                {doc.file_type}
              </span>
            </div>
            
            <button 
              onClick={() => triggerReprocessConfirm(doc.id, doc.original_file_name)}
              disabled={doc.status === 'PENDING' || doc.status === 'PROCESSING'}
              className="btn-secondary" 
              style={{ 
                padding: '8px 16px', 
                fontSize: '0.85rem', 
                display: 'inline-flex', 
                alignItems: 'center', 
                gap: '6px',
                background: doc.status === 'PENDING' || doc.status === 'PROCESSING' 
                  ? 'rgba(99, 102, 241, 0.05)' 
                  : 'rgba(99, 102, 241, 0.1)',
                border: doc.status === 'PENDING' || doc.status === 'PROCESSING'
                  ? '1px solid rgba(99, 102, 241, 0.05)'
                  : '1px solid rgba(99, 102, 241, 0.2)',
                color: doc.status === 'PENDING' || doc.status === 'PROCESSING'
                  ? '#4b5563'
                  : '#818cf8',
                borderRadius: '10px',
                cursor: doc.status === 'PENDING' || doc.status === 'PROCESSING' ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s'
              }}
            >
              <RefreshCw className={`w-4 h-4 ${doc.status === 'PROCESSING' ? 'animate-spin' : ''}`} />
              Reprocess Document
            </button>
          </div>

          <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '4px 0 16px 0' }}>
            Document ID: {doc.id}
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Status</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', fontWeight: 600 }}>
                {getStatusIcon(doc.status)}
                <span style={{ fontSize: '0.9rem' }}>{doc.status}</span>
              </div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>File Hash</span>
              <div style={{ fontSize: '0.9rem', marginTop: '4px', fontFamily: 'monospace', color: '#cbd5e1' }} title={doc.file_hash}>
                {doc.file_hash.substring(0, 12)}...
              </div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Last Ingested At</span>
              <div style={{ fontSize: '0.9rem', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px', color: '#cbd5e1' }}>
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>{new Date(doc.created_at).toLocaleString()}</span>
              </div>
            </div>
          </div>

          {doc.error_message && (
            <div style={{ marginTop: '20px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', padding: '12px 16px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
              <AlertTriangle className="w-4 h-4 text-rose-400" style={{ marginTop: '2px' }} />
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f87171' }}>Ingestion Error</div>
                <div style={{ fontSize: '0.8rem', color: '#fca5a5', marginTop: '2px', wordBreak: 'break-all' }}>{doc.error_message}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Two Column Layout: Versions (Left) & Chunks (Right) */}
      <div style={{ display: 'grid', gridTemplateColumns: '4fr 8fr', gap: '32px' }}>
        
        {/* Versions Log Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid rgba(38, 53, 88, 0.5)', paddingBottom: '12px' }}>
              <Layers className="w-4 h-4 text-indigo-400" />
              Version History
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {doc.versions.map((ver) => (
                <div 
                  key={ver.id}
                  style={{ 
                    background: ver.is_active ? 'rgba(99, 102, 241, 0.1)' : 'rgba(31, 41, 55, 0.3)',
                    border: ver.is_active ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid rgba(38, 53, 88, 0.3)',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    position: 'relative'
                  }}
                >
                  {ver.is_active && (
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
                  )}
                  
                  <div style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '0.95rem' }}>
                    Version {ver.version_number}
                  </div>
                  
                  <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px', fontFamily: 'monospace' }}>
                    Hash: {ver.file_hash.substring(0, 10)}...
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', fontSize: '0.75rem' }}>
                    <span style={{ color: '#94a3b8' }}>Status: {ver.status}</span>
                    <span style={{ color: '#64748b' }}>{new Date(ver.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Chunks List Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid rgba(38, 53, 88, 0.5)', paddingBottom: '12px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BookOpen className="w-4 h-4 text-indigo-400" />
                Document Chunks ({chunks.length})
              </h3>
            </div>

            {chunks.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#94a3b8' }}>
                <Hash className="w-8 h-8 text-slate-600" style={{ margin: '0 auto 12px auto' }} />
                <p style={{ margin: 0, fontSize: '0.9rem' }}>No chunk details available. Chunking only occurs when the document status is READY.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '600px', overflowY: 'auto', paddingRight: '8px' }}>
                {chunks.map((chunk, idx) => (
                  <div 
                    key={chunk.id} 
                    className="glass-panel-hover"
                    style={{ 
                      background: 'rgba(31, 41, 55, 0.3)',
                      border: '1px solid rgba(38, 53, 88, 0.3)',
                      borderRadius: '8px',
                      padding: '16px'
                    }}
                  >
                    {/* Chunk header details */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '12px', borderBottom: '1px dashed rgba(38, 53, 88, 0.4)', paddingBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600, color: '#a855f7' }}>
                        <Hash className="w-3.5 h-3.5" />
                        <span>Order #{chunk.chunk_order}</span>
                      </div>
                      
                      {/* Metadata badges based on file type */}
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {chunk.page_number && (
                          <span style={{ fontSize: '0.7rem', background: 'rgba(99, 102, 241, 0.1)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.2)', padding: '2px 8px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <BookOpen className="w-3 h-3" />
                            Page {chunk.page_number}
                          </span>
                        )}
                        {chunk.heading && (
                          <span style={{ fontSize: '0.7rem', background: 'rgba(236, 72, 153, 0.1)', color: '#f472b6', border: '1px solid rgba(236, 72, 153, 0.2)', padding: '2px 8px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '4px' }} title={chunk.heading}>
                            <Layers className="w-3 h-3" />
                            Heading: {chunk.heading}
                          </span>
                        )}
                        {chunk.sheet_name && (
                          <span style={{ fontSize: '0.7rem', background: 'rgba(16, 185, 129, 0.1)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '2px 8px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            Sheet: {chunk.sheet_name}
                          </span>
                        )}
                        {(chunk.row_start || chunk.row_end) && (
                          <span style={{ fontSize: '0.7rem', background: 'rgba(245, 158, 11, 0.1)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.2)', padding: '2px 8px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <MapPin className="w-3 h-3" />
                            Row {chunk.row_start === chunk.row_end ? chunk.row_start : `${chunk.row_start}-${chunk.row_end}`}
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {/* Chunk content preview */}
                    <div style={{ 
                      fontSize: '0.875rem', 
                      color: '#cbd5e1', 
                      lineHeight: '1.6', 
                      whiteSpace: 'pre-wrap',
                      background: 'rgba(11, 15, 25, 0.4)',
                      padding: '12px',
                      borderRadius: '6px',
                      border: '1px solid rgba(38, 53, 88, 0.2)',
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

      </div>

      {/* Custom Reprocess Confirmation Modal */}
      {documentToReprocess && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
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
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: 'rgba(99, 102, 241, 0.1)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#6366f1'
              }}>
                <RefreshCw className="w-6 h-6" />
              </div>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#818cf8' }}>
                  Xác nhận xử lý lại tài liệu
                </h3>
                <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Tạo phiên bản mới cho tài liệu này</span>
              </div>
            </div>

            <div style={{ color: '#e2e8f0', fontSize: '0.95rem', lineHeight: '1.6', background: 'rgba(15, 23, 42, 0.3)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
              Bạn có chắc chắn muốn xử lý lại tài liệu <strong style={{ color: '#a855f7' }}>"{documentToReprocess.fileName}"</strong> không? 
              <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem', color: '#94a3b8' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <span style={{ color: '#6366f1' }}>•</span>
                  <span>Lấy lại file gốc đã lưu trữ và tạo một phiên bản (`DocumentVersion`) mới.</span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <span style={{ color: '#6366f1' }}>•</span>
                  <span>Chạy lại pipeline: phân tích (parse), cắt nhỏ (chunking), tạo vector (embedding), và trích xuất thực thể đồ thị (graph extraction).</span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <span style={{ color: '#6366f1' }}>•</span>
                  <span>Chỉ chuyển đổi sang phiên bản mới khi quá trình xử lý hoàn tất thành công.</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
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
                  borderColor: reprocessing ? 'transparent' : '#6366f1',
                  color: '#fff',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                {reprocessing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Đang khởi tạo...
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
