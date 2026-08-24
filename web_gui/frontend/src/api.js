import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 5000,
});

// O17: if a control token was fetched from /api/config/control_token and
// stored in sessionStorage, every REST request carries it. No token stored →
// no header → matches the no-token-configured backend exactly.
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('control_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** Append the control token to a WebSocket URL (`?token=`) when configured. */
export function withWsToken(url) {
  const token = sessionStorage.getItem('control_token');
  if (!token) return url;
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export function getWsUrl() {
  const base = API_BASE.replace(/^http/, 'ws');
  return `${base}/ws/stream`;
}
