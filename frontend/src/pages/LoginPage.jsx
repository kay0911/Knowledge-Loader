import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { 
  LogIn, Lock, User, Eye, EyeOff, AlertCircle, 
  HelpCircle, CheckCircle2, X, Send, Sparkles, Shield
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Contact Admin Modal State
  const [showContactModal, setShowContactModal] = useState(false);
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [contactNote, setContactNote] = useState('');
  const [contactSuccess, setContactSuccess] = useState(false);
  const [contactLoading, setContactLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Vui lòng nhập tên đăng nhập và mật khẩu.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const userInfo = await login(username.trim(), password);
      if (userInfo.role === 'ADMIN' || userInfo.role === 'SUBADMIN') {
        navigate('/chat');
      } else {
        navigate('/chat');
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleContactSubmit = async (e) => {
    e.preventDefault();
    if (!contactName.trim() || !contactEmail.trim()) {
      return;
    }
    setContactLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/auth/contact-admin`, {
        full_name: contactName,
        email: contactEmail,
        phone: contactPhone,
        note: contactNote
      });
      setContactSuccess(true);
    } catch (err) {
      alert('Không thể gửi yêu cầu. Vui lòng thử lại sau.');
    } finally {
      setContactLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(circle at 50% 30%, rgba(16, 185, 129, 0.15), rgba(15, 23, 42, 0.98))',
      padding: '20px',
      position: 'relative'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '440px',
        background: 'rgba(30, 41, 59, 0.75)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '20px',
        padding: '36px 32px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
      }}>
        {/* Header Branding */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #10b981, #059669)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 8px 20px rgba(16, 185, 129, 0.3)'
          }}>
            <Shield style={{ width: '28px', height: '28px', color: '#ffffff' }} />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-color)', marginBottom: '8px' }}>
            Knowledge Loader
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
            Đăng nhập hệ thống Quản trị & Trợ lý AI
          </p>
        </div>

        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '10px',
            padding: '12px 14px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            color: '#f87171',
            fontSize: '0.875rem'
          }}>
            <AlertCircle style={{ width: '18px', height: '18px', flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin}>
          {/* Username Input */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#cbd5e1', marginBottom: '8px' }}>
              Tên đăng nhập hoặc Email
            </label>
            <div style={{ position: 'relative' }}>
              <User style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', width: '18px', height: '18px', color: '#64748b' }} />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Nhập tên đăng nhập..."
                style={{
                  width: '100%',
                  padding: '12px 14px 12px 42px',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '10px',
                  color: 'var(--text-color)',
                  fontSize: '0.95rem',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          </div>

          {/* Password Input */}
          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#cbd5e1', marginBottom: '8px' }}>
              Mật khẩu
            </label>
            <div style={{ position: 'relative' }}>
              <Lock style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', width: '18px', height: '18px', color: '#64748b' }} />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Nhập mật khẩu..."
                style={{
                  width: '100%',
                  padding: '12px 44px 12px 42px',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '10px',
                  color: 'var(--text-color)',
                  fontSize: '0.95rem',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  cursor: 'pointer',
                  padding: '4px'
                }}
              >
                {showPassword ? <EyeOff style={{ width: '18px', height: '18px' }} /> : <Eye style={{ width: '18px', height: '18px' }} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '14px',
              background: 'linear-gradient(135deg, #10b981, #059669)',
              border: 'none',
              borderRadius: '10px',
              color: '#ffffff',
              fontSize: '1rem',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 14px rgba(16, 185, 129, 0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              transition: 'all 0.2s'
            }}
          >
            {loading ? (
              <span>Đang xác thực...</span>
            ) : (
              <>
                <LogIn style={{ width: '20px', height: '20px' }} />
                <span>Đăng nhập</span>
              </>
            )}
          </button>
        </form>

        {/* Footer Contact Admin Request */}
        <div style={{ marginTop: '24px', paddingTop: '20px', borderTop: '1px solid rgba(255, 255, 255, 0.08)', textAlign: 'center' }}>
          <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '8px' }}>
            Chưa có tài khoản?
          </p>
          <button
            type="button"
            onClick={() => {
              setShowContactModal(true);
              setContactSuccess(false);
            }}
            style={{
              background: 'none',
              border: 'none',
              color: '#34d399',
              fontSize: '0.875rem',
              fontWeight: 600,
              cursor: 'pointer',
              textDecoration: 'underline',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <HelpCircle style={{ width: '16px', height: '16px' }} />
            <span>Liên hệ Admin để đăng ký tài khoản</span>
          </button>
        </div>

        {/* Quick Admin Test Login Button */}
        <div style={{ marginTop: '16px', textAlign: 'center' }}>
          <button
            type="button"
            onClick={() => {
              setUsername('admin');
              setPassword('admin123');
            }}
            style={{
              background: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: '8px',
              padding: '6px 12px',
              color: '#38bdf8',
              fontSize: '0.75rem',
              fontWeight: 500,
              cursor: 'pointer'
            }}
          >
            Sử dụng Tài khoản Admin Mặc định (admin / admin123)
          </button>
        </div>
      </div>

      {/* Contact Admin Modal */}
      {showContactModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(6px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px'
        }}>
          <div style={{
            width: '100%',
            maxWidth: '460px',
            background: 'var(--card-bg, #1e293b)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '16px',
            padding: '28px',
            position: 'relative'
          }}>
            <button
              onClick={() => setShowContactModal(false)}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                background: 'none',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer'
              }}
            >
              <X style={{ width: '20px', height: '20px' }} />
            </button>

            {contactSuccess ? (
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <CheckCircle2 style={{ width: '48px', height: '48px', color: '#10b981', margin: '0 auto 16px' }} />
                <h3 style={{ fontSize: '1.2rem', color: 'var(--text-color)', marginBottom: '8px' }}>Yêu cầu đã được gửi!</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '20px' }}>
                  Quản trị viên đã nhận được thông tin đăng ký của bạn và sẽ liên hệ tạo tài khoản trong thời gian sớm nhất.
                </p>
                <button
                  onClick={() => setShowContactModal(false)}
                  style={{
                    padding: '10px 24px',
                    background: '#10b981',
                    border: 'none',
                    borderRadius: '8px',
                    color: '#fff',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Đóng
                </button>
              </div>
            ) : (
              <form onSubmit={handleContactSubmit}>
                <h3 style={{ fontSize: '1.25rem', color: 'var(--text-color)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles style={{ width: '20px', height: '20px', color: '#10b981' }} />
                  Đăng ký cấp Tài khoản
                </h3>
                <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '20px' }}>
                  Điền thông tin cá nhân bên dưới để gửi yêu cầu cấp tài khoản tới Quản trị viên.
                </p>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Họ và tên *</label>
                  <input
                    type="text"
                    required
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    placeholder="Nguyễn Văn A..."
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      background: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      borderRadius: '8px',
                      color: 'var(--text-color)',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Email làm việc *</label>
                  <input
                    type="email"
                    required
                    value={contactEmail}
                    onChange={(e) => setContactEmail(e.target.value)}
                    placeholder="user@company.com..."
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      background: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      borderRadius: '8px',
                      color: 'var(--text-color)',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Số điện thoại (tùy chọn)</label>
                  <input
                    type="text"
                    value={contactPhone}
                    onChange={(e) => setContactPhone(e.target.value)}
                    placeholder="0987654321..."
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      background: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      borderRadius: '8px',
                      color: 'var(--text-color)',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '6px' }}>Ghi chú gửi Admin</label>
                  <textarea
                    rows={3}
                    value={contactNote}
                    onChange={(e) => setContactNote(e.target.value)}
                    placeholder="Lý do cần sử dụng hệ thống..."
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      background: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      borderRadius: '8px',
                      color: 'var(--text-color)',
                      boxSizing: 'border-box',
                      resize: 'none'
                    }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setShowContactModal(false)}
                    style={{
                      padding: '10px 18px',
                      background: 'rgba(255, 255, 255, 0.1)',
                      border: 'none',
                      borderRadius: '8px',
                      color: 'var(--text-color)',
                      cursor: 'pointer'
                    }}
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    disabled={contactLoading}
                    style={{
                      padding: '10px 20px',
                      background: '#10b981',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#fff',
                      fontWeight: 600,
                      cursor: contactLoading ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <Send style={{ width: '16px', height: '16px' }} />
                    <span>Gửi yêu cầu</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
