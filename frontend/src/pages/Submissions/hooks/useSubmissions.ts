import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchSubmissions } from '../utils/api';
import type { Filters } from '../types';
import { useDebounce } from './useDebounce';

interface UseSubmissionsProps {
  offset: number;
  limit: number;
  filters: Filters;
}

export function useSubmissions({ offset, limit, filters }: UseSubmissionsProps) {
  const debouncedFilters = useDebounce(filters, 500);

  return useQuery({
    queryKey: ['submissions', 'list', offset, limit, debouncedFilters],
    queryFn: () => fetchSubmissions(offset, limit, debouncedFilters),
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
}
