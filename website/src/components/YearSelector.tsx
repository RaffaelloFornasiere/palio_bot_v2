import React, { useState, useEffect } from 'react';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Box
} from '@mui/material';
import { getAvailableYearsData, getCurrentYear } from '../utils/yearApi';

interface YearSelectorProps {
  selectedYear?: number;
  onYearChange: (year?: number) => void;
  showCurrentYear?: boolean;
}

const YearSelector: React.FC<YearSelectorProps> = ({
  selectedYear,
  onYearChange,
  showCurrentYear = true
}) => {
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchYears = async () => {
      try {
        setLoading(true);
        const response = await getAvailableYearsData();
        
        if (response.error) {
          throw new Error('Failed to fetch available years');
        }
        
        setAvailableYears(response.data!.years);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchYears();
  }, []);

  const handleChange = (event: any) => {
    const value = event.target.value;
    if (value === 'current') {
      onYearChange(undefined);
    } else {
      onYearChange(Number(value));
    }
  };

  const getDisplayValue = () => {
    if (selectedYear) {
      return selectedYear.toString();
    }
    return showCurrentYear ? 'current' : '';
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', minWidth: 120 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ minWidth: 120 }}>
        Errore caricamento anni
      </Alert>
    );
  }

  return (
    <FormControl size="small" sx={{ minWidth: 120 }}>
      <InputLabel id="year-selector-label">Anno</InputLabel>
      <Select
        labelId="year-selector-label"
        value={getDisplayValue()}
        label="Anno"
        onChange={handleChange}
      >
        {showCurrentYear && (
          <MenuItem value="current">
            {getCurrentYear()} (Corrente)
          </MenuItem>
        )}
        {availableYears.map((year) => (
          <MenuItem key={year} value={year.toString()}>
            {year}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
};

export default YearSelector;