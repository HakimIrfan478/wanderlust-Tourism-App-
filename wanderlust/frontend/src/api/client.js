import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL } from '../config';

export const TOKEN_KEY = 'wl_access_token';
export const REFRESH_KEY = 'wl_refresh_token';

// 30s rather than the usual 15s: the very first recommendation request after a
// cold server start can wait on the sentence-transformer loading (~10s). The
// backend warms the model at startup so this should not normally be hit, but a
// timeout shorter than the worst case turns a slow first request into a
// spurious "is the backend running?" error.
const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach the JWT access token to every request, if present.
client.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, try a one-time refresh; if that fails, clear tokens.
let isRefreshing = false;

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !isRefreshing
    ) {
      original._retry = true;
      isRefreshing = true;
      try {
        const refresh = await AsyncStorage.getItem(REFRESH_KEY);
        if (refresh) {
          const res = await axios.post(`${API_BASE_URL}/api/auth/token/refresh/`, {
            refresh,
          });
          await AsyncStorage.setItem(TOKEN_KEY, res.data.access);
          original.headers.Authorization = `Bearer ${res.data.access}`;
          isRefreshing = false;
          return client(original);
        }
      } catch (e) {
        // fall through to clearing tokens
      }
      isRefreshing = false;
      await AsyncStorage.multiRemove([TOKEN_KEY, REFRESH_KEY]);
    }
    return Promise.reject(error);
  }
);

export default client;
