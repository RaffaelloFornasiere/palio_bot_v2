// Explicit CRA dev-server proxy. Forwards /api/* and WebSocket /events to
// palio-core. Overrides the simpler `"proxy"` field in package.json — CRA
// picks this file up automatically when present, and the per-path config
// is more reliable behind tunnels / when the request's Accept header varies.
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  const target = process.env.PALIO_CORE_URL || 'http://localhost:8000';

  // Without an error handler, an upstream socket reset (core restart,
  // WS disconnect) bubbles up as an unhandled 'error' event and kills
  // the whole dev server.
  const onError = (label) => (err, req, res) => {
    console.warn(`[proxy ${label}] ${err.code || err.message}`);
    if (res && !res.headersSent && typeof res.writeHead === 'function') {
      try {
        res.writeHead(502, { 'Content-Type': 'text/plain' });
        res.end('upstream unreachable');
      } catch (_) { /* socket already gone */ }
    } else if (res && typeof res.destroy === 'function') {
      res.destroy();
    }
  };

  app.use(
    '/api',
    createProxyMiddleware({
      target,
      changeOrigin: true,
      onError: onError('api'),
    }),
  );

  app.use(
    '/events',
    createProxyMiddleware({
      target,
      changeOrigin: true,
      ws: true,
      onError: onError('events'),
    }),
  );
};
