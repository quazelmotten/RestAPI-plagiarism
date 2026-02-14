import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import api from '../services/api';

interface User {
  id: string;
  username: string;
  email: string;
  role: 'teacher' | 'admin';
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setIsLoading(false);
    }
  }, []);

  const fetchUser = async () => {
    try {
      const response = await api.get('/auth/me');
      setUser(response.data);
    } catch (error) {
      localStorage.removeItem('token');
      delete api.defaults.headers.common['Authorization'];
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (username: string, email: string, password: string) => {
    console.log('=== LOGIN FUNCTION START ===');
    console.log('API URL:', api.defaults.baseURL);
    console.log('Attempting login with:', { username, email });
    
    try {
      const loginUrl = '/auth/login';
      console.log('Making POST request to:', loginUrl);
      
      const response = await api.post(loginUrl, { username, email, password });
      
      console.log('Login response received:', response.status);
      console.log('Login response data:', response.data);
      
      // Check if the response contains an error
      if (response.data.detail) {
        throw new Error(response.data.detail);
      }
      
      const { access_token } = response.data;
      
      if (!access_token) {
        throw new Error('No access token received');
      }
      
      localStorage.setItem('token', access_token);
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      await fetchUser();
      navigate('/dashboard');
    } catch (error: any) {
      console.error('=== LOGIN ERROR ===');
      console.error('Error type:', error.constructor.name);
      console.error('Error message:', error.message);
      console.error('Error code:', error.code);
      console.error('Error config:', error.config);
      
      if (error.response) {
        console.error('Error response status:', error.response.status);
        console.error('Error response data:', error.response.data);
        console.error('Error response headers:', error.response.headers);
      } else if (error.request) {
        console.error('Error request:', error.request);
      }
      
      throw new Error(error.response?.data?.detail || error.message || 'Invalid credentials');
    } finally {
      console.log('=== LOGIN FUNCTION END ===');
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    delete api.defaults.headers.common['Authorization'];
    setUser(null);
    navigate('/login');
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
