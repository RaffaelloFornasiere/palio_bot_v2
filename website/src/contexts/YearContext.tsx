import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

interface YearContextType {
  selectedYear: number | undefined;
  setSelectedYear: (year: number | undefined) => void;
}

const YearContext = createContext<YearContextType | undefined>(undefined);

export const useYear = () => {
  const context = useContext(YearContext);
  if (!context) {
    throw new Error('useYear must be used within a YearProvider');
  }
  return context;
};

interface YearProviderProps {
  children: ReactNode;
}

export const YearProvider: React.FC<YearProviderProps> = ({ children }) => {
  const [selectedYear, setSelectedYear] = useState<number | undefined>(undefined);
  const location = useLocation();

  // Initialize from URL on mount and route changes
  useEffect(() => {
    const pathSegments = location.pathname.split('/').filter(Boolean);
    
    // Check if first segment is a valid year (year-first URL pattern)
    if (pathSegments.length > 0) {
      const firstSegment = pathSegments[0];
      if (firstSegment && !isNaN(Number(firstSegment))) {
        const year = Number(firstSegment);
        // Only consider years that make sense for this context (e.g., 2020-2030)
        if (year >= 2020 && year <= 2030) {
          setSelectedYear(year);
          return;
        }
      }
    }
    
    // If no year found in URL, reset to current year (undefined)
    // This ensures clean state when navigating to non-year URLs
    setSelectedYear(undefined);
  }, [location.pathname]);

  return (
    <YearContext.Provider value={{ selectedYear, setSelectedYear }}>
      {children}
    </YearContext.Provider>
  );
};