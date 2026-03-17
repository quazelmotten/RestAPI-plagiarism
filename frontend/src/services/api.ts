import axios from 'axios';
import API_ENDPOINTS from '../constants/api';

const SUBPATH = import.meta.env.VITE_SUBPATH !== undefined ? import.meta.env.VITE_SUBPATH : 'plagitype';
const API_URL = import.meta.env.VITE_API_URL || (SUBPATH ? `http://localhost:8000/${SUBPATH}` : 'http://localhost:8000');

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = SUBPATH ? `/${SUBPATH}/login` : '/login';
    }
    return Promise.reject(error);
  }
);

// Helper function to construct full API path
export const getApiUrl = (endpoint: string): string => {
  const base = api.defaults.baseURL || '';
  return `${base}${endpoint}`;
};

export { API_ENDPOINTS };
export default api;
