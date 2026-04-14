import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
  forgotPassword as apiForgotPassword,
  resetPassword as apiResetPassword,
  changePassword as apiChangePassword,
  isAuthenticated as apiIsAuthenticated,
  getToken,
} from '../services/api';

export interface User {
  id: string;
  email: string;
  is_global_admin: boolean;
  role?: string;
}

interface AuthContextProps {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (token: string, newPassword: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextProps | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);

  // On mount, if token exists, set user from token payload (lightweight)
  useEffect(() => {
    if (apiIsAuthenticated()) {
      const token = getToken();
      if (token) {
        try {
          const payload = JSON.parse(atob(token.split('.')[1]));
          setUser({
            id: payload.sub,
            email: payload.email,
            is_global_admin: payload.is_global_admin,
            role: payload.role,
          });
        } catch {
          // ignore malformed token
        }
      }
    }
    setAuthReady(true);
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiLogin(email, password);
    setUser({
      id: data.user.id,
      email: data.user.email,
      is_global_admin: data.user.is_global_admin,
      role: data.user.role,
    });
  };

  const logout = async () => {
    await apiLogout();
    setUser(null);
  };

  const register = async (email: string, password: string) => {
    await apiRegister(email, password);
    // optional: auto‑login after registration
    await login(email, password);
  };

  const forgotPassword = async (email: string) => {
    await apiForgotPassword(email);
  };

  const resetPassword = async (token: string, newPassword: string) => {
    await apiResetPassword(token, newPassword);
  };

  const changePassword = async (currentPassword: string, newPassword: string) => {
    await apiChangePassword(currentPassword, newPassword);
  };

  const isAuthenticated = apiIsAuthenticated();

  const value: AuthContextProps = {
    user,
    login,
    logout,
    register,
    forgotPassword,
    resetPassword,
    changePassword,
    isAuthenticated,
  };

  // Render children only after auth readiness to avoid flashing protected UI
  if (!authReady) return null;
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextProps => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
};
