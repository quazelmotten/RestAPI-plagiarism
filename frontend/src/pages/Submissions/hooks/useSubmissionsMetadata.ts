import { useQuery } from '@tanstack/react-query';
import { fetchSubmissionsMetadata } from '../utils/api';

export function useSubmissionsMetadata() {
  return useQuery({
    queryKey: ['submissions', 'metadata'],
    queryFn: fetchSubmissionsMetadata,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
  });
}
