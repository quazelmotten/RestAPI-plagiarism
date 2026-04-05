import { getStatusColorScheme as _getStatusColorScheme } from '../../../utils/statusColors';

export function formatDate(dateString: string): string {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${day}.${month}.${year} ${hours}:${minutes}`;
  } catch {
    return dateString;
  }
}

export function formatSimilarity(similarity: number | null): string {
  if (similarity === null || similarity === undefined) return '-';
  return `${(similarity * 100).toFixed(1)}%`;
}

export function getStatusColor(status: string): 'green' | 'yellow' | 'blue' | 'orange' | 'purple' | 'gray' | 'red' {
  return _getStatusColorScheme(status) as 'green' | 'yellow' | 'blue' | 'orange' | 'purple' | 'gray' | 'red';
}

const ALL_STATUSES = ['queued', 'indexing', 'finding_pairs', 'processing', 'completed', 'failed'];

export { ALL_STATUSES };
