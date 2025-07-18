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