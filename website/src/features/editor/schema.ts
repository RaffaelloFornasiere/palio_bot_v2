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

export const leaderboardSchema: Hint = {
  kind: 'object',
  fields: [
    {
      name: 'villages',
      label: 'Borghi',
      hint: {
        kind: 'array',
        item: { kind: 'string' },
        defaultItem: () => '',
        itemLabel: (_, v) => v || '(vuoto)',
      },
    },
    {
      name: 'palio_leaderboard',
      label: 'Classifica Palio',
      collapsible: true,
      hint: villagePointsDict,
    },
    {
      name: 'game_leaderboards',
      label: 'Classifiche per gioco',
      collapsible: true,
      hint: {
        kind: 'dict',
        valueLabel: (v: any) => v?.game_name || '(senza nome)',
        value: {
          kind: 'object',
          fields: [
            { name: 'game_name', label: 'Nome gioco', hint: { kind: 'string' } },
            {
              name: 'completed',
              label: 'Completato',
              optional: true,
              hint: { kind: 'nullable', inner: { kind: 'boolean' } },
            },
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
        },
        defaultValue: () => ({
          game_name: '',
          divisions: [],
          overall_leaderboard: {},
          completed: true,
          updated_at: null,
        }),
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

// Union-aware single-game hint: fields exist depending on the game variant.
// Both variants share status + applied_bonuses + applied_penalties. The rest
// are marked optional so the form only renders what's present in the data.
export const singleGameStatusHint: Hint = {
  kind: 'object',
  fields: [
    { name: 'status', label: 'Stato', hint: { kind: 'enum', options: STATUS_OPTIONS } },

    // score-based only
    {
      name: 'scores',
      label: 'Punteggi (score-based)',
      optional: true,
      collapsible: true,
      hint: {
        kind: 'dict',
        keyHint: 'village',
        value: { kind: 'numberOrString' },
        defaultValue: () => 0,
      },
      defaultValue: () => ({}),
    },
    {
      name: 'score_penalties',
      label: 'Penalità punteggio (score-based)',
      optional: true,
      collapsible: true,
      hint: {
        kind: 'array',
        itemLabel: (_, v) => v?.village || 'penalità',
        defaultItem: () => ({ village: '', description: '', points: 0 }),
        item: scorePenaltyHint,
      },
      defaultValue: () => [],
    },

    // round-robin only
    {
      name: 'rounds',
      label: 'Round (round-robin)',
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
    },

    // both variants may use divisions (different shape)
    {
      name: 'divisions',
      label: 'Divisioni',
      optional: true,
      collapsible: true,
      hint: {
        kind: 'nullable',
        inner: {
          kind: 'array',
          // Heuristic: if item has `scores` (dict) it's score-based, else round-robin.
          // We render with the shared schema; both variants share the same top-level fields.
          itemLabel: (i, v) => v?.name || `Divisione ${i + 1}`,
          defaultItem: () => ({
            name: '',
            status: STATUS_OPTIONS[0],
            scores: {},
            score_penalties: [],
            applied_bonuses: [],
            applied_penalties: [],
          }),
          // We pick based on which fields exist — use a permissive union
          item: {
            kind: 'object',
            fields: [
              { name: 'name', label: 'Nome', hint: { kind: 'string' } },
              { name: 'status', label: 'Stato', hint: { kind: 'enum', options: STATUS_OPTIONS } },
              {
                name: 'scores', label: 'Punteggi',
                hint: {
                  kind: 'dict',
                  keyHint: 'village',
                  value: { kind: 'numberOrString' },
                  defaultValue: () => 0,
                },
              },
              {
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
              },
              {
                name: 'score_penalties', label: 'Penalità punteggio', optional: true, collapsible: true,
                hint: {
                  kind: 'array',
                  itemLabel: (_, v) => v?.village || 'penalità',
                  defaultItem: () => ({ village: '', description: '', points: 0 }),
                  item: scorePenaltyHint,
                },
                defaultValue: () => [],
              },
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
            ],
          },
        },
      },
      defaultValue: () => [],
    },

    {
      name: 'applied_bonuses',
      label: 'Bonus di gioco',
      collapsible: true,
      hint: {
        kind: 'array',
        itemLabel: (_, v) => v?.village ? `${v.village} (+${v.points})` : 'bonus',
        defaultItem: () => ({ village: '', description: '', points: 0 }),
        item: gameBonusHint,
      },
    },
    {
      name: 'applied_penalties',
      label: 'Penalità di gioco',
      collapsible: true,
      hint: {
        kind: 'array',
        itemLabel: (_, v) => v?.village ? `${v.village} (${v.points})` : 'penalità',
        defaultItem: () => ({ village: '', description: '', points: 0 }),
        item: gamePenaltyHint,
      },
    },
  ],
};

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
