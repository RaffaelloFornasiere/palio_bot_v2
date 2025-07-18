// API Configuration
export const API_CONFIG = {
  // Base URL for API calls
  // In development: defaults to localhost:8000 unless REACT_APP_SERVER_URL is set
  // In production: defaults to empty string (relative paths) unless REACT_APP_SERVER_URL is set
  baseUrl: process.env.NODE_ENV === 'production' 
    ? (process.env.REACT_APP_SERVER_URL || '') 
    : (process.env.REACT_APP_SERVER_URL || 'http://localhost:8000'),
    
  // OpenAPI generation URL (used by openapi-ts.config.ts)
  openApiUrl: 'http://localhost:8000/openapi.json'
};