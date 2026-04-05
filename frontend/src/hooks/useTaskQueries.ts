import { useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';
import type { TaskListItem, TaskDetails } from '../types';

interface TasksListResponse {
  items: TaskListItem[];
}

export function useTasksList() {
  return useQuery<TasksListResponse>({
    queryKey: ['tasks', 'list'],
    queryFn: async () => {
      const response = await api.get<{ items: TaskListItem[] }>(API_ENDPOINTS.TASKS);
      const taskList = response.data.items;
      if (!Array.isArray(taskList)) {
        return { items: [] };
      }
      taskList.sort((a, b) => {
        const dateA = new Date(a.created_at || 0).getTime();
        const dateB = new Date(b.created_at || 0).getTime();
        return dateB - dateA;
      });
      return { items: taskList };
    },
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
}

export function useTaskDetails(taskId: string | undefined) {
  return useQuery<TaskDetails>({
    queryKey: ['tasks', 'details', taskId],
    queryFn: async () => {
      const response = await api.get<TaskDetails>(API_ENDPOINTS.TASK_DETAILS(taskId!), {
        params: { limit: 50, offset: 0 },
      });
      const data = response.data;
      return {
        task_id: data.task_id,
        status: data.status,
        total_pairs: data.total_pairs,
        files: data.files,
        results: data.results,
        progress: data.progress || {
          completed: 0,
          total: 0,
          percentage: 0,
          display: '0%',
        },
        overall_stats: data.overall_stats,
      };
    },
    enabled: !!taskId,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
}
