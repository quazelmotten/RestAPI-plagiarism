import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';
import type { Subject, SubjectWithAssignments, Assignment } from '../types';

interface SubjectsResponse {
  items: Subject[];
  total: number;
  limit: number;
  offset: number;
}

export function useSubjects() {
  return useQuery<Subject[]>({
    queryKey: ['subjects'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.SUBJECTS);
      return res.data;
    },
  });
}

export function useSubjectsWithAssignments() {
  return useQuery<SubjectWithAssignments[]>({
    queryKey: ['subjects', 'with-assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.SUBJECTS);
      return res.data;
    },
  });
}

export function useUncategorizedAssignments() {
  return useQuery<Assignment[]>({
    queryKey: ['assignments', 'uncategorized'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.UNCATEGORIZED_ASSIGNMENTS);
      return res.data;
    },
  });
}

export function useCreateSubject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name: string; description: string | null }) => {
      const res = await api.post(API_ENDPOINTS.SUBJECTS, payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] });
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
    },
  });
}

export function useUpdateSubject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: { name?: string; description?: string | null } }) => {
      const res = await api.patch(`${API_ENDPOINTS.SUBJECTS}/${id}`, payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] });
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
    },
  });
}

export function useDeleteSubject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`${API_ENDPOINTS.SUBJECTS}/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] });
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
    },
  });
}
