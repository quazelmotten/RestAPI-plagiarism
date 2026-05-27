import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';
import type { UploadListItem, UploadDetails, UploadFile, ReviewPair } from '../types';

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

interface UploadsListParams {
  limit?: number;
  offset?: number;
  assignment_id?: string;
  status?: string;
}

interface ReviewQueueParams {
  limit?: number;
  offset?: number;
  upload_id?: string;
  assignment_id?: string;
  status?: string;
  min_similarity?: number;
}

// --- Uploads ---

export function useUploads(params?: UploadsListParams) {
  return useQuery<PaginatedResponse<UploadListItem>>({
    queryKey: ['uploads', params],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<UploadListItem>>(API_ENDPOINTS.UPLOADS, {
        params: {
          limit: params?.limit ?? 50,
          offset: params?.offset ?? 0,
          ...(params?.assignment_id && { assignment_id: params.assignment_id }),
          ...(params?.status && { status: params.status }),
        },
      });
      return response.data;
    },
    staleTime: 10_000,
    gcTime: 5 * 60_000,
    refetchInterval: 5000,
  });
}

export function useUploadDetails(taskId: string | undefined) {
  const ACTIVE_STATUSES = ['pending', 'queued', 'indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results'];

  return useQuery<UploadDetails>({
    queryKey: ['uploads', 'details', taskId],
    queryFn: async () => {
      const response = await api.get<UploadDetails>(API_ENDPOINTS.UPLOAD_DETAILS(taskId!));
      return response.data;
    },
    enabled: !!taskId,
    staleTime: 10_000,
    gcTime: 5 * 60_000,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_STATUSES.includes(status) ? 3000 : false;
    },
  });
}

export function useUpdateUpload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ taskId, name, language, assignment_id }: { taskId: string; name?: string; language?: string; assignment_id?: string }) => {
      const response = await api.patch(API_ENDPOINTS.UPDATE_UPLOAD(taskId), { name, language, assignment_id });
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      queryClient.invalidateQueries({ queryKey: ['uploads', 'details', variables.taskId] });
    },
  });
}

export function useDeleteUpload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (taskId: string) => {
      const response = await api.delete(API_ENDPOINTS.DELETE_UPLOAD(taskId));
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    },
  });
}

export function useReanalyzeUpload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ taskId, language }: { taskId: string; language?: string }) => {
      const response = await api.post(API_ENDPOINTS.REANALYZE_UPLOAD(taskId), { language });
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      queryClient.invalidateQueries({ queryKey: ['uploads', 'details', variables.taskId] });
    },
  });
}

export function useUnassignUpload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (taskId: string) => {
      const response = await api.patch(API_ENDPOINTS.UPDATE_UPLOAD(taskId), { assignment_id: '' });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    },
  });
}

// --- Upload Files ---

export function useUploadFiles(taskId: string | undefined) {
  return useQuery<UploadFile[]>({
    queryKey: ['uploads', 'files', taskId],
    queryFn: async () => {
      const response = await api.get<UploadFile[]>(API_ENDPOINTS.UPLOAD_FILES(taskId!));
      return response.data;
    },
    enabled: !!taskId,
    staleTime: 10_000,
    gcTime: 5 * 60_000,
  });
}

export function useDeleteUploadFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ taskId, fileId }: { taskId: string; fileId: string }) => {
      const response = await api.delete(API_ENDPOINTS.DELETE_UPLOAD_FILE(taskId, fileId));
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uploads', 'files', variables.taskId] });
      queryClient.invalidateQueries({ queryKey: ['uploads', 'details', variables.taskId] });
    },
  });
}

export function useUpdateUploadFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ taskId, fileId, filename, language }: { taskId: string; fileId: string; filename?: string; language?: string }) => {
      const response = await api.patch(API_ENDPOINTS.UPDATE_UPLOAD_FILE(taskId, fileId), { filename, language });
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['uploads', 'files', variables.taskId] });
      queryClient.invalidateQueries({ queryKey: ['uploads', 'details', variables.taskId] });
    },
  });
}

// --- Review Queue ---

export function useReviewQueue(params?: ReviewQueueParams) {
  return useQuery<PaginatedResponse<ReviewPair>>({
    queryKey: ['review-queue', params],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<ReviewPair>>(API_ENDPOINTS.GLOBAL_REVIEW_QUEUE, {
        params: {
          limit: params?.limit ?? 50,
          offset: params?.offset ?? 0,
          ...(params?.upload_id && { upload_id: params.upload_id }),
          ...(params?.assignment_id && { assignment_id: params.assignment_id }),
          ...(params?.status && { status: params.status }),
          ...(params?.min_similarity !== undefined && { min_similarity: params.min_similarity }),
        },
      });
      return response.data;
    },
    staleTime: 10_000,
    gcTime: 5 * 60_000,
  });
}


