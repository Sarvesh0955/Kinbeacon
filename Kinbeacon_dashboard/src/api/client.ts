import axios from 'axios';

// Get API Key from localStorage if configured
export const getApiKey = (): string | null => {
  return localStorage.getItem('kinbeacon_api_key');
};

export const setApiKey = (key: string | null) => {
  if (key) {
    localStorage.setItem('kinbeacon_api_key', key);
  } else {
    localStorage.removeItem('kinbeacon_api_key');
  }
};

export const api = axios.create({
  baseURL: '', // Vite proxy handles /api and /health
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to attach optional X-API-Key
api.interceptors.request.use((config) => {
  const key = getApiKey();
  if (key) {
    config.headers['X-API-Key'] = key;
  }
  return config;
});

// Response error handler to extract structured backend messages
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    if (error.response?.data?.message) {
      return error.response.data.message;
    }
    if (error.response?.data?.detail) {
      return typeof error.response.data.detail === 'string'
        ? error.response.data.detail
        : JSON.stringify(error.response.data.detail);
    }
    if (error.response?.data?.error) {
      return error.response.data.error;
    }
    if (error.message) {
      return error.message;
    }
  }
  return 'An unexpected error occurred';
};
