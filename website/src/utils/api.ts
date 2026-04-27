// API utility functions

/**
 * Get the base URL for API calls
 * In development mode, uses REACT_APP_SERVER_URL if available
 * In production, uses relative paths (same origin)
 */
export const getApiBaseUrl = (): string => {
  // Default to relative paths in both dev and prod. The CRA dev server has
  // `proxy: http://localhost:8000` in package.json, so /api/* is forwarded
  // to core while the browser stays same-origin — this is what lets the
  // app work behind a Cloudflare tunnel without CORS gymnastics.
  // Set REACT_APP_SERVER_URL only if you need to point at a different host.
  return process.env.REACT_APP_SERVER_URL || '';
};

