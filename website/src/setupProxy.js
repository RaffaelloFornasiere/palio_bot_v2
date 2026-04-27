// Explicit CRA dev-server proxy. Forwards /api/* and WebSocket /events to
// palio-core on localhost:8000. Overrides the simpler `"proxy"` field in
// package.json — CRA picks this file up automatically when present, and
// the per-path config is more reliable behind tunnels / when the request's
// Accept header varies.
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  const target = process.env.PALIO_CORE_URL || 'http://localhost:8000';

  app.use(
    '/api',
    createProxyMiddleware({
      target,
      changeOrigin: true,
    }),
  );

  app.use(
    '/events',
    createProxyMiddleware({
      target,
      changeOrigin: true,
      ws: true,
    }),
  );
};
