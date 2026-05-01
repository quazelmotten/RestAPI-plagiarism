import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import API_ENDPOINTS from '../constants/api';
import { getSubpath, getBasePath } from '../utils/subpath';

const API_URL = import.meta.env.VITE_API_URL || (() => {
  const subpath = getSubpath();
  return subpath ? `/${subpath}` : '';
})();

const TOKEN_KEY = 'auth_token';

export const setToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
};

export const isAuthenticated = (): boolean => {
  return !!getToken();
};

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important for HttpOnly cookies to work
});

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const response = await api.post('/auth/refresh', {});
        if (response.data.access_token) {
          setToken(response.data.access_token);
        }
        // Retry original request with new token
        return api(originalRequest);
      } catch (e) {
        // Refresh failed – clear tokens and redirect
        removeToken();
        window.location.href = `${getBasePath()}/login`;
        return Promise.reject(error);
      }
    }
    if (error.response?.status === 401) {
      removeToken();
      window.location.href = `${getBasePath()}/login`;
    }
    return Promise.reject(error);
  }
);

export const getApiUrl = (endpoint: string): string => {
  const base = api.defaults.baseURL || '';
  return `${base}${endpoint}`;
};

export const login = async (email: string, password: string) => {
  const response = await api.post('/auth/login', { email, password });
  if (response.data.access_token) {
    setToken(response.data.access_token);
  }
  return response.data;
};

export const register = async (email: string, password: string) => {
  const response = await api.post('/auth/register', { email, password });
  // Save the access token from registration (auto sign-in)
  if (response.data.access_token) {
    setToken(response.data.access_token);
  }
  return response.data;
};

export const forgotPassword = async (email: string) => {
  const response = await api.post('/auth/forgot-password', { email });
  return response.data;
};

export const resetPassword = async (token: string, newPassword: string) => {
  const response = await api.post('/auth/reset-password', { token, new_password: newPassword });
  return response.data;
};

export const changePassword = async (currentPassword: string, newPassword: string) => {
  const response = await api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword });
  return response.data;
};

export const refreshToken = async () => {
  // Refresh token is now stored in HttpOnly cookie, no need to send it manually
  const response = await api.post('/auth/refresh', {});
  if (response.data.access_token) {
    setToken(response.data.access_token);
  }
  return response.data;
};

export const logout = async () => {
  try {
    await api.post('/auth/logout');
  } catch (e) {
    // ignore errors, still clear local tokens
  }
  removeToken();
};

// Admin user management functions
export const getUsers = async () => {
  const response = await api.get('/auth/users');
  return response.data;
};

export const getUser = async (userId: string) => {
  const response = await api.get(`/auth/users/${userId}`);
  return response.data;
};

export const deleteUser = async (userId: string) => {
  await api.delete(`/auth/users/${userId}`);
};

export const updateUserGlobalRole = async (userId: string, isGlobalAdmin: boolean) => {
  const response = await api.put(`/auth/users/${userId}/global-role`, { is_global_admin: isGlobalAdmin });
  return response.data;
};

export const adminChangePassword = async (userId: string, newPassword: string) => {
  await api.post(`/auth/users/${userId}/change-password`, { new_password: newPassword });
};

export const restoreAssignment = (id: string) => 
  api.post(`${API_ENDPOINTS.ASSIGNMENTS}/${id}/restore`);

export const restoreSubject = (id: string) => 
  api.post(`${API_ENDPOINTS.SUBJECTS}/${id}/restore`);

export { API_ENDPOINTS };
export default api;