import React, { useState } from 'react';
import {
  Box, TextField, Switch, FormControlLabel, IconButton, Button,
  Accordion, AccordionSummary, AccordionDetails, Typography, Stack, MenuItem, Chip,
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
    }
  | {
      kind: 'dict';
      value: Hint;
      keyHint?: 'village' | 'string';
      defaultValue: () => any;
      // presented keys (e.g., all villages) so we can offer add-missing
      suggestedKeys?: string[];
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
        <TextField
          size="small"
          type="number"
          label={label}
          value={value ?? 0}
          inputProps={{ inputMode: hint.kind === 'integer' ? 'numeric' : 'decimal', step: hint.kind === 'integer' ? 1 : 'any' }}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === '' || raw === '-') { onChange(raw === '' ? 0 : raw); return; }
            const n = hint.kind === 'integer' ? parseInt(raw, 10) : parseFloat(raw);
            onChange(Number.isNaN(n) ? value : n);
          }}
          fullWidth
        />
      );
    case 'numberOrString':
      return (
        <TextField
          size="small"
          label={label}
          value={value ?? ''}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === '') { onChange(0); return; }
            const n = Number(raw);
            onChange(Number.isFinite(n) && raw.trim() !== '' ? n : raw);
          }}
          fullWidth
        />
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
    case 'nullable':
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
  const entries = Object.entries(value || {});
  const [newKey, setNewKey] = useState('');
  const existing = new Set(entries.map(([k]) => k));
  const suggestions = (hint.keyHint === 'village' ? ctx.villages : hint.suggestedKeys ?? [])
    .filter((k) => !existing.has(k));

  const addKey = (key: string) => {
    if (!key || existing.has(key)) return;
    onChange({ ...(value || {}), [key]: hint.defaultValue() });
    setNewKey('');
  };

  return (
    <Box>
      {label && <Typography variant="subtitle2" sx={{ mb: 1 }}>{label} ({entries.length})</Typography>}
      <Stack spacing={1}>
        {entries.map(([k, v]) => (
          <Box key={k} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Chip label={k} size="small" color={hint.keyHint === 'village' ? 'primary' : 'default'} />
              <Box sx={{ flex: 1 }} />
              <IconButton
                size="small"
                onClick={() => {
                  const next = { ...(value || {}) }; delete next[k]; onChange(next);
                }}
                aria-label="rimuovi"
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Box>
            <FieldNode
              value={v}
              onChange={(nv) => onChange({ ...(value || {}), [k]: nv })}
              hint={hint.value}
              ctx={ctx}
            />
          </Box>
        ))}
      </Stack>
      <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {hint.keyHint === 'village' ? (
          <>
            <TextField
              select
              size="small"
              label="Nuova contrada"
              value=""
              onChange={(e) => addKey(e.target.value)}
              sx={{ minWidth: 180 }}
              disabled={suggestions.length === 0}
            >
              {suggestions.map((v) => <MenuItem key={v} value={v}>{v}</MenuItem>)}
            </TextField>
          </>
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
