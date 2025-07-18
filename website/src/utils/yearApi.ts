// Year-aware API utility functions
import { 
  getPalioData, 
  getLeaderboardData, 
  getPalioGamesStatus,
  getAvailableYears,
  getPalioDataByYear,
  getLeaderboardDataByYear,
  getPalioGamesStatusByYear
} from '../generated/sdk.gen';

/**
 * Get palio data for current year or specific year
 */
export const getPalioDataForYear = (year?: number) => {
  if (year) {
    return getPalioDataByYear({ path: { year } });
  }
  return getPalioData();
};

/**
 * Get leaderboard data for current year or specific year
 */
export const getLeaderboardDataForYear = (year?: number) => {
  if (year) {
    return getLeaderboardDataByYear({ path: { year } });
  }
  return getLeaderboardData();
};

/**
 * Get games status data for current year or specific year
 */
export const getPalioGamesStatusForYear = (year?: number) => {
  if (year) {
    return getPalioGamesStatusByYear({ path: { year } });
  }
  return getPalioGamesStatus();
};

/**
 * Get all available years
 */
export const getAvailableYearsData = () => {
  return getAvailableYears();
};

/**
 * Get current year
 */
export const getCurrentYear = (): number => {
  return new Date().getFullYear();
};