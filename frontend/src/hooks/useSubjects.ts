import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';
import type { Subject, SubjectWithAssignments, Assignment } from '../types';
import { restoreSubject, restoreAssignment } from '../services/api';

interface SubjectMember {
  user_id: string;
  email: string;
  granted_at: string;
  granted_by: string | null;
}

interface SubjectMembersResponse {
  members: SubjectMember[];
}

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
      return res.data.subjects;
    },
  });
}

export function useSubjectsWithAssignments() {
  return useQuery<SubjectWithAssignments[]>({
    queryKey: ['subjects', 'with-assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.SUBJECTS);
      return res.data.subjects;
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
      queryClient.invalidateQueries({ queryKey: ['subjects', 'with-uncategorized'] });
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
      queryClient.invalidateQueries({ queryKey: ['subjects', 'with-uncategorized'] });
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
      queryClient.invalidateQueries({ queryKey: ['subjects', 'with-uncategorized'] });
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
    },
  });
}

export function useRestoreSubject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await restoreSubject(id);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] });
      queryClient.invalidateQueries({ queryKey: ['subjects', 'with-uncategorized'] });
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
    },
  });
}

export function useRestoreAssignment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await restoreAssignment(id);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['subjects'] });
    },
  });
}

export function useSubjectMembers(subjectId: string) {
  return useQuery<SubjectMember[]>({
    queryKey: ['subject-members', subjectId],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.SUBJECT_MEMBERS(subjectId));
      return res.data.members;
    },
    enabled: !!subjectId,
  });
}

export function useGrantSubjectAccess() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ subjectId, userEmail }: { subjectId: string; userEmail: string }) => {
      const res = await api.post(API_ENDPOINTS.SUBJECT_GRANT(subjectId), { user_email: userEmail });
      return res.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['subject-members', variables.subjectId] });
    },
  });
}

export function useRevokeSubjectAccess() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ subjectId, userId }: { subjectId: string; userId: string }) => {
      await api.delete(API_ENDPOINTS.SUBJECT_REVOKE(subjectId, userId));
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['subject-members', variables.subjectId] });
    },
  });
}