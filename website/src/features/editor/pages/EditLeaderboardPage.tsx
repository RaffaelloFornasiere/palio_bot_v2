import React, { useEffect, useState } from 'react';
import { Outlet, useMatch, useNavigate, useOutletContext } from 'react-router-dom';
import { useEditorSession } from '../hooks/useEditorSession';
import { EditorShell } from '../components/EditorShell';
import { editorApi } from '../api/client';

interface LeaderboardEntry { points: number; position: number }
interface DivisionLeaderboard {
  name: string;
  leaderboard: Record<string, LeaderboardEntry>;
  updated_at?: string | null;
}
interface GameLeaderboard {
  game_id: string;
  game_name: string;
  divisions: DivisionLeaderboard[];
  overall_leaderboard: Record<string, LeaderboardEntry>;
  updated_at?: string | null;
}
export interface LeaderboardData {
  villages: string[];
  palio_leaderboard: Record<string, LeaderboardEntry>;
  game_leaderboards: Record<string, GameLeaderboard>;
}

export interface LeaderboardOutletContext {
  content: LeaderboardData;
  setContent: (updater: (prev: LeaderboardData) => LeaderboardData) => void;
  villages: string[];
}

export const useLeaderboardContext = () =>
  useOutletContext<LeaderboardOutletContext>();

const EditLeaderboardPage: React.FC = () => {
  const session = useEditorSession<LeaderboardData>('leaderboard', 'manual_edit_leaderboard');
  const [villages, setVillages] = useState<string[]>([]);
  const navigate = useNavigate();
  const onDetail = useMatch('/edit/leaderboard/:gameId');

  useEffect(() => {
    editorApi
      .readFile<{ villages?: string[] }>('palio')
      .then((p) => setVillages(p.villages ?? []))
      .catch(() => setVillages([]));
  }, []);

  // Resolve villages: prefer palio.json, fall back to leaderboard's own
  // copy if the read failed.
  const effectiveVillages =
    villages.length > 0 ? villages : session.content?.villages ?? [];

  const onBack = onDetail ? () => navigate('/edit/leaderboard') : undefined;
  const title = onDetail ? 'Classifica · gioco' : 'Classifica';

  return (
    <EditorShell title={title} session={session} onBack={onBack}>
      {(content) => (
        <Outlet
          context={{
            content,
            setContent: session.setContent,
            villages: effectiveVillages,
          } satisfies LeaderboardOutletContext}
        />
      )}
    </EditorShell>
  );
};

export default EditLeaderboardPage;
