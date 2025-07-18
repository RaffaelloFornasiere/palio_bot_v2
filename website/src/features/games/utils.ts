export function getStatusColor(status: string) {
   switch (status) {
      case 'completed':
         return 'success';
      case 'in-progress':
         return 'warning';
      case 'not-started':
         return 'default';
      default:
         return 'default';
   }
}

export function getStatusText(status: string) {
   switch (status) {
      case 'completed':
         return 'Completato';
      case 'in-progress':
         return 'In corso';
      case 'not-started':
         return 'Non iniziato';
      default:
         return 'Sconosciuto';
   }
}

export function formatDate(dateString: string): string {
   try {
      const date = new Date(dateString);
      return date.toLocaleDateString('it-IT', {
         year: 'numeric',
         month: 'short',
         day: 'numeric',
         hour: '2-digit',
         minute: '2-digit'
      });
   } catch {
      return 'Data non disponibile';
   }
}

// Utility function to get division leaderboard results sorted by position
export function getDivisionLeaderboardSorted(leaderboard: { [key: string]: number }): [string, number][] {
   return Object.entries(leaderboard).sort(([,a], [,b]) => a - b);
}

// Utility function to get overall leaderboard results sorted by position
export function getOverallLeaderboardSorted(leaderboard: { [key: string]: { points: number, position: number } }): [string, { points: number, position: number }][] {
   return Object.entries(leaderboard).sort(([,a], [,b]) => a.position - b.position);
}

// Utility function to get the winner from division leaderboard
export function getDivisionWinner(leaderboard: { [key: string]: number }): string {
   const sorted = getDivisionLeaderboardSorted(leaderboard);
   return sorted.length > 0 ? sorted[0][0] : '';
}

// Utility function to get the winner from overall leaderboard
export function getOverallWinner(leaderboard: { [key: string]: { points: number, position: number } }): string {
   const winner = Object.entries(leaderboard).find(([, entry]) => entry.position === 1);
   return winner ? winner[0] : '';
}