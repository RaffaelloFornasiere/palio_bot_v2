import React, { useState } from 'react';
import {
  Box, TextField, Switch, FormControlLabel, IconButton, Button,
  Accordion, AccordionSummary, AccordionDetails, Typography, Stack, MenuItem, Chip,
  ToggleButton, ToggleButtonGroup,
  Table, TableHead, TableBody, TableRow, TableCell,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import VillagePicker from './VillagePicker';

export type Hint =
  | { kind: 'string'; multiline?: boolean }
  | { kind: 'number' }
  | { kind: 'integer' }
  | { kind: 'boolean' }
  | { kind: 'enum'; options: string[] }
  | { kind: 'village' }
  | { kind: 'nullable'; inner: Hint }
  | { kind: 'numberOrString' } // permissive: palio points sometimes stored as string
  | {
      kind: 'array';
      item: Hint;
      itemLabel?: (i: number, val: any) => string;
      defaultItem: () => any;
      // 'table' renders one row per array item with one column per field
      // of the item object. Requires item.kind === 'object'; falls back to
      // the stacked layout otherwise.
      presentation?: 'table';
    }
  | {
      kind: 'dict';
      value: Hint;
      keyHint?: 'village' | 'string';
      defaultValue: () => any;
      // presented keys (e.g., all villages) so we can offer add-missing
      suggestedKeys?: string[];
      // 'table' renders one row per entry. Object-valued dicts get one
      // column per field; scalar-valued dicts get a single value column.
      presentation?: 'table';
      // Header for the single value column when `presentation: 'table'`
      // and `value` is scalar. Defaults to 'Valore'.
      valueColumnLabel?: string;
      // Optional: derive the entry's user-facing label from its value
      // instead of showing the raw key. Used when the key is an internal
      // identifier the user shouldn't see (e.g. game_id).
      valueLabel?: (value: any) => string;
    }
  | {
      kind: 'object';
      fields: Array<{
        name: string;
        label?: string;
        hint: Hint;
        collapsible?: boolean;
        optional?: boolean;
        defaultValue?: () => any;
      }>;
    };

export interface FormContext {
  villages: string[];
}

interface NodeProps {
  value: any;
  onChange: (v: any) => void;
  hint: Hint;
  ctx: FormContext;
  label?: string;
}

// Controlled numeric input that survives transitional strings ('', '-', '1.', '0.').
// Holds a string draft while the user is typing; only commits a parsed number
// to onChange when the draft is parseable. On blur the draft is reconciled
// with the parent value.
const NumberLeaf: React.FC<{
  value: number | null | undefined;
  onChange: (v: number) => void;
  label?: string;
  isInteger: boolean;
}> = ({ value, onChange, label, isInteger }) => {
  const [draft, setDraft] = useState<string | null>(null);
  const display = draft !== null ? draft : (value == null ? '' : String(value));
  const parse = (s: string) => (isInteger ? parseInt(s, 10) : parseFloat(s));
  return (
    <TextField
      size="small"
      type="text"
      label={label}
      value={display}
      inputProps={{ inputMode: isInteger ? 'numeric' : 'decimal' }}
      onChange={(e) => {
        const raw = e.target.value;
        setDraft(raw);
        if (raw === '' || raw === '-' || raw === '.' || raw === '-.') return;
        const n = parse(raw);
        if (Number.isFinite(n)) onChange(n);
      }}
      onBlur={() => {
        if (draft === null) return;
        const n = parse(draft);
        onChange(Number.isFinite(n) ? n : 0);
        setDraft(null);
      }}
      fullWidth
    />
  );
};

// Like NumberLeaf, but commits a string when the draft isn't a finite number
// (used for fields that historically may have been stored as strings).
const NumberOrStringLeaf: React.FC<{
  value: any;
  onChange: (v: any) => void;
  label?: string;
}> = ({ value, onChange, label }) => {
  const [draft, setDraft] = useState<string | null>(null);
  const display = draft !== null ? draft : (value == null ? '' : String(value));
  return (
    <TextField
      size="small"
      type="text"
      label={label}
      value={display}
      inputProps={{ inputMode: 'decimal' }}
      onChange={(e) => {
        const raw = e.target.value;
        setDraft(raw);
        if (raw === '' || raw === '-' || raw === '.' || raw === '-.') return;
        const n = Number(raw);
        if (Number.isFinite(n)) onChange(n);
      }}
      onBlur={() => {
        if (draft === null) return;
        if (draft.trim() === '') { onChange(0); setDraft(null); return; }
        const n = Number(draft);
        onChange(Number.isFinite(n) ? n : draft);
        setDraft(null);
      }}
      fullWidth
    />
  );
};

const FieldNode: React.FC<NodeProps> = ({ value, onChange, hint, ctx, label }) => {
  switch (hint.kind) {
    case 'string':
      return (
        <TextField
          size="small"
          label={label}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          multiline={hint.multiline}
          minRows={hint.multiline ? 2 : undefined}
          fullWidth
        />
      );
    case 'number':
    case 'integer':
      return (
        <NumberLeaf
          value={value}
          onChange={onChange}
          label={label}
          isInteger={hint.kind === 'integer'}
        />
      );
    case 'numberOrString':
      return (
        <NumberOrStringLeaf value={value} onChange={onChange} label={label} />
      );
    case 'boolean':
      return (
        <FormControlLabel
          control={<Switch checked={!!value} onChange={(e) => onChange(e.target.checked)} />}
          label={label ?? ''}
        />
      );
    case 'enum':
      return (
        <TextField
          select
          size="small"
          label={label}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          fullWidth
        >
          {hint.options.map((o) => <MenuItem key={o} value={o}>{o}</MenuItem>)}
        </TextField>
      );
    case 'village':
      return (
        <VillagePicker
          value={value ?? ''}
          villages={ctx.villages}
          onChange={onChange}
          label={label}
          fullWidth
        />
      );
    case 'nullable': {
      if (hint.inner.kind === 'boolean') {
        const current = value == null ? 'null' : value ? 'true' : 'false';
        return (
          <Box>
            {label && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                {label}
              </Typography>
            )}
            <ToggleButtonGroup
              exclusive
              size="small"
              value={current}
              onChange={(_, nv) => {
                if (nv == null) return;
                onChange(nv === 'null' ? null : nv === 'true');
              }}
            >
              <ToggleButton value="null">Vuoto</ToggleButton>
              <ToggleButton value="true">Sì</ToggleButton>
              <ToggleButton value="false">No</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        );
      }
      return (
        <Box>
          <FormControlLabel
            control={
              <Switch
                checked={value != null}
                onChange={(e) => onChange(e.target.checked ? defaultFor(hint.inner) : null)}
              />
            }
            label={`${label ?? 'valore'}: ${value == null ? 'vuoto' : 'impostato'}`}
          />
          {value != null && (
            <FieldNode value={value} onChange={onChange} hint={hint.inner} ctx={ctx} />
          )}
        </Box>
      );
    }
    case 'array':
      return <ArrayNode value={value ?? []} onChange={onChange} hint={hint} ctx={ctx} label={label} />;
    case 'dict':
      return <DictNode value={value ?? {}} onChange={onChange} hint={hint} ctx={ctx} label={label} />;
    case 'object':
      return <ObjectNode value={value ?? {}} onChange={onChange} hint={hint} ctx={ctx} label={label} />;
  }
};

