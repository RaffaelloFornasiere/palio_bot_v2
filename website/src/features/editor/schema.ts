import { Hint } from './components/JsonForm';

const STATUS_OPTIONS = ['not-started', 'in-progress', 'completed'];

const leaderboardEntryHint: Hint = {
  kind: 'object',
  fields: [
    { name: 'points', label: 'Punti', hint: { kind: 'integer' } },
    { name: 'position', label: 'Posizione', hint: { kind: 'integer' } },
  ],
};

const villagePointsDict: Hint = {
  kind: 'dict',
  keyHint: 'village',
  value: leaderboardEntryHint,
  defaultValue: () => ({ points: 0, position: 0 }),
  presentation: 'table',
};

// Just the palio leaderboard map (village → {points, position}). Shown on
// the leaderboard home page, editable behind a toggle.
export const palioLeaderboardHint: Hint = villagePointsDict;

// One game's leaderboard entry. Used in the per-game detail view.
export const singleGameLeaderboardHint: Hint = {
  kind: 'object',
  fields: [
    { name: 'game_name', label: 'Nome gioco', hint: { kind: 'string' } },
    {
      name: 'updated_at',
      label: 'Aggiornato il',
      optional: true,
      hint: { kind: 'nullable', inner: { kind: 'string' } },
    },
    {
      name: 'overall_leaderboard',
      label: 'Classifica generale',
      collapsible: true,
      hint: villagePointsDict,
    },
    {
      name: 'divisions',
      label: 'Divisioni',
      collapsible: true,
      hint: {
        kind: 'array',
        itemLabel: (i, v) => v?.name || `Divisione ${i + 1}`,
        defaultItem: () => ({ name: '', leaderboard: {}, updated_at: null }),
        item: {
          kind: 'object',
          fields: [
            { name: 'name', label: 'Nome', hint: { kind: 'string' } },
            {
              name: 'updated_at',
              label: 'Aggiornato il',
              optional: true,
              hint: { kind: 'nullable', inner: { kind: 'string' } },
            },
            {
              name: 'leaderboard',
              label: 'Punteggi',
              hint: villagePointsDict,
            },
          ],
        },
      },
    },
  ],
};

// Game status schema

const scorePenaltyHint: Hint = {
  kind: 'object',
  fields: [
    { name: 'village', label: 'Borgo', hint: { kind: 'village' } },
    { name: 'description', label: 'Descrizione', hint: { kind: 'string' } },
    { name: 'points', label: 'Punti', hint: { kind: 'number' } },
  ],
};

const gameBonusHint: Hint = {
  kind: 'object',
  fields: [
    { name: 'village', label: 'Borgo', hint: { kind: 'village' } },
    { name: 'description', label: 'Descrizione', hint: { kind: 'string' } },
    { name: 'points', label: 'Punti', hint: { kind: 'integer' } },
  ],
};

const gamePenaltyHint: Hint = gameBonusHint;

const roundRobinScoreHint: Hint = {
  kind: 'object',
  fields: [
    { name: 'village', label: 'Borgo', hint: { kind: 'village' } },
    { name: 'points', label: 'Punti', hint: { kind: 'numberOrString' } },
  ],
};

const gameRoundHint: Hint = {
  kind: 'object',
  fields: [
    {
      name: 'scores',
      label: 'Punteggi',
      hint: {
        kind: 'array',
        itemLabel: (_, v) => v?.village || 'borgo',
        defaultItem: () => ({ village: '', points: 0 }),
        item: roundRobinScoreHint,
      },
    },
    {
      name: 'score_penalties',
      label: 'Penalità',
      collapsible: true,
      hint: {
        kind: 'array',
        itemLabel: (_, v) => v?.village ? `${v.village} (${v.points})` : 'penalità',
        defaultItem: () => ({ village: '', description: '', points: 0 }),
        item: scorePenaltyHint,
      },
    },
  ],
};

export type GameVariant = 'score-based' | 'round-robin';

type ObjectField = Extract<Hint, { kind: 'object' }>['fields'][number];

