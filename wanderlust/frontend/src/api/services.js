import client from './client';
import { API } from '../config';

export const AuthAPI = {
  register: (payload) => client.post(API.register, payload),
  login: (username, password) => client.post(API.token, { username, password }),
  me: () => client.get(API.me),
  updateMe: (payload) => client.patch(API.me, payload),
  favorites: () => client.get(API.favorites),
  toggleFavorite: (destinationId) =>
    client.post(`${API.favorites}${destinationId}/`),
};

export const DestinationAPI = {
  list: (params = {}) => client.get(API.destinations, { params }),
  detail: (id) => client.get(`${API.destinations}${id}/`),
  facets: () => client.get(API.facets),
  reviews: (id) => client.get(`${API.destinations}${id}/reviews/`),
  addReview: (id, rating, comment) =>
    client.post(`${API.destinations}${id}/reviews/`, { rating, comment }),
};

export const RecommendAPI = {
  /** Rank with one named model. `model` is 'semantic', 'tfidf', or null for the default. */
  get: (query, { model = null, category = null, topK = 6, personalize = false } = {}) =>
    client.post(API.recommendations, {
      query,
      model,
      category,
      top_k: topK,
      personalize,
    }),

  /** Run both models over the same query and get the agreement stats back. */
  compare: (query, { category = null, topK = 5 } = {}) =>
    client.post(API.compare, { query, category, top_k: topK }),

  /** Which backends this deployment can actually run. */
  models: () => client.get(API.models),
};

export const EvaluationAPI = {
  results: (full = false) =>
    client.get(API.evaluation, { params: full ? { full: 1 } : {} }),
  queries: () => client.get(API.evaluationQueries),
};

export const IntegrationAPI = {
  /** Weather and country facts for a destination in a single round trip. */
  context: (destinationId) =>
    client.get(API.context, { params: { destination: destinationId } }),
  weather: (destinationId) =>
    client.get(API.weather, { params: { destination: destinationId } }),
  country: (destinationId) =>
    client.get(API.country, { params: { destination: destinationId } }),
};
