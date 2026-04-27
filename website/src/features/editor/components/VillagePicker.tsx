import React from 'react';
import { TextField, MenuItem } from '@mui/material';

interface Props {
  value: string;
  villages: string[];
  onChange: (v: string) => void;
  label?: string;
  size?: 'small' | 'medium';
  fullWidth?: boolean;
}

const VillagePicker: React.FC<Props> = ({ value, villages, onChange, label, size = 'small', fullWidth }) => {
  const options = villages.includes(value) || !value ? villages : [value, ...villages];
  return (
    <TextField
      select
      size={size}
      fullWidth={fullWidth}
      label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      sx={{ minWidth: 120 }}
    >
      {options.map((v) => (
        <MenuItem key={v} value={v}>{v}</MenuItem>
      ))}
    </TextField>
  );
};

export default VillagePicker;
