import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Attach token synchronously to any outgoing request
axios.interceptors.request.use(
  (config) => {
    const storedToken = localStorage.getItem('access_token');
    if (storedToken) {
      config.headers.Authorization = `Bearer ${storedToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('access_token') || null);
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user_info');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
  };

  // Setup Response Interceptor to handle 401 (excluding login attempts)
  useEffect(() => {
    const resInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (
          error.response && 
          error.response.status === 401 && 
          !error.config?.url?.includes('/auth/login')
        ) {
          console.warn("401 Unauthorized received. Logging out...");
          logout();
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.response.eject(resInterceptor);
    };
  }, []);

  // Fetch current user details on initial load if token exists
  useEffect(() => {
    let isMounted = true;
    if (token) {
      axios.get(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      .then((res) => {
        if (isMounted) {
          setUser(res.data);
          localStorage.setItem('user_info', JSON.stringify(res.data));
        }
      })
      .catch((err) => {
        console.error("Failed to validate token on startup:", err);
        if (isMounted) {
          logout();
        }
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });
    } else {
      setLoading(false);
    }

    return () => {
      isMounted = false;
    };
  }, [token]);

  const login = async (username, password) => {
    const res = await axios.post(`${API_BASE_URL}/auth/login`, { username, password });
    const { access_token, user: userInfo } = res.data;
    setToken(access_token);
    setUser(userInfo);
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('user_info', JSON.stringify(userInfo));
    return userInfo;
  };

  const updateUserProfile = (updatedUser) => {
    setUser(updatedUser);
    localStorage.setItem('user_info', JSON.stringify(updatedUser));
  };

  const value = {
    token,
    user,
    role: user?.role || 'USER',
    isAuthenticated: !!token && !!user,
    loading,
    login,
    logout,
    updateUserProfile
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
