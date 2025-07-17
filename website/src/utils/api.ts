// API utility functions

/**
 * Get the base URL for API calls
 * In development mode, uses REACT_APP_SERVER_URL if available
 * In production, uses relative paths (same origin)
 */
export const getApiBaseUrl = (): string => {
  if (process.env.NODE_ENV === 'production') {
    // In production, use REACT_APP_SERVER_URL or empty string (relative path)
    return process.env.REACT_APP_SERVER_URL || '';
  }
  // In development, use REACT_APP_SERVER_URL or default to localhost:8000
  return process.env.REACT_APP_SERVER_URL || 'http://localhost:8000';
};

