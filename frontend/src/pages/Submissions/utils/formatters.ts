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

export function getStatusColor(status: string): 'green' | 'yellow' | 'gray' | 'red' {
  switch (status) {
    case 'completed':
      return 'green';
    case 'processing':
      return 'yellow';
    case 'queued':
      return 'gray';
    case 'failed':
      return 'red';
    default:
      return 'gray';
  }
}

const ALL_STATUSES = ['queued', 'processing', 'completed', 'failed'];

export { ALL_STATUSES };
