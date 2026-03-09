import axios from 'axios';

const backendApi = axios.create({
  baseURL: '/api4',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

backendApi.interceptors.response.use(
  (response) => response,
  (error) => {
    let errorMsg = 'Failed to fetch data. Please try again.';
    const errorData = error.response?.data as { error?: string };
    if (errorData?.error) {
      errorMsg = errorData.error;
    }

    const err = new Error(errorMsg) as Error & { status?: number };
    err.status = error.response?.status;
    return Promise.reject(err);
  },
);

export { backendApi };
export default backendApi;
