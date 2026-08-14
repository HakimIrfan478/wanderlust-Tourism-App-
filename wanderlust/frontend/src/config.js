import Constants from 'expo-constants';
import { Platform } from 'react-native';

/**
 * Where the Django API lives.
 *
 * Getting this wrong is the most common reason the app shows "Is the backend
 * running?", because `localhost` on a phone means the phone itself. So rather
 * than hardcoding one host, we work it out:
 *
 *  1. `EXPO_PUBLIC_API_URL` in the environment, if you set one.
 *  2. The machine running Metro. Expo tells the app which host it was served
 *    from, and that is almost always the same machine running Django — so a
 *    physical device over Wi-Fi works with no edit at all.
 *  3. Platform defaults: 10.0.2.2 for the Android emulator (its alias for the
 *     host loopback), 127.0.0.1 elsewhere.
 *
 * Start Django with `python manage.py runserver 0.0.0.0:8000` so it accepts
 * connections from the phone, not just from the machine it runs on.
 */
const API_PORT = 8000;

function hostFromExpo() {
  const hostUri =
    Constants.expoConfig?.hostUri ||
    Constants.expoGoConfig?.debuggerHost ||
    Constants.manifest2?.extra?.expoGo?.debuggerHost ||
    '';
  const host = hostUri.split(':')[0];
  // Ignore the tunnel/web cases, where the Metro host is not the API host.
  if (!host || host === 'localhost' || host.includes('exp.direct')) return null;
  return host;
}

function resolveBaseUrl() {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL.replace(/\/$/, '');
  }
  const lanHost = hostFromExpo();
  if (lanHost) return `http://${lanHost}:${API_PORT}`;
  if (Platform.OS === 'android') return `http://10.0.2.2:${API_PORT}`;
  return `http://127.0.0.1:${API_PORT}`;
}

export const API_BASE_URL = resolveBaseUrl();

export const API = {
  base: API_BASE_URL,

  // auth
  register: '/api/auth/register/',
  token: '/api/auth/token/',
  refresh: '/api/auth/token/refresh/',
  me: '/api/auth/me/',
  favorites: '/api/auth/favorites/',

  // catalogue
  destinations: '/api/destinations/',
  facets: '/api/destinations/facets/',

  // recommender
  recommendations: '/api/recommendations/',
  compare: '/api/recommendations/compare/',
  models: '/api/recommendations/models/',

  // evaluation
  evaluation: '/api/evaluation/',
  evaluationQueries: '/api/evaluation/queries/',

  // external data
  weather: '/api/integrations/weather/',
  country: '/api/integrations/country/',
  context: '/api/integrations/context/',
};

/** Model ids, kept in sync with recommendations/engine.py. */
export const MODELS = {
  SEMANTIC: 'semantic',
  TFIDF: 'tfidf',
};
