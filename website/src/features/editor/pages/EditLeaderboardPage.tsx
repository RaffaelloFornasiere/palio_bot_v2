import React from 'react';
import { useEditorSession } from '../hooks/useEditorSession';
import { EditorShell } from '../components/EditorShell';
import { JsonForm } from '../components/JsonForm';
import { leaderboardSchema } from '../schema';

interface Leaderboard {
  villages: string[];
  palio_leaderboard: Record<string, { points: number; position: number }>;
  game_leaderboards: Record<string, any>;
}

const EditLeaderboardPage: React.FC = () => {
  const session = useEditorSession<Leaderboard>('leaderboard', 'manual_edit_leaderboard');

  return (
    <EditorShell title="Classifica" session={session}>
      {(content) => (
        <JsonForm
          value={content}
          onChange={(nv) => session.setContent(() => nv)}
          hint={leaderboardSchema}
          villages={content.villages ?? []}
        />
      )}
    </EditorShell>
  );
};

export default EditLeaderboardPage;
