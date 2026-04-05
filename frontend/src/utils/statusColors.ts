export const getSimilarityColor = (similarity: number): string => {
  if (similarity >= 0.8) return 'red';
  if (similarity >= 0.5) return 'orange';
  if (similarity >= 0.3) return 'yellow';
  return 'green';
};

export const getStatusColorScheme = (status: string): string => {
  switch (status) {
    case 'completed':
      return 'green';
    case 'failed':
      return 'red';
    case 'storing_results':
      return 'orange';
    case 'indexing':
      return 'blue';
    case 'finding_intra_pairs':
    case 'finding_cross_pairs':
      return 'purple';
    case 'processing':
      return 'orange';
    case 'finding_pairs':
      return 'purple';
    case 'queued':
      return 'gray';
    case 'pending':
      return 'yellow';
    default:
      return 'gray';
  }
};
