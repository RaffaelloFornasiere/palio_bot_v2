import React, { useEffect, useState } from 'react';
import { useEditorSession } from '../hooks/useEditorSession';
import { EditorShell } from '../components/EditorShell';
import { JsonForm } from '../components/JsonForm';
import { gameStatusSchema } from '../schema';
import { editorApi } from '../api/client';

interface GameStatus {
  game_scores: Record<string, any>;
  last_updated: string;
}

const EditGameStatusPage: React.FC = () => {
  const session = useEditorSession<GameStatus>('palio_games_status', 'manual_edit_games');
  const [villages, setVillages] = useState<string[]>([]);

  useEffect(() => {
    editorApi
      .readFile<{ villages?: string[] }>('palio')
      .then((p) => setVillages(p.villages ?? []))
      .catch(() => setVillages([]));
  }, []);

  return (
    <EditorShell title="Stato giochi" session={session}>
      {(content) => (
        <JsonForm
          value={content}
          onChange={(nv) => session.setContent(() => nv)}
          hint={gameStatusSchema}
          villages={villages}
        />
      )}
    </EditorShell>
  );
};

export default EditGameStatusPage;
