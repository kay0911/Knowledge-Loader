import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  UploadCloud, FileText, RefreshCw, AlertTriangle, 
  CheckCircle2, Clock, PlayCircle, Layers, HelpCircle, ArrowRight, Trash2
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export default function AdminDocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

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

  // Poll for document status changes if any doc is in PENDING or PROCESSING state
  useEffect(() => {
    fetchDocuments();
    const interval = setInterval(() => {
      const hasProcessing = documents.some(
        doc => doc.status === 'PENDING' || doc.status === 'PROCESSING'
      );
      if (hasProcessing || documents.length === 0) {
        fetchDocuments();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [documents]);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate size and format
    const extension = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'xlsx'].includes(extension)) {
      setUploadError("Only PDF, DOCX, and XLSX file formats are supported.");
      return;
    }

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(false);

    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post(`${API_BASE_URL}/documents/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadSuccess(true);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchDocuments();
    } catch (err) {
      console.error("Upload error:", err);
      setUploadError(err.response?.data?.detail || "Upload failed. Please check backend connection.");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (id, fileName) => {
    if (!window.confirm(`Are you sure you want to delete "${fileName}"? This will delete all of its chunks, Neo4j graph data, and rebuild the search indexes.`)) {
      return;
    }
    
    try {
      await axios.delete(`${API_BASE_URL}/documents/${id}`);
      fetchDocuments();
    } catch (err) {
      console.error("Delete error:", err);
      alert(err.response?.data?.detail || "Failed to delete the document.");
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

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 20px' }}>
      
      {/* Top Title Section */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 className="gradient-text" style={{ fontSize: '2.5rem', fontWeight: 700, margin: 0, letterSpacing: '-0.03em' }}>
            Knowledge Ingestion Dashboard
          </h1>
          <p style={{ color: '#94a3b8', margin: '8px 0 0 0', fontSize: '1rem' }}>
            Upload and process PDF, Word, and Excel files into chunks for GraphRAG MVP.
          </p>
        </div>
        
        <button 
          onClick={() => fetchDocuments(true)} 
          className="btn-secondary" 
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          disabled={refreshing}
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh List'}
        </button>
      </div>

      {/* Grid: Ingestion Upload Panel & Quick Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '7fr 3fr', gap: '24px', marginBottom: '40px' }}>
        
        {/* Drag & Drop Upload Glass Panel */}
        <div className="glass-panel" style={{ padding: '32px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', minHeight: '220px' }}>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            style={{ display: 'none' }} 
            accept=".pdf,.docx,.xlsx"
          />
          <div 
            style={{ cursor: 'pointer' }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (e.dataTransfer.files?.length) {
                handleFileUpload({ target: { files: e.dataTransfer.files } });
              }
            }}
          >
            <div style={{ 
              background: 'rgba(99, 102, 241, 0.1)', 
              borderRadius: '50%', 
              padding: '16px', 
              display: 'inline-flex', 
              marginBottom: '16px',
              border: '1px solid rgba(99, 102, 241, 0.2)'
            }}>
              <UploadCloud className="w-10 h-10 text-indigo-400" />
            </div>
            
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600, margin: '0 0 8px 0' }}>
              Drag & Drop file to upload
            </h3>
            <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 16px 0', maxWidth: '360px' }}>
              Support format: <strong style={{ color: '#c084fc' }}>PDF</strong>, <strong style={{ color: '#c084fc' }}>DOCX</strong> or <strong style={{ color: '#c084fc' }}>XLSX</strong> (max 50MB)
            </p>
            <button className="btn-primary" disabled={uploading}>
              {uploading ? 'Processing File...' : 'Select Document'}
            </button>
          </div>

          {uploadError && (
            <div style={{ marginTop: '16px', color: '#f87171', display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(239, 68, 68, 0.1)', padding: '8px 16px', borderRadius: '8px', fontSize: '0.875rem', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <AlertTriangle className="w-4 h-4" />
              <span>{uploadError}</span>
            </div>
          )}

          {uploadSuccess && (
            <div style={{ marginTop: '16px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(16, 185, 129, 0.1)', padding: '8px 16px', borderRadius: '8px', fontSize: '0.875rem', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <CheckCircle2 className="w-4 h-4" />
              <span>File uploaded and queued for processing!</span>
            </div>
          )}
        </div>

        {/* Quick Stats Panel */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '0 0 16px 0', borderBottom: '1px solid rgba(38, 53, 88, 0.5)', paddingBottom: '12px' }}>
            Ingestion Stats
          </h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div style={{ background: 'rgba(31, 41, 55, 0.3)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(38, 53, 88, 0.3)' }}>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Total Docs</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '4px', color: '#f1f5f9' }}>{documents.length}</div>
            </div>
            <div style={{ background: 'rgba(31, 41, 55, 0.3)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(38, 53, 88, 0.3)' }}>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Total Chunks</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '4px', color: '#a855f7' }}>
                {documents.reduce((acc, curr) => acc + (curr.chunks_count || 0), 0)}
              </div>
            </div>
            <div style={{ background: 'rgba(31, 41, 55, 0.3)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(38, 53, 88, 0.3)' }}>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Ready</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '4px', color: '#34d399' }}>
                {documents.filter(d => d.status === 'READY').length}
              </div>
            </div>
            <div style={{ background: 'rgba(31, 41, 55, 0.3)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(38, 53, 88, 0.3)' }}>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Processing</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '4px', color: '#60a5fa' }}>
                {documents.filter(d => d.status === 'PROCESSING' || d.status === 'PENDING').length}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Documents Table List */}
      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(38, 53, 88, 0.5)', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <FileText className="w-5 h-5 text-indigo-400" />
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Document Repository</h2>
        </div>

        {documents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#94a3b8' }}>
            <FileText className="w-12 h-12 text-slate-600" style={{ margin: '0 auto 16px auto' }} />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '0 0 8px 0', color: '#e2e8f0' }}>No documents uploaded yet</h3>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>Upload your first PDF, DOCX, or XLSX file above to begin chunk ingestion.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ background: 'rgba(30, 41, 59, 0.3)', borderBottom: '1px solid rgba(38, 53, 88, 0.5)' }}>
                  <th style={{ padding: '16px 24px', color: '#94a3b8', fontWeight: 600 }}>File Name</th>
                  <th style={{ padding: '16px 24px', color: '#94a3b8', fontWeight: 600 }}>Type</th>
                  <th style={{ padding: '16px 24px', color: '#94a3b8', fontWeight: 600 }}>Routing</th>
                  <th style={{ padding: '16px 24px', color: '#94a3b8', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '16px 24px', color: '#94a3b8', fontWeight: 600 }}>Chunks</th>
                  <th style={{ padding: '16px 24px', color: '#94a3b8', fontWeight: 600 }}>Uploaded At</th>
                  <th style={{ padding: '16px 24px', color: '#94a3b8', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr 
                    key={doc.id} 
                    style={{ borderBottom: '1px solid rgba(38, 53, 88, 0.3)', transition: 'background 0.2s' }}
                    className="table-row-hover"
                  >
                    {/* File name & size */}
                    <td style={{ padding: '16px 24px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontWeight: 600, color: '#f1f5f9' }}>{doc.original_file_name}</span>
                        <span style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px' }}>{doc.id}</span>
                      </div>
                    </td>
                    
                    {/* File type */}
                    <td style={{ padding: '16px 24px' }}>
                      <span style={{ 
                        textTransform: 'uppercase', 
                        fontSize: '0.75rem', 
                        fontWeight: 700, 
                        color: doc.file_type === 'pdf' ? '#f43f5e' : doc.file_type === 'docx' ? '#3b82f6' : '#10b981',
                        background: 'rgba(31, 41, 55, 0.5)',
                        padding: '2px 8px',
                        borderRadius: '4px'
                      }}>
                        {doc.file_type}
                      </span>
                    </td>

                    {/* Routing result */}
                    <td style={{ padding: '16px 24px' }}>
                      <span style={{ 
                        fontSize: '0.8rem', 
                        fontWeight: 600,
                        color: doc.routing_result === 'NEW' ? '#a855f7' : doc.routing_result === 'UPDATED' ? '#f59e0b' : '#94a3b8' 
                      }}>
                        {doc.routing_result || '-'}
                      </span>
                    </td>

                    {/* Status badge */}
                    <td style={{ padding: '16px 24px' }}>
                      <span className={`badge ${getStatusBadgeClass(doc.status)}`}>
                        {getStatusIcon(doc.status)}
                        {doc.status}
                      </span>
                      {doc.error_message && (
                        <div style={{ fontSize: '0.75rem', color: '#f87171', marginTop: '4px', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={doc.error_message}>
                          {doc.error_message}
                        </div>
                      )}
                    </td>

                    {/* Number of chunks */}
                    <td style={{ padding: '16px 24px', fontWeight: 600 }}>
                      {doc.status === 'READY' ? doc.chunks_count : '-'}
                    </td>

                    {/* Created at */}
                    <td style={{ padding: '16px 24px', color: '#94a3b8' }}>
                      {new Date(doc.created_at).toLocaleString()}
                    </td>

                    {/* Details & Delete action buttons */}
                    <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                        <button 
                          onClick={() => navigate(`/documents/${doc.id}`)}
                          className="btn-secondary" 
                          style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        >
                          Details
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                        <button 
                          onClick={() => handleDeleteDocument(doc.id, doc.original_file_name)}
                          className="btn-danger" 
                          style={{ 
                            padding: '6px 12px', 
                            fontSize: '0.8rem', 
                            display: 'inline-flex', 
                            alignItems: 'center', 
                            gap: '4px',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.2)',
                            color: '#f87171',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            transition: 'all 0.2s'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                            e.currentTarget.style.borderColor = '#ef4444';
                            e.currentTarget.style.color = '#ef4444';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)';
                            e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                            e.currentTarget.style.color = '#f87171';
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

    </div>
  );
}
