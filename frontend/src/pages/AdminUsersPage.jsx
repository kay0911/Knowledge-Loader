import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { 
  Users, UserPlus, Search, Shield, ShieldAlert, Edit, 
  Trash2, Key, CheckCircle2, XCircle, AlertTriangle, 
  X, Save, RefreshCw, Filter, Check
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  
  const [selectedUser, setSelectedUser] = useState(null);

  // Form fields for Create / Edit
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'USER',
    is_active: true
  });

  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (roleFilter) params.role = roleFilter;
      
      const res = await axios.get(`${API_BASE_URL}/users/`, { params });
      setUsers(res.data);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Không thể tải danh sách tài khoản.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [roleFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchUsers();
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    try {
      await axios.post(`${API_BASE_URL}/users/`, formData);
      setSuccessMsg(`Tạo tài khoản '${formData.username}' thành công!`);
      setShowCreateModal(false);
      resetForm();
      fetchUsers();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Không thể tạo tài khoản.');
    }
  };

  const handleEditUser = async (e) => {
    e.preventDefault();
    if (!selectedUser) return;
    setErrorMsg('');
    try {
      const payload = {
        full_name: formData.full_name,
        email: formData.email,
        role: formData.role,
        is_active: formData.is_active
      };
      if (formData.password && formData.password.trim()) {
        payload.password = formData.password.trim();
      }

      await axios.put(`${API_BASE_URL}/users/${selectedUser.id}`, payload);
      setSuccessMsg(`Cập nhật tài khoản '${selectedUser.username}' thành công!`);
      setShowEditModal(false);
      resetForm();
      fetchUsers();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Không thể cập nhật tài khoản.');
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;
    try {
      await axios.delete(`${API_BASE_URL}/users/${selectedUser.id}`);
      setSuccessMsg(`Đã xóa tài khoản '${selectedUser.username}'.`);
      setShowDeleteModal(false);
      setSelectedUser(null);
      fetchUsers();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Không thể xóa tài khoản.');
    }
  };

  const resetForm = () => {
    setFormData({
      username: '',
      email: '',
      full_name: '',
      password: '',
      role: 'USER',
      is_active: true
    });
    setSelectedUser(null);
    setErrorMsg('');
  };

  const openEditModal = (u) => {
    setSelectedUser(u);
    setFormData({
      username: u.username,
      email: u.email || '',
      full_name: u.full_name || '',
      password: '',
      role: u.role,
      is_active: u.is_active
    });
    setShowEditModal(true);
  };

  const getRoleBadge = (role) => {
    switch (role) {
      case 'ADMIN':
        return <span style={{ padding: '3px 8px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.2)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#f87171', fontSize: '0.75rem', fontWeight: 600 }}>ADMIN</span>;
      case 'SUBADMIN':
        return <span style={{ padding: '3px 8px', borderRadius: '12px', background: 'rgba(56, 189, 248, 0.2)', border: '1px solid rgba(56, 189, 248, 0.4)', color: '#38bdf8', fontSize: '0.75rem', fontWeight: 600 }}>SUBADMIN</span>;
      default:
        return <span style={{ padding: '3px 8px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.2)', border: '1px solid rgba(16, 185, 129, 0.4)', color: '#34d399', fontSize: '0.75rem', fontWeight: 600 }}>USER</span>;
    }
  };

  const totalAdmins = users.filter(u => u.role === 'ADMIN').length;
  const totalSubadmins = users.filter(u => u.role === 'SUBADMIN').length;
  const totalUsersRole = users.filter(u => u.role === 'USER').length;

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-color)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Users style={{ width: '28px', height: '28px', color: '#10b981' }} />
            Quản lý Người dùng & Phân quyền
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
            Tạo mới, phân quyền (ADMIN, SUBADMIN, USER) và quản lý tài khoản người dùng
          </p>
        </div>

        <button
          onClick={() => {
            resetForm();
            setShowCreateModal(true);
          }}
          style={{
            padding: '12px 20px',
            background: 'linear-gradient(135deg, #10b981, #059669)',
            border: 'none',
            borderRadius: '10px',
            color: '#fff',
            fontWeight: 600,
            fontSize: '0.95rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 4px 14px rgba(16, 185, 129, 0.3)'
          }}
        >
          <UserPlus style={{ width: '18px', height: '18px' }} />
          <span>Tạo tài khoản mới</span>
        </button>
      </div>

      {/* Messages */}
      {successMsg && (
        <div style={{ background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '10px', padding: '12px 16px', marginBottom: '20px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle2 style={{ width: '18px', height: '18px' }} />
          <span>{successMsg}</span>
          <X onClick={() => setSuccessMsg('')} style={{ marginLeft: 'auto', cursor: 'pointer', width: '16px', height: '16px' }} />
        </div>
      )}

      {errorMsg && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '10px', padding: '12px 16px', marginBottom: '20px', color: '#f87171', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle style={{ width: '18px', height: '18px' }} />
          <span>{errorMsg}</span>
          <X onClick={() => setErrorMsg('')} style={{ marginLeft: 'auto', cursor: 'pointer', width: '16px', height: '16px' }} />
        </div>
      )}

      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div style={{ background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '16px' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600 }}>TỔNG TÀI KHOẢN</span>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-color)', marginTop: '4px' }}>{users.length}</p>
        </div>
        <div style={{ background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '16px' }}>
          <span style={{ color: '#f87171', fontSize: '0.8rem', fontWeight: 600 }}>QUẢN TRỊ VIÊN (ADMIN)</span>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, color: '#f87171', marginTop: '4px' }}>{totalAdmins}</p>
        </div>
        <div style={{ background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '16px' }}>
          <span style={{ color: '#38bdf8', fontSize: '0.8rem', fontWeight: 600 }}>QUẢN TRỊ PHỤ (SUBADMIN)</span>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, color: '#38bdf8', marginTop: '4px' }}>{totalSubadmins}</p>
        </div>
        <div style={{ background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '16px' }}>
          <span style={{ color: '#34d399', fontSize: '0.8rem', fontWeight: 600 }}>NGƯỜI DÙNG (USER)</span>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, color: '#34d399', marginTop: '4px' }}>{totalUsersRole}</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '16px', marginBottom: '24px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
        <form onSubmit={handleSearchSubmit} style={{ flex: 1, minWidth: '240px', display: 'flex', gap: '8px' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', width: '18px', height: '18px', color: '#64748b' }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo tên đăng nhập, email, tên..."
              style={{
                width: '100%',
                padding: '10px 12px 10px 40px',
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '8px',
                color: 'var(--text-color)',
                boxSizing: 'border-box'
              }}
            />
          </div>
          <button type="submit" style={{ padding: '10px 16px', background: 'rgba(255, 255, 255, 0.1)', border: 'none', borderRadius: '8px', color: 'var(--text-color)', cursor: 'pointer' }}>
            Tìm kiếm
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter style={{ width: '16px', height: '16px', color: '#94a3b8' }} />
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            style={{
              padding: '10px 14px',
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: '8px',
              color: 'var(--text-color)',
              outline: 'none'
            }}
          >
            <option value="">Tất cả Vai trò</option>
            <option value="ADMIN">ADMIN</option>
            <option value="SUBADMIN">SUBADMIN</option>
            <option value="USER">USER</option>
          </select>
        </div>
      </div>

      {/* User Table */}
      <div style={{ background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: 'rgba(15, 23, 42, 0.6)', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: '#94a3b8', fontSize: '0.85rem' }}>
              <th style={{ padding: '14px 16px' }}>TÀI KHOẢN</th>
              <th style={{ padding: '14px 16px' }}>HỌ VÀ TÊN</th>
              <th style={{ padding: '14px 16px' }}>VAI TRÒ (ROLE)</th>
              <th style={{ padding: '14px 16px' }}>TRẠNG THÁI</th>
              <th style={{ padding: '14px 16px' }}>NGÀY TẠO</th>
              <th style={{ padding: '14px 16px', textAlign: 'right' }}>THAO TÁC</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>
                  Đang tải danh sách người dùng...
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>
                  Không tìm thấy tài khoản nào.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.9rem' }}>
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 600, fontSize: '0.9rem' }}>
                        {u.username[0].toUpperCase()}
                      </div>
                      <div>
                        <span style={{ fontWeight: 600, color: 'var(--text-color)', display: 'block' }}>{u.username}</span>
                        <span style={{ fontSize: '0.78rem', color: '#64748b' }}>{u.email || 'Chưa cập nhật email'}</span>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px', color: '#cbd5e1' }}>
                    {u.full_name || '—'}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    {getRoleBadge(u.role)}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    {u.is_active ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#34d399', fontSize: '0.8rem', fontWeight: 500 }}>
                        <CheckCircle2 style={{ width: '14px', height: '14px' }} /> Hoạt động
                      </span>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#f87171', fontSize: '0.8rem', fontWeight: 500 }}>
                        <XCircle style={{ width: '14px', height: '14px' }} /> Đã khóa
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '14px 16px', color: '#64748b', fontSize: '0.85rem' }}>
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('vi-VN') : '—'}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '8px' }}>
                      <button
                        onClick={() => openEditModal(u)}
                        title="Chỉnh sửa tài khoản"
                        style={{ padding: '6px 10px', background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '6px', color: '#38bdf8', cursor: 'pointer' }}
                      >
                        <Edit style={{ width: '14px', height: '14px' }} />
                      </button>

                      {currentUser.role === 'ADMIN' && u.id !== currentUser.id && (
                        <button
                          onClick={() => {
                            setSelectedUser(u);
                            setShowDeleteModal(true);
                          }}
                          title="Xóa tài khoản"
                          style={{ padding: '6px 10px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#f87171', cursor: 'pointer' }}
                        >
                          <Trash2 style={{ width: '14px', height: '14px' }} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, padding: '20px' }}>
          <div style={{ width: '100%', maxWidth: '480px', background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '16px', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-color)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <UserPlus style={{ width: '20px', height: '20px', color: '#10b981' }} />
                Tạo tài khoản mới
              </h3>
              <X onClick={() => setShowCreateModal(false)} style={{ cursor: 'pointer', color: '#94a3b8' }} />
            </div>

            <form onSubmit={handleCreateUser}>
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Tên đăng nhập *</label>
                <input
                  type="text"
                  required
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  placeholder="john_doe..."
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Mật khẩu ban đầu *</label>
                <input
                  type="password"
                  required
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="Mật khẩu tối thiểu 4 ký tự..."
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Họ và tên</label>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  placeholder="Nguyễn Văn A..."
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="user@company.com..."
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Vai trò (Role)</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                >
                  <option value="USER">USER (Chỉ Chat & Hồ sơ)</option>
                  <option value="SUBADMIN">SUBADMIN (Quản lý tài liệu & Người dùng)</option>
                  {currentUser.role === 'ADMIN' && <option value="ADMIN">ADMIN (Quản trị tối cao)</option>}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button type="button" onClick={() => setShowCreateModal(false)} style={{ padding: '10px 18px', background: 'rgba(255, 255, 255, 0.1)', border: 'none', borderRadius: '8px', color: 'var(--text-color)', cursor: 'pointer' }}>Hủy</button>
                <button type="submit" style={{ padding: '10px 20px', background: '#10b981', border: 'none', borderRadius: '8px', color: '#fff', fontWeight: 600, cursor: 'pointer' }}>Tạo tài khoản</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {showEditModal && selectedUser && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, padding: '20px' }}>
          <div style={{ width: '100%', maxWidth: '480px', background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '16px', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-color)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Edit style={{ width: '20px', height: '20px', color: '#38bdf8' }} />
                Chỉnh sửa tài khoản @{selectedUser.username}
              </h3>
              <X onClick={() => setShowEditModal(false)} style={{ cursor: 'pointer', color: '#94a3b8' }} />
            </div>

            <form onSubmit={handleEditUser}>
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Họ và tên</label>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Reset Mật khẩu mới (Bỏ trống nếu không đổi)</label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="Nhập mật khẩu mới..."
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Vai trò (Role)</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  style={{ width: '100%', padding: '10px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px', color: 'var(--text-color)', boxSizing: 'border-box' }}
                >
                  <option value="USER">USER (Chỉ Chat & Hồ sơ)</option>
                  <option value="SUBADMIN">SUBADMIN (Quản lý tài liệu & Người dùng)</option>
                  {currentUser.role === 'ADMIN' && <option value="ADMIN">ADMIN (Quản trị tối cao)</option>}
                </select>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#cbd5e1', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    style={{ width: '16px', height: '16px' }}
                  />
                  <span>Tài khoản đang hoạt động (Bỏ tick để Khóa tài khoản)</span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button type="button" onClick={() => setShowEditModal(false)} style={{ padding: '10px 18px', background: 'rgba(255, 255, 255, 0.1)', border: 'none', borderRadius: '8px', color: 'var(--text-color)', cursor: 'pointer' }}>Hủy</button>
                <button type="submit" style={{ padding: '10px 20px', background: '#38bdf8', border: 'none', borderRadius: '8px', color: '#0f172a', fontWeight: 600, cursor: 'pointer' }}>Lưu thông tin</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && selectedUser && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, padding: '20px' }}>
          <div style={{ width: '100%', maxWidth: '420px', background: 'var(--card-bg, #1e293b)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '16px', padding: '24px', textAlign: 'center' }}>
            <AlertTriangle style={{ width: '48px', height: '48px', color: '#f87171', margin: '0 auto 16px' }} />
            <h3 style={{ fontSize: '1.2rem', color: 'var(--text-color)', marginBottom: '8px' }}>Xác nhận xóa tài khoản?</h3>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '20px' }}>
              Bạn có chắc chắn muốn xóa tài khoản <strong>@{selectedUser.username}</strong>? Hành động này không thể hoàn tác.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '12px' }}>
              <button onClick={() => setShowDeleteModal(false)} style={{ padding: '10px 20px', background: 'rgba(255, 255, 255, 0.1)', border: 'none', borderRadius: '8px', color: 'var(--text-color)', cursor: 'pointer' }}>Hủy</button>
              <button onClick={handleDeleteUser} style={{ padding: '10px 20px', background: '#ef4444', border: 'none', borderRadius: '8px', color: '#fff', fontWeight: 600, cursor: 'pointer' }}>Xóa vĩnh viễn</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