const ArrayNode: React.FC<NodeProps & { hint: Extract<Hint, { kind: 'array' }> }> = ({
  value, onChange, hint, ctx, label,
}) => {
  const items: any[] = Array.isArray(value) ? value : [];

  if (hint.presentation === 'table' && hint.item.kind === 'object') {
    const fields = hint.item.fields;
    return (
      <Box>
        {label && <Typography variant="subtitle2" sx={{ mb: 1 }}>{label} ({items.length})</Typography>}
        <Table size="small">
          <TableHead>
            <TableRow>
              {fields.map((f) => (
                <TableCell key={f.name} sx={{ px: 1 }}>{f.label ?? f.name}</TableCell>
              ))}
              <TableCell sx={{ width: 40, pl: 1, pr: 0 }} />
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item, i) => {
              const row = (item ?? {}) as Record<string, any>;
              return (
                <TableRow key={i}>
                  {fields.map((f) => (
                    <TableCell
                      key={f.name}
                      sx={{ px: 1, '& .MuiOutlinedInput-input': { px: 1 } }}
                    >
                      <FieldNode
                        value={row[f.name]}
                        onChange={(nv) => {
                          const next = [...items];
                          next[i] = { ...row, [f.name]: nv };
                          onChange(next);
                        }}
                        hint={f.hint}
                        ctx={ctx}
                      />
                    </TableCell>
                  ))}
                  <TableCell sx={{ pl: 1, pr: 0 }}>
                    <IconButton
                      size="small"
                      onClick={() => {
                        const next = [...items]; next.splice(i, 1); onChange(next);
                      }}
                      aria-label="rimuovi"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <Button
          size="small"
          startIcon={<AddIcon />}
          onClick={() => onChange([...items, hint.defaultItem()])}
          sx={{ mt: 1 }}
        >
          Aggiungi
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {label && <Typography variant="subtitle2" sx={{ mb: 1 }}>{label} ({items.length})</Typography>}
      <Stack spacing={1}>
        {items.map((item, i) => (
          <Box key={i} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1, position: 'relative' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, gap: 1 }}>
              <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
                {hint.itemLabel ? hint.itemLabel(i, item) : `#${i + 1}`}
              </Typography>
              <IconButton
                size="small"
                onClick={() => {
                  const next = [...items]; next.splice(i, 1); onChange(next);
                }}
                aria-label="rimuovi"
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Box>
            <FieldNode
              value={item}
              onChange={(nv) => {
                const next = [...items]; next[i] = nv; onChange(next);
              }}
              hint={hint.item}
              ctx={ctx}
            />
          </Box>
        ))}
      </Stack>
      <Button
        size="small"
        startIcon={<AddIcon />}
        onClick={() => onChange([...items, hint.defaultItem()])}
        sx={{ mt: 1 }}
      >
        Aggiungi
      </Button>
    </Box>
  );
};

