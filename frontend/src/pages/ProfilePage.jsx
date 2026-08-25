import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { 
  User, Shield, Mail, Calendar, Key, Edit3, 
  CheckCircle2, AlertCircle, Save, Lock, Sparkles
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export default function ProfilePage() {
  const { user, updateUserProfile } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);

  const handleUpdateName = async (e) => {
    e.preventDefault();
    setMsg({ type: '', text: '' });
    setLoading(true);
    try {
      const res = await axios.put(`${API_BASE_URL}/auth/profile`, {
        full_name: fullName.trim()
      });
      updateUserProfile(res.data);
      setMsg({ type: 'success', text: 'Cập nhật họ tên thành công!' });
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Cập nhật thất bại.' });
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setMsg({ type: '', text: '' });
    if (newPassword !== confirmPassword) {
      setMsg({ type: 'error', text: 'Mật khẩu mới xác nhận không trùng khớp.' });
      return;
    }
    if (newPassword.length < 4) {
      setMsg({ type: 'error', text: 'Mật khẩu mới phải có ít nhất 4 ký tự.' });
      return;
    }
    setLoading(true);
    try {
      const res = await axios.put(`${API_BASE_URL}/auth/profile`, {
        current_password: currentPassword,
        new_password: newPassword
      });
      updateUserProfile(res.data);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setMsg({ type: 'success', text: 'Đổi mật khẩu thành công!' });
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Đổi mật khẩu thất bại.' });
    } finally {
      setLoading(false);
    }
  };

  const getRoleBadge = (role) => {
    switch (role) {
      case 'ADMIN':
        return { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.3)', color: '#f87171', label: 'Quản trị viên (ADMIN)' };
      case 'SUBADMIN':
        return { bg: 'rgba(56, 189, 248, 0.15)', border: 'rgba(56, 189, 248, 0.3)', color: '#38bdf8', label: 'Quản trị viên phụ (SUBADMIN)' };
      default:
        return { bg: 'rgba(16, 185, 129, 0.15)', border: 'rgba(16, 185, 129, 0.3)', color: '#34d399', label: 'Người dùng (USER)' };
    }
  };

  const badge = getRoleBadge(user?.role);

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-color)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <User style={{ width: '28px', height: '28px', color: '#10b981' }} />
          Hồ sơ cá nhân
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
          Quản lý thông tin tài khoản và đổi mật khẩu bảo mật
        </p>
      </div>

      {msg.text && (
        <div style={{
          background: msg.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
          border: `1px solid ${msg.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
          borderRadius: '10px',
          padding: '12px 16px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          color: msg.type === 'success' ? '#34d399' : '#f87171'
        }}>
          {msg.type === 'success' ? <CheckCircle2 style={{ width: '20px', height: '20px' }} /> : <AlertCircle style={{ width: '20px', height: '20px' }} />}
          <span>{msg.text}</span>
        </div>
      )}

      {/* User Info Card */}
      <div style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--card-border)',
        borderRadius: '16px',
        padding: '24px',
        marginBottom: '24px',
        display: 'flex',
        alignItems: 'center',
        gap: '20px',
        flexWrap: 'wrap',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.03)'
      }}>
        <div style={{
          width: '72px',
          height: '72px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #10b981, #059669)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '1.75rem',
          fontWeight: 700,
          color: '#fff',
          boxShadow: '0 8px 16px rgba(16, 185, 129, 0.25)'
        }}>
          {user?.username ? user.username[0].toUpperCase() : 'U'}
        </div>

        <div style={{ flex: 1, minWidth: '200px' }}>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 600, color: 'var(--text-color)', marginBottom: '4px' }}>
            {user?.full_name || user?.username}
          </h2>
          <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', marginBottom: '8px' }}>
            @{user?.username}
          </p>

          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 10px',
            background: badge.bg,
            border: `1px solid ${badge.border}`,
            color: badge.color,
            borderRadius: '20px',
            fontSize: '0.8rem',
            fontWeight: 600
          }}>
            <Shield style={{ width: '14px', height: '14px' }} />
            {badge.label}
          </span>
        </div>
      </div>

      {/* Profile Name Form */}
      <div style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--card-border)',
        borderRadius: '16px',
        padding: '24px',
        marginBottom: '24px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.03)'
      }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-color)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Edit3 style={{ width: '18px', height: '18px', color: '#10b981' }} />
          Chỉnh sửa Họ và tên
        </h3>
        <form onSubmit={handleUpdateName}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-light)', marginBottom: '6px' }}>Họ và tên hiển thị</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Nhập họ và tên..."
              style={{
                width: '100%',
                padding: '10px 14px',
                background: 'var(--input-bg)',
                border: '1px solid var(--input-border)',
                borderRadius: '8px',
                color: 'var(--text-color)',
                boxSizing: 'border-box',
                outline: 'none'
              }}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '10px 20px',
              background: '#10b981',
              border: 'none',
              borderRadius: '8px',
              color: '#fff',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Save style={{ width: '16px', height: '16px' }} />
            <span>Lưu thay đổi</span>
          </button>
        </form>
      </div>

      {/* Change Password Form */}
      <div style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--card-border)',
        borderRadius: '16px',
        padding: '24px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.03)'
      }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-color)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Lock style={{ width: '18px', height: '18px', color: '#38bdf8' }} />
          Đổi mật khẩu
        </h3>
        <form onSubmit={handleChangePassword}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-light)', marginBottom: '6px' }}>Mật khẩu hiện tại *</label>
            <input
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Nhập mật khẩu hiện tại..."
              style={{
                width: '100%',
                padding: '10px 14px',
                background: 'var(--input-bg)',
                border: '1px solid var(--input-border)',
                borderRadius: '8px',
                color: 'var(--text-color)',
                boxSizing: 'border-box',
                outline: 'none'
              }}
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-light)', marginBottom: '6px' }}>Mật khẩu mới *</label>
            <input
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Nhập mật khẩu mới (tối thiểu 4 ký tự)..."
              style={{
                width: '100%',
                padding: '10px 14px',
                background: 'var(--input-bg)',
                border: '1px solid var(--input-border)',
                borderRadius: '8px',
                color: 'var(--text-color)',
                boxSizing: 'border-box',
                outline: 'none'
              }}
            />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-light)', marginBottom: '6px' }}>Xác nhận mật khẩu mới *</label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Nhập lại mật khẩu mới..."
              style={{
                width: '100%',
                padding: '10px 14px',
                background: 'var(--input-bg)',
                border: '1px solid var(--input-border)',
                borderRadius: '8px',
                color: 'var(--text-color)',
                boxSizing: 'border-box',
                outline: 'none'
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '10px 20px',
              background: '#38bdf8',
              border: 'none',
              borderRadius: '8px',
              color: '#0f172a',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Key style={{ width: '16px', height: '16px' }} />
            <span>Cập nhật Mật khẩu</span>
          </button>
        </form>
      </div>
    </div>
  );
}
