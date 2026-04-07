import { useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';

interface Task {
  task_id: string;
  status: 'pending' | 'indexing' | 'finding_pairs' | 'processing' | 'completed' | 'failed';
  total_pairs: number;
  files: { id: string; filename: string }[];
  results: Array<{
    ast_similarity: number;
  }>;
  created_at?: string;
  updated_at?: string;
  progress?: {
    completed: number;
    total: number;
  };
  files_count?: number;
  high_similarity_count?: number;
  assignment_id?: string | null;
  assignment_name?: string | null;
  subject_id?: string | null;
  subject_name?: string | null;
}

interface TasksResponse {
  items: Task[];
}

export function useTasks() {
  return useQuery<TasksResponse>({
    queryKey: ['overview', 'tasks'],
    queryFn: async () => {
      const response = await api.get(API_ENDPOINTS.TASKS);
      if (!Array.isArray(response.data.items)) {
        return { items: [] };
      }
      return response.data;
    },
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
}

export type { Task };
