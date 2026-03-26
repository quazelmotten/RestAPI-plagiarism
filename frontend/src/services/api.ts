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

// Helper function to construct full API path
export const getApiUrl = (endpoint: string): string => {
  const base = api.defaults.baseURL || '';
  return `${base}${endpoint}`;
};

export { API_ENDPOINTS };
export default api;