const DictNode: React.FC<NodeProps & { hint: Extract<Hint, { kind: 'dict' }> }> = ({
  value, onChange, hint, ctx, label,
}) => {
  const data: Record<string, any> = value || {};
  const dataKeys = Object.keys(data);
  const [newKey, setNewKey] = useState('');

  // Village-keyed dicts always show one row per known village (in master
  // order), so users don't have to add villages one by one. Extra keys
  // present in the data but not in the master list are appended.
  const isVillageDict = hint.keyHint === 'village' && ctx.villages.length > 0;
  const villageSet = new Set(ctx.villages);
  const orderedKeys = isVillageDict
    ? [...ctx.villages, ...dataKeys.filter((k) => !villageSet.has(k))]
    : dataKeys;
  const isMasterVillage = (k: string) => isVillageDict && villageSet.has(k);

  const existing = new Set(dataKeys);
  const suggestions = (hint.keyHint === 'village' ? ctx.villages : hint.suggestedKeys ?? [])
    .filter((k) => !existing.has(k));

  const addKey = (key: string) => {
    if (!key || existing.has(key)) return;
    onChange({ ...data, [key]: hint.defaultValue() });
    setNewKey('');
  };

  const removeKey = (k: string) => {
    const next = { ...data }; delete next[k]; onChange(next);
  };

  const valueFor = (k: string) =>
    k in data ? data[k] : hint.defaultValue();

  // For village dicts the picker is redundant — all villages are pre-shown.
  const adder = isVillageDict ? null : (
    <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
      {hint.keyHint === 'village' ? (
        <TextField
          select
          size="small"
          label="Nuovo borgo"
          value=""
          onChange={(e) => addKey(e.target.value)}
          sx={{ minWidth: 180 }}
          disabled={suggestions.length === 0}
        >
          {suggestions.map((v) => <MenuItem key={v} value={v}>{v}</MenuItem>)}
        </TextField>
      ) : (
        <>
          <TextField
            size="small"
            label="Nuova chiave"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addKey(newKey); } }}
          />
          <Button size="small" startIcon={<AddIcon />} onClick={() => addKey(newKey)} disabled={!newKey}>
            Aggiungi
          </Button>
        </>
      )}
    </Box>
  );

  const count = isVillageDict ? orderedKeys.length : dataKeys.length;

  if (hint.presentation === 'table') {
    const objectValue = hint.value.kind === 'object' ? hint.value : null;
    const fields = objectValue?.fields ?? null;
    const keyLabel = hint.keyHint === 'village' ? 'Borgo' : 'Chiave';
    return (
      <Box>
        {label && <Typography variant="subtitle2" sx={{ mb: 1 }}>{label} ({count})</Typography>}
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ pl: 0, pr: 1 }}>{keyLabel}</TableCell>
              {fields ? (
                fields.map((f) => (
                  <TableCell key={f.name} sx={{ px: 1 }}>{f.label ?? f.name}</TableCell>
                ))
              ) : (
                <TableCell sx={{ px: 1 }}>{hint.valueColumnLabel ?? 'Valore'}</TableCell>
              )}
              <TableCell sx={{ width: 40, pl: 1, pr: 0 }} />
            </TableRow>
          </TableHead>
          <TableBody>
            {orderedKeys.map((k) => {
              const raw = valueFor(k);
              return (
                <TableRow key={k}>
                  <TableCell sx={{ pl: 0, pr: 1 }}>
                    <Chip label={k} size="small" color={hint.keyHint === 'village' ? 'primary' : 'default'} />
                  </TableCell>
                  {fields ? (
                    fields.map((f) => {
                      const row = (raw ?? {}) as Record<string, any>;
                      return (
                        <TableCell
                          key={f.name}
                          sx={{
                            px: 1,
                            '& .MuiOutlinedInput-input': { px: 1 },
                          }}
                        >
                          <FieldNode
                            value={row[f.name]}
                            onChange={(nv) => onChange({ ...data, [k]: { ...row, [f.name]: nv } })}
                            hint={f.hint}
                            ctx={ctx}
                          />
                        </TableCell>
                      );
                    })
                  ) : (
                    <TableCell
                      sx={{
                        px: 1,
                        '& .MuiOutlinedInput-input': { px: 1 },
                      }}
                    >
                      <FieldNode
                        value={raw}
                        onChange={(nv) => onChange({ ...data, [k]: nv })}
                        hint={hint.value}
                        ctx={ctx}
                      />
                    </TableCell>
                  )}
                  <TableCell sx={{ pl: 1, pr: 0 }}>
                    {!isMasterVillage(k) && (
                      <IconButton size="small" onClick={() => removeKey(k)} aria-label="rimuovi">
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {adder}
      </Box>
    );
  }

  return (
    <Box>
      {label && <Typography variant="subtitle2" sx={{ mb: 1 }}>{label} ({count})</Typography>}
      <Stack spacing={1}>
        {orderedKeys.map((k) => {
          const v = valueFor(k);
          return (
            <Box key={k} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Chip
                  label={hint.valueLabel ? hint.valueLabel(v) : k}
                  size="small"
                  color={hint.keyHint === 'village' ? 'primary' : 'default'}
                />
                <Box sx={{ flex: 1 }} />
                {!isMasterVillage(k) && (
                  <IconButton
                    size="small"
                    onClick={() => removeKey(k)}
                    aria-label="rimuovi"
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
              <FieldNode
                value={v}
                onChange={(nv) => onChange({ ...data, [k]: nv })}
                hint={hint.value}
                ctx={ctx}
              />
            </Box>
          );
        })}
      </Stack>
      {adder}
    </Box>
  );
};

const ObjectNode: React.FC<NodeProps & { hint: Extract<Hint, { kind: 'object' }> }> = ({
  value, onChange, hint, ctx, label,
}) => {
  const obj: Record<string, any> = value ?? {};
  return (
    <Box>
      {label && <Typography variant="subtitle2" sx={{ mb: 1 }}>{label}</Typography>}
      <Stack spacing={2}>
        {hint.fields.map((f) => {
          const present = f.name in obj;
          if (f.optional && !present && f.collapsible) {
            return (
              <Button
                key={f.name}
                size="small"
                startIcon={<AddIcon />}
                onClick={() =>
                  onChange({ ...obj, [f.name]: f.defaultValue ? f.defaultValue() : defaultFor(f.hint) })
                }
              >
                Aggiungi {f.label ?? f.name}
              </Button>
            );
          }
          const child = (
            <FieldNode
              value={obj[f.name]}
              onChange={(nv) => onChange({ ...obj, [f.name]: nv })}
              hint={f.hint}
              ctx={ctx}
              label={f.label ?? f.name}
            />
          );
          if (f.collapsible) {
            return (
              <Accordion key={f.name} defaultExpanded={false} disableGutters>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">{f.label ?? f.name}</Typography>
                </AccordionSummary>
                <AccordionDetails>{child}</AccordionDetails>
              </Accordion>
            );
          }
          return <Box key={f.name}>{child}</Box>;
        })}
      </Stack>
    </Box>
  );
};

export function defaultFor(hint: Hint): any {
  switch (hint.kind) {
    case 'string': return '';
    case 'number': case 'integer': case 'numberOrString': return 0;
    case 'boolean': return false;
    case 'enum': return hint.options[0] ?? '';
    case 'village': return '';
    case 'nullable': return null;
    case 'array': return [];
    case 'dict': return {};
    case 'object': {
      const o: Record<string, any> = {};
      for (const f of hint.fields) {
        if (!f.optional) o[f.name] = f.defaultValue ? f.defaultValue() : defaultFor(f.hint);
      }
      return o;
    }
  }
}

interface FormProps {
  value: any;
  onChange: (v: any) => void;
  hint: Hint;
  villages: string[];
}

export const JsonForm: React.FC<FormProps> = ({ value, onChange, hint, villages }) => {
  return <FieldNode value={value} onChange={onChange} hint={hint} ctx={{ villages }} />;
};
