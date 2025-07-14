// API utility functions

/**
 * Get the base URL for API calls
 * In development mode, uses REACT_APP_SERVER_URL if available
 * In production, uses relative paths (same origin)
 */
export const getApiBaseUrl = (): string => {
  if (process.env.NODE_ENV === 'development' && process.env.REACT_APP_SERVER_URL) {
    return process.env.REACT_APP_SERVER_URL;
  }
  return '';
};

/**
 * Make an API call with the correct base URL
 */
export const apiCall = async (endpoint: string, options?: RequestInit): Promise<Response> => {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;
  
  return fetch(url, options);
};