import { useEffect, useState } from 'react';
import { getPalioDataForYear } from '../../utils/yearApi';

/* Canonical borgo names + raw colours for the current (or selected) year,
   pulled from palio.json — the same source the backend validates votes
   against. */
export interface PalioVillages {
  villages: string[];
  colors: Record<string, string>;
  loading: boolean;
}

export function usePalioVillages(year?: number): PalioVillages {
  const [state, setState] = useState<PalioVillages>({
    villages: [],
    colors: {},
    loading: true,
  });

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res: any = await getPalioDataForYear(year);
        const palio = res?.data;
        if (alive && palio) {
          setState({
            villages: palio.villages || [],
            colors: palio.villages_colors || {},
            loading: false,
          });
          return;
        }
      } catch {
        /* fall through to empty */
      }
      if (alive) setState((s) => ({ ...s, loading: false }));
    })();
    return () => {
      alive = false;
    };
  }, [year]);

  return state;
}
