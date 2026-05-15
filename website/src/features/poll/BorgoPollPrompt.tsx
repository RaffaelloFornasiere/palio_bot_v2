import React, { useEffect, useState } from 'react';
import { getClientId } from '../../utils/clientId';
import { getPollStatus } from '../../utils/pollApi';
import BorgoPollDialog from './BorgoPollDialog';

/* Mounted once in the public Layout. First visit (this device has never
   voted) → auto-open the vote dialog, prominent but dismissable. Once
   dismissed or voted we don't nag again this browser session; a fresh
   session re-prompts only until the device has ever voted. The dialog
   stays reachable any time from the "Borgo più amato" page. */

const SESSION_KEY = 'palio_poll_prompted';

const BorgoPollPrompt: React.FC = () => {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem(SESSION_KEY)) return;
    let alive = true;
    (async () => {
      try {
        const status = await getPollStatus(getClientId());
        if (alive && !status.ever_voted) {
          sessionStorage.setItem(SESSION_KEY, '1');
          setOpen(true);
        }
      } catch {
        /* backend unreachable / poll off: stay silent, never block the app */
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return <BorgoPollDialog open={open} onClose={() => setOpen(false)} />;
};

export default BorgoPollPrompt;
