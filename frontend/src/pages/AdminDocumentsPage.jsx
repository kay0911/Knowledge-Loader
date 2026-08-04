import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  UploadCloud, FileText, RefreshCw, AlertTriangle, 
  CheckCircle2, Clock, PlayCircle, Layers, HelpCircle, ArrowRight, Trash2, Power
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export default function AdminDocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [documentToReprocess, setDocumentToReprocess] = useState(null);
  const [reprocessing, setReprocessing] = useState(false);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const handleToggleEnablement = async (docId, e) => {
    if (e) e.stopPropagation();
    try {
      await axios.post(`${API_BASE_URL}/documents/${docId}/toggle`);
      fetchDocuments();
    } catch (err) {
      console.error("Toggle error:", err);
      alert(err.response?.data?.detail || "Không thể thay đổi trạng thái RAG của tài liệu.");
    }
  };

  const fetchDocuments = async (showLoading = false) => {
    if (showLoading) setRefreshing(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/documents`);
      setDocuments(res.data);
      setUploadError(null);
    } catch (err) {
      console.error("Error fetching documents:", err);
    } finally {
      if (showLoading) setRefreshing(false);
    }
  };

  // Initial fetch on component mount
  useEffect(() => {
    fetchDocuments();
  }, []);

  // Poll only when there are processing documents
  useEffect(() => {
    const hasProcessing = documents.some(
      doc => doc.status === 'PENDING' || doc.status === 'PROCESSING'
    );
    if (hasProcessing) {
      const timer = setTimeout(() => {
        fetchDocuments();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [documents]);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate size and format
    const allowedExtensions = ['pdf', 'docx', 'xlsx'];
    const fileExtension = file.name.split('.').pop().toLowerCase();
    if (!allowedExtensions.includes(fileExtension)) {
      setUploadError("Chỉ chấp nhận các tệp định dạng PDF, DOCX, hoặc XLSX.");
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(false);

    try {
      await axios.post(`${API_BASE_URL}/documents/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadSuccess(true);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchDocuments();
    } catch (err) {
      console.error("Upload error:", err);
      setUploadError(err.response?.data?.detail || "Tải lên thất bại. Vui lòng kiểm tra lại kết nối backend.");
    } finally {
      setUploading(false);
    }
  };

  const executeDeleteDocument = async () => {
    if (!documentToDelete) return;
    setDeleting(true);
    try {
      await axios.delete(`${API_BASE_URL}/documents/${documentToDelete.id}`);
      setDocumentToDelete(null);
      fetchDocuments();
    } catch (err) {
      console.error("Delete error:", err);
      alert(err.response?.data?.detail || "Không thể xóa tài liệu.");
    } finally {
      setDeleting(false);
    }
  };

  const triggerReprocessConfirm = (id, fileName) => {
    setDocumentToReprocess({ id, fileName });
  };

  const executeReprocessDocument = async () => {
    if (!documentToReprocess) return;
    setReprocessing(true);
    try {
      await axios.post(`${API_BASE_URL}/documents/${documentToReprocess.id}/reprocess`);
      setDocumentToReprocess(null);
      fetchDocuments();
    } catch (err) {
      console.error("Reprocess error:", err);
      alert(err.response?.data?.detail || "Không thể yêu cầu xử lý lại.");
    } finally {
      setReprocessing(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'READY':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'PROCESSING':
        return <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'PENDING':
        return <Clock className="w-4 h-4 text-amber-400" />;
      case 'FAILED':
        return <AlertTriangle className="w-4 h-4 text-rose-400" />;
      default:
        return <HelpCircle className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'READY': return 'badge-ready';
      case 'PROCESSING': return 'badge-processing';
      case 'PENDING': return 'badge-pending';
      case 'FAILED': return 'badge-failed';
      case 'SKIPPED': return 'badge-skipped';
      default: return 'badge-skipped';
    }
  };

  // Quick statistics calculation
  const totalDocs = documents.length;
  const readyDocs = documents.filter(d => d.status === 'READY').length;
  const failedDocs = documents.filter(d => d.status === 'FAILED').length;
  const processingDocs = documents.filter(d => d.status === 'PROCESSING' || d.status === 'PENDING').length;

  return (
    <div style={{ maxWidth: '1280px', width: '100%', margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: '32px', boxSizing: 'border-box' }} className="fade-in">
      
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 700, margin: 0, color: 'var(--text-color)', letterSpacing: '-0.02em' }}>
            Quản lý tài liệu tri thức
          </h1>
          <p style={{ color: 'var(--text-light)', margin: '6px 0 0 0', fontSize: '0.9rem' }}>
            Tải lên và xử lý tệp PDF, Word, Excel để nạp vào cơ sở tri thức GraphRAG.
          </p>
        </div>
        
        <button 
          onClick={() => fetchDocuments(true)} 
          className="chatgpt-btn-icon"
          style={{ padding: '10px', backgroundColor: 'var(--input-bg)', border: '1px solid var(--sidebar-border)' }}
          title="Tải lại danh sách"
          disabled={refreshing}
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Main Grid Split: Upload Box (Left) & Stats Widgets (Right) */}
      <div style={{ display: 'grid', gridTemplateColumns: '7fr 3fr', gap: '24px' }}>
        
        {/* Upload File Box */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '1rem', fontWeight: 600, color: 'var(--text-color)' }}>
            Tải tài liệu mới lên
          </h3>
          
          <div 
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: '2px dashed var(--sidebar-border)',
              borderRadius: '12px',
              padding: '40px 20px',
              textAlign: 'center',
              cursor: uploading ? 'not-allowed' : 'pointer',
              backgroundColor: 'var(--sub-box-bg)',
              transition: 'all 0.2s ease-in-out'
            }}
            onMouseEnter={(e) => {
              if (!uploading) {
                e.currentTarget.style.borderColor = '#10b981';
                e.currentTarget.style.backgroundColor = 'rgba(16, 185, 129, 0.04)';
              }
            }}
            onMouseLeave={(e) => {
              if (!uploading) {
                e.currentTarget.style.borderColor = 'var(--sidebar-border)';
                e.currentTarget.style.backgroundColor = 'var(--sub-box-bg)';
              }
            }}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileUpload} 
              style={{ display: 'none' }}
              accept=".pdf,.docx,.xlsx"
              disabled={uploading}
            />
            
            {uploading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                <RefreshCw className="w-10 h-10 text-emerald-400 animate-spin" />
                <p style={{ color: 'var(--text-color)', fontSize: '0.9rem', margin: 0 }}>Đang truyền tải và đăng ký tệp vào hệ thống...</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                <UploadCloud className="w-10 h-10 text-emerald-400" />
                <div>
                  <p style={{ color: 'var(--text-color)', fontSize: '0.95rem', fontWeight: 500, margin: '0 0 4px 0' }}>
                    Nhấn vào đây để tải tệp lên
                  </p>
                  <p style={{ color: 'var(--text-light)', fontSize: '0.75rem', margin: 0 }}>
                    Hỗ trợ tệp PDF, DOCX (Word), XLSX (Excel)
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Feedback messages */}
          {uploadError && (
            <div style={{ marginTop: '16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#f87171', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          {uploadSuccess && (
            <div style={{ marginTop: '16px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)', color: '#34d399', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span>Đăng ký tệp thành công! Pipeline xử lý ngầm đã được kích hoạt.</span>
            </div>
          )}
        </div>

        {/* Quick statistics Widget Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          
          <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>Tổng số tệp</span>
            <strong style={{ fontSize: '1.25rem', color: 'var(--text-color)' }}>{totalDocs}</strong>
          </div>

          <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>Sẵn sàng (Ready)</span>
            <strong style={{ fontSize: '1.25rem', color: '#10b981' }}>{readyDocs}</strong>
          </div>

          <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>Đang xử lý</span>
            <strong style={{ fontSize: '1.25rem', color: '#3b82f6' }}>{processingDocs}</strong>
          </div>

          <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>Xử lý lỗi</span>
            <strong style={{ fontSize: '1.25rem', color: '#ef4444' }}>{failedDocs}</strong>
          </div>

        </div>

      </div>

      {/* Documents Table list */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '1rem', fontWeight: 600, color: 'var(--text-color)' }}>
          Tài liệu trong hệ thống
        </h3>
        
        {documents.length === 0 ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-light)' }}>
            <FileText className="w-12 h-12 text-slate-400" style={{ margin: '0 auto 12px auto' }} />
            <p style={{ margin: 0, fontSize: '0.9rem' }}>Chưa có tài liệu nào trong cơ sở dữ liệu.</p>
          </div>
        ) : (
          <div className="table-container" style={{ width: '100%', overflowX: 'auto', paddingBottom: '8px' }}>
            <table style={{ width: '100%', minWidth: '980px', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--table-border)', color: 'var(--text-light)' }}>
                  <th style={{ padding: '12px 16px', fontWeight: 600, minWidth: '240px' }}>Tên tài liệu</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, minWidth: '90px' }}>Định dạng</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, minWidth: '90px' }}>Routing</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, minWidth: '130px' }}>Trạng thái</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, minWidth: '90px' }}>Số Chunks</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right', minWidth: '340px' }}>Hành động</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr 
                    key={doc.id} 
                    style={{ borderBottom: '1px solid var(--table-border)' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--sidebar-item-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    
                    {/* File Name & UUID */}
                    <td style={{ padding: '16px', maxWidth: '300px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span 
                          style={{ 
                            fontWeight: 500, 
                            color: 'var(--text-color)', 
                            cursor: 'pointer',
                            wordBreak: 'break-word',
                            whiteSpace: 'normal',
                            lineHeight: '1.4'
                          }} 
                          onClick={() => navigate(`/documents/${doc.id}`)}
                          title={doc.original_file_name}
                        >
                          {doc.original_file_name}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-light)', marginTop: '4px', wordBreak: 'break-all' }}>{doc.id}</span>
                      </div>
                    </td>

                    {/* Format type */}
                    <td style={{ padding: '16px' }}>
                      <span style={{ 
                        textTransform: 'uppercase', 
                        fontSize: '0.7rem', 
                        fontWeight: 700, 
                        color: doc.file_type === 'pdf' ? '#f43f5e' : doc.file_type === 'docx' ? '#3b82f6' : '#10b981',
                        backgroundColor: doc.file_type === 'pdf' ? 'rgba(244, 63, 94, 0.1)' : doc.file_type === 'docx' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                        padding: '2px 6px',
                        borderRadius: '4px'
                      }}>
                        {doc.file_type}
                      </span>
                    </td>

                    {/* Routing State result */}
                    <td style={{ padding: '16px' }}>
                      <span style={{ 
                        fontWeight: 600, 
                        fontSize: '0.75rem',
                        color: doc.routing_result === 'NEW' ? '#a855f7' : doc.routing_result === 'UPDATED' ? '#f59e0b' : 'var(--text-light)' 
                      }}>
                        {doc.routing_result || '-'}
                      </span>
                    </td>

                    {/* Status badge */}
                    <td style={{ padding: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className={`badge ${getStatusBadgeClass(doc.status)}`}>
                          {getStatusIcon(doc.status)}
                          {doc.status}
                        </span>
                        {doc.is_enabled === false && (
                          <span style={{
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            color: '#94a3b8',
                            background: 'rgba(148, 163, 184, 0.15)',
                            border: '1px solid rgba(148, 163, 184, 0.3)',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            textTransform: 'uppercase'
                          }}>
                            Tắt RAG
                          </span>
                        )}
                      </div>
                      {doc.error_message && (
                        <div style={{ fontSize: '0.7rem', color: '#f87171', marginTop: '4px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={doc.error_message}>
                          {doc.error_message}
                        </div>
                      )}
                    </td>

                    {/* Chunk counts */}
                    <td style={{ padding: '16px', fontWeight: 600, color: 'var(--text-color)' }}>
                      {doc.status === 'READY' ? doc.chunks_count : '-'}
                    </td>

                    {/* Action buttons */}
                    <td style={{ padding: '16px', textAlign: 'right', whiteSpace: 'nowrap', minWidth: '340px' }}>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', alignItems: 'center' }}>
                        <button 
                          onClick={(e) => handleToggleEnablement(doc.id, e)}
                          className="btn-secondary" 
                          style={{ 
                            padding: '6px 12px', 
                            fontSize: '0.75rem', 
                            display: 'inline-flex', 
                            alignItems: 'center', 
                            gap: '4px',
                            background: doc.is_enabled !== false ? 'rgba(16, 185, 129, 0.1)' : 'rgba(148, 163, 184, 0.1)',
                            border: doc.is_enabled !== false ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid rgba(148, 163, 184, 0.25)',
                            color: doc.is_enabled !== false ? '#34d399' : '#94a3b8',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            transition: 'all 0.2s'
                          }}
                          title={doc.is_enabled !== false ? "Bấm để TẮT RAG (tạm ngưng cho AI hỏi tệp này)" : "Bấm để BẬT RAG (cho phép AI trả lời từ tệp này)"}
                        >
                          <Power className="w-3.5 h-3.5" />
                          {doc.is_enabled !== false ? "Bật RAG" : "Tắt RAG"}
                        </button>

                        <button 
                          onClick={() => navigate(`/documents/${doc.id}`)}
                          className="btn-secondary" 
                          style={{ padding: '6px 12px', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        >
                          Chi tiết
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                        
                        <button 
                          onClick={() => triggerReprocessConfirm(doc.id, doc.original_file_name)}
                          disabled={doc.status === 'PENDING' || doc.status === 'PROCESSING'}
                          className="btn-secondary" 
                          style={{ 
                            padding: '6px 12px', 
                            fontSize: '0.75rem', 
                            display: 'inline-flex', 
                            alignItems: 'center', 
                            gap: '4px',
                            background: doc.status === 'PENDING' || doc.status === 'PROCESSING' 
                              ? 'rgba(99, 102, 241, 0.03)' 
                              : 'rgba(99, 102, 241, 0.1)',
                            border: doc.status === 'PENDING' || doc.status === 'PROCESSING'
                              ? '1px solid rgba(99, 102, 241, 0.03)'
                              : '1px solid rgba(99, 102, 241, 0.2)',
                            color: doc.status === 'PENDING' || doc.status === 'PROCESSING' ? '#555' : '#818cf8',
                            borderRadius: '8px',
                            cursor: doc.status === 'PENDING' || doc.status === 'PROCESSING' ? 'not-allowed' : 'pointer'
                          }}
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${doc.status === 'PROCESSING' ? 'animate-spin' : ''}`} />
                          Reprocess
                        </button>

                        <button 
                          onClick={() => setDocumentToDelete({ id: doc.id, fileName: doc.original_file_name })}
                          className="btn-danger" 
                          style={{ 
                            padding: '6px 12px', 
                            fontSize: '0.75rem', 
                            display: 'inline-flex', 
                            alignItems: 'center', 
                            gap: '4px',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.2)',
                            color: '#f87171',
                            borderRadius: '8px',
                            cursor: 'pointer'
                          }}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Delete
                        </button>
                      </div>
                    </td>

                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Custom Delete Confirmation Modal */}
      {documentToDelete && (
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
            border: '1px solid rgba(239, 68, 68, 0.2)',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
            background: 'var(--modal-bg)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '48px', height: '48px', borderRadius: '12px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#ef4444'
              }}>
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#f87171' }}>
                  Xác nhận xóa tài liệu
                </h3>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>Hành động này không thể hoàn tác</span>
              </div>
            </div>

            <div style={{ color: 'var(--text-color)', fontSize: '0.95rem', lineHeight: '1.6', background: 'var(--sub-box-bg)', padding: '16px', borderRadius: '12px', border: '1px solid var(--table-border)' }}>
              Bạn có chắc chắn muốn xóa tài liệu <strong style={{ color: '#10b981' }}>"{documentToDelete.fileName}"</strong> không? 
              <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem', color: 'var(--text-light)' }}>
                <div>• Xóa các chunks trong cơ sở dữ liệu PostgreSQL.</div>
                <div>• Gỡ bỏ liên kết thực thể (Neo4j).</div>
                <div>• Rebuild lại chỉ mục tìm kiếm BM25.</div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button 
                onClick={() => setDocumentToDelete(null)}
                disabled={deleting}
                className="btn-secondary"
                style={{ padding: '10px 20px', borderRadius: '10px' }}
              >
                Hủy
              </button>
              <button 
                onClick={executeDeleteDocument}
                disabled={deleting}
                className="btn-primary"
                style={{ 
                  padding: '10px 20px', 
                  borderRadius: '10px',
                  background: deleting ? 'rgba(239, 68, 68, 0.5)' : '#ef4444',
                  border: 'none',
                  color: '#fff',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: 'none'
                }}
              >
                {deleting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Đang xóa...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    Xác nhận xóa
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

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
