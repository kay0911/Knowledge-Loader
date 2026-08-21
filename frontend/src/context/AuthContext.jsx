import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('access_token') || null);
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user_info');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  // Setup Axios Authorization Interceptor
  useEffect(() => {
    const reqInterceptor = axios.interceptors.request.use(
      (config) => {
        const storedToken = localStorage.getItem('access_token');
        if (storedToken) {
          config.headers.Authorization = `Bearer ${storedToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    const resInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          // Unauthenticated token expired
          logout();
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(reqInterceptor);
      axios.interceptors.response.eject(resInterceptor);
    };
  }, []);

  // Fetch current user details on initial load if token exists
  useEffect(() => {
    if (token) {
      axios.get(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      .then((res) => {
        setUser(res.data);
        localStorage.setItem('user_info', JSON.stringify(res.data));
      })
      .catch(() => {
        logout();
      })
      .finally(() => {
        setLoading(false);
      });
    } else {
      setLoading(false);
    }
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

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
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