// Variant-aware single-game hint. When `type` is known the form prunes the
// branch of the other variant so the user only sees one "Aggiungi …" button.
// When `type` is undefined we fall back to a permissive union — useful for
// generic editors that don't know the game type.
export function singleGameStatusHintFor(type?: GameVariant): Hint {
  const showScores = type !== 'round-robin';
  const showRounds = type !== 'score-based';

  const scoresField: ObjectField = {
    name: 'scores',
    label: showRounds ? 'Punteggi (score-based)' : 'Punteggi',
    optional: true,
    collapsible: true,
    hint: {
      kind: 'dict',
      keyHint: 'village',
      value: { kind: 'numberOrString' },
      defaultValue: () => 0,
    },
    defaultValue: () => ({}),
  };

  const scorePenaltiesField: ObjectField = {
    name: 'score_penalties',
    label: showRounds ? 'Penalità punteggio (score-based)' : 'Penalità punteggio',
    optional: true,
    collapsible: true,
    hint: {
      kind: 'array',
      itemLabel: (_, v) => v?.village || 'penalità',
      defaultItem: () => ({ village: '', description: '', points: 0 }),
      item: scorePenaltyHint,
    },
    defaultValue: () => [],
  };

  const roundsField: ObjectField = {
    name: 'rounds',
    label: showScores ? 'Round (round-robin)' : 'Round',
    optional: true,
    collapsible: true,
    hint: {
      kind: 'nullable',
      inner: {
        kind: 'array',
        itemLabel: (i) => `Round ${i + 1}`,
        defaultItem: () => ({ scores: [], score_penalties: [] }),
        item: gameRoundHint,
      },
    },
    defaultValue: () => [],
  };

  const appliedBonusesField: ObjectField = {
    name: 'applied_bonuses',
    label: 'Bonus di gioco',
    collapsible: true,
    hint: {
      kind: 'array',
      itemLabel: (_, v) => v?.village ? `${v.village} (+${v.points})` : 'bonus',
      defaultItem: () => ({ village: '', description: '', points: 0 }),
      item: gameBonusHint,
    },
  };

  const appliedPenaltiesField: ObjectField = {
    name: 'applied_penalties',
    label: 'Penalità di gioco',
    collapsible: true,
    hint: {
      kind: 'array',
      itemLabel: (_, v) => v?.village ? `${v.village} (${v.points})` : 'penalità',
      defaultItem: () => ({ village: '', description: '', points: 0 }),
      item: gamePenaltyHint,
    },
  };

  // Divisions inherit the parent game's variant.
  const divisionItemFields: ObjectField[] = [
    { name: 'name', label: 'Nome', hint: { kind: 'string' } },
    { name: 'status', label: 'Stato', hint: { kind: 'enum', options: STATUS_OPTIONS } },
  ];
  if (showScores) {
    divisionItemFields.push({
      name: 'scores', label: 'Punteggi',
      hint: {
        kind: 'dict',
        keyHint: 'village',
        value: { kind: 'numberOrString' },
        defaultValue: () => 0,
      },
    });
  }
  if (showRounds) {
    divisionItemFields.push({
      name: 'rounds', label: 'Round', optional: true, collapsible: true,
      hint: {
        kind: 'nullable',
        inner: {
          kind: 'array',
          itemLabel: (i) => `Round ${i + 1}`,
          defaultItem: () => ({ scores: [], score_penalties: [] }),
          item: gameRoundHint,
        },
      },
      defaultValue: () => [],
    });
  }
  if (showScores) {
    divisionItemFields.push({
      name: 'score_penalties', label: 'Penalità punteggio', optional: true, collapsible: true,
      hint: {
        kind: 'array',
        itemLabel: (_, v) => v?.village || 'penalità',
        defaultItem: () => ({ village: '', description: '', points: 0 }),
        item: scorePenaltyHint,
      },
      defaultValue: () => [],
    });
  }
  divisionItemFields.push(
    {
      name: 'applied_bonuses', label: 'Bonus applicati', optional: true, collapsible: true,
      hint: {
        kind: 'array',
        itemLabel: (_, v) => v?.village || 'bonus',
        defaultItem: () => ({ village: '', description: '', points: 0 }),
        item: gameBonusHint,
      },
      defaultValue: () => [],
    },
    {
      name: 'applied_penalties', label: 'Penalità applicate', optional: true, collapsible: true,
      hint: {
        kind: 'array',
        itemLabel: (_, v) => v?.village || 'penalità',
        defaultItem: () => ({ village: '', description: '', points: 0 }),
        item: gamePenaltyHint,
      },
      defaultValue: () => [],
    },
  );

  const divisionsField: ObjectField = {
    name: 'divisions',
    label: 'Divisioni',
    optional: true,
    collapsible: true,
    hint: {
      kind: 'nullable',
      inner: {
        kind: 'array',
        itemLabel: (i, v) => v?.name || `Divisione ${i + 1}`,
        defaultItem: () => {
          const def: Record<string, any> = {
            name: '',
            status: STATUS_OPTIONS[0],
            applied_bonuses: [],
            applied_penalties: [],
          };
          if (showScores) def.scores = {};
          return def;
        },
        item: { kind: 'object', fields: divisionItemFields },
      },
    },
    defaultValue: () => [],
  };

  const fields: ObjectField[] = [
    { name: 'status', label: 'Stato', hint: { kind: 'enum', options: STATUS_OPTIONS } },
    ...(showScores ? [scoresField, scorePenaltiesField] : []),
    ...(showRounds ? [roundsField] : []),
    divisionsField,
    appliedBonusesField,
    appliedPenaltiesField,
  ];

  return { kind: 'object', fields };
}

// Permissive union (both variants visible) — used by callers that don't
// know the game type.
export const singleGameStatusHint: Hint = singleGameStatusHintFor();

export const gameStatusSchema: Hint = {
  kind: 'object',
  fields: [
    { name: 'last_updated', label: 'Aggiornato il', hint: { kind: 'string' } },
    {
      name: 'game_scores',
      label: 'Giochi',
      hint: {
        kind: 'dict',
        value: singleGameStatusHint,
        defaultValue: () => ({
          status: STATUS_OPTIONS[0],
          applied_bonuses: [],
          applied_penalties: [],
        }),
      },
    },
  ],
};
