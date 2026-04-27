// API Configuration
export const API_CONFIG = {
  // Base URL for API calls. Defaults to relative paths (same-origin). The
  // CRA dev server has `proxy: http://localhost:8000` in package.json which
  // forwards /api/* to core, so dev and prod behave identically.
  baseUrl: process.env.REACT_APP_SERVER_URL || '',

  // OpenAPI generation URL (used by openapi-ts.config.ts)
  openApiUrl: 'http://localhost:8000/openapi.json'
};