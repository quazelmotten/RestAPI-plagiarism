import axios from 'axios';
import API_ENDPOINTS from '../constants/api';
import { getSubpath } from '../utils/subpath';

// Priority: explicit VITE_API_URL > relative URL (same-origin prod) > localhost (dev fallback)
// Relative '' resolves against current origin at request time → works in Docker (same-origin)
// For local dev without proxy, set: VITE_API_URL=http://localhost:8000/plagitype
const API_URL = import.meta.env.VITE_API_URL || (() => {
  const subpath = getSubpath();
  return subpath ? `/${subpath}` : '';
})();

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

// Assignment APIs
export const restoreAssignment = (id: string) => 
  api.post(`${API_ENDPOINTS.ASSIGNMENTS}/${id}/restore`);

// Subject APIs
export const restoreSubject = (id: string) => 
  api.post(`${API_ENDPOINTS.SUBJECTS}/${id}/restore`);

export { API_ENDPOINTS };
export default api;
