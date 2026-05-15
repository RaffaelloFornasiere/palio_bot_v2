import React, { useEffect, useRef } from 'react';
import { Box, Typography } from '@mui/material';

/* Cloudflare Turnstile, explicit-render. The token is short-lived and
   single-use: we surface it via onToken and clear it on expiry/error so
   the parent disables submit until a fresh one arrives. Sitekey is the
   PUBLIC key from REACT_APP_TURNSTILE_SITEKEY. */

interface TurnstileApi {
  render: (
    el: HTMLElement,
    opts: {
      sitekey: string;
      theme?: 'light' | 'dark' | 'auto';
      callback: (token: string) => void;
      'expired-callback'?: () => void;
      'error-callback'?: () => void;
    },
  ) => string;
  remove: (id: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT_SRC =
  'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise<void>((resolve, reject) => {
    const s = document.createElement('script');
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('Turnstile script failed to load'));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

interface Props {
  onToken: (token: string | null) => void;
}

const SITEKEY = process.env.REACT_APP_TURNSTILE_SITEKEY;

const Turnstile: React.FC<Props> = ({ onToken }) => {
  const boxRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!SITEKEY || !boxRef.current) return;
    let cancelled = false;
    const el = boxRef.current;

    loadScript()
      .then(() => {
        if (cancelled || !window.turnstile || widgetIdRef.current) return;
        widgetIdRef.current = window.turnstile.render(el, {
          sitekey: SITEKEY,
          theme: 'dark',
          callback: (t) => onToken(t),
          'expired-callback': () => onToken(null),
          'error-callback': () => onToken(null),
        });
      })
      .catch(() => onToken(null));

    return () => {
      cancelled = true;
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          /* widget already gone */
        }
        widgetIdRef.current = null;
      }
    };
  }, [onToken]);

  if (!SITEKEY) {
    return (
      <Typography variant="caption" color="warning.main">
        Verifica anti-bot non configurata (REACT_APP_TURNSTILE_SITEKEY mancante).
      </Typography>
    );
  }

  return <Box ref={boxRef} sx={{ minHeight: 65, display: 'flex', justifyContent: 'center' }} />;
};

export default Turnstile;
