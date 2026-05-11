import React, { useEffect, useState } from 'react';
import { Outlet, useMatch, useNavigate, useOutletContext } from 'react-router-dom';
import { useEditorSession } from '../hooks/useEditorSession';
import { EditorShell } from '../components/EditorShell';
import { editorApi } from '../api/client';

interface GameStatus {
  game_scores: Record<string, any>;
  last_updated: string;
}

export interface PalioGameMeta {
  id: string;
  name: string;
  type?: string;
}

export interface GameStatusOutletContext {
  content: GameStatus;
  setContent: (updater: (prev: GameStatus) => GameStatus) => void;
  villages: string[];
  games: PalioGameMeta[];
}

export const useGameStatusContext = () =>
  useOutletContext<GameStatusOutletContext>();

const EditGameStatusPage: React.FC = () => {
  const session = useEditorSession<GameStatus>('palio_games_status', 'manual_edit_games');
  const [villages, setVillages] = useState<string[]>([]);
  const [games, setGames] = useState<PalioGameMeta[]>([]);
  const navigate = useNavigate();
  const onDetail = useMatch('/edit/games/:gameId');

  useEffect(() => {
    editorApi
      .readFile<{ villages?: string[]; games?: PalioGameMeta[] }>('palio')
      .then((p) => {
        setVillages(p.villages ?? []);
        setGames(p.games ?? []);
      })
      .catch(() => {
        setVillages([]);
        setGames([]);
      });
  }, []);

  // On the detail page, the top-bar back returns to the list (preserving
  // the open session). On the list page, the default (discard + go home)
  // applies.
  const onBack = onDetail ? () => navigate('/edit/games') : undefined;
  const title = onDetail ? 'Stato giochi · gioco' : 'Stato giochi';

  return (
    <EditorShell
      title={title}
      session={session}
      onBack={onBack}
      promptRecomputeLeaderboard
    >
      {(content) => (
        <Outlet
          context={{
            content,
            setContent: session.setContent,
            villages,
            games,
          } satisfies GameStatusOutletContext}
        />
      )}
    </EditorShell>
  );
};

export default EditGameStatusPage;
