import axios from 'axios';

/**
 * Axios instance for the SSO backend (directory, identity, teams).
 * Proxied via /api3 -> http://127.0.0.1:13456/api
 */
export const ssoApi = axios.create({
  baseURL: '/api3',
  timeout: 20000,
  withCredentials: true,
});

ssoApi.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('SSO API Error:', error);
    return Promise.reject(error);
  },
);

export default ssoApi;
