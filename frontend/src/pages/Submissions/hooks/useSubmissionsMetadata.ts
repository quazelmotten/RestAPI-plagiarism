import { useQuery } from '@tanstack/react-query';
import { fetchSubmissionsMetadata } from '../utils/api';

export interface SubmissionsMetadata {
  taskIds: string[];
  languages: string[];
  assignments: Array<{ id: string; name: string }>;
  subjects: Array<{ id: string; name: string }>;
}

export function useSubmissionsMetadata() {
  return useQuery<SubmissionsMetadata>({
    queryKey: ['submissions', 'metadata'],
    queryFn: fetchSubmissionsMetadata,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
  });
}
