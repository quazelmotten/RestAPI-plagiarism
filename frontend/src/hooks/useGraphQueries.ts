import { useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';
import type { TaskListItem, TaskDetails } from '../types';

interface TasksListResponse {
  items: TaskListItem[];
}

export function useGraphTasks() {
  return useQuery<TasksListResponse>({
    queryKey: ['graph', 'tasks'],
    queryFn: async () => {
      const response = await api.get<{ items: TaskListItem[] }>(API_ENDPOINTS.TASKS);
      if (!Array.isArray(response.data.items)) {
        return { items: [] };
      }
      return response.data;
    },
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
}

export function useGraphTaskDetails(taskId: string | undefined, limit = 500) {
  return useQuery<TaskDetails>({
    queryKey: ['graph', 'taskDetails', taskId],
    queryFn: async () => {
      const response = await api.get<TaskDetails>(API_ENDPOINTS.TASK_DETAILS(taskId!), {
        params: { limit },
      });
      return response.data;
    },
    enabled: !!taskId,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
}
