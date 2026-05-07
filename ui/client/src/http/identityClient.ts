import axios from 'axios';

/**
 * Axios instance for Identity APIs (directory, teams, non-auth JSON calls).
 * Proxied via /api3 -> http://127.0.0.1:13456/api
 */
export const identityApi = axios.create({
  baseURL: '/api3',
  timeout: 20000,
  withCredentials: true,
});

identityApi.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('Identity API Error:', error);
    return Promise.reject(error);
  },
);

export default identityApi;
