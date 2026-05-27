import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';
import type { FileInfo, FileContent, FileListItem, ApiError } from '../types';

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

interface FilesListResponse {
  items: FileInfo[];
}

interface AllFilesParams {
  limit?: number;
  offset?: number;
  filename?: string;
  language?: string;
  status?: string;
  assignment_id?: string;
  similarity_min?: number;
  similarity_max?: number;
  submitted_after?: string;
  submitted_before?: string;
}

export function useFilesList() {
  return useQuery<FilesListResponse>({
    queryKey: ['pairComparison', 'files'],
    queryFn: async () => {
      const response = await api.get<{ items: FileInfo[] }>(API_ENDPOINTS.FILES_LIST);
      return response.data;
    },
    staleTime: 60_000,
    gcTime: 10 * 60_000,
  });
}

export function useAllFiles(params?: AllFilesParams) {
  return useQuery<PaginatedResponse<FileListItem>>({
    queryKey: ['files', params],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<FileListItem>>(API_ENDPOINTS.FILES, {
        params: {
          limit: params?.limit ?? 100,
          offset: params?.offset ?? 0,
          ...(params?.filename && { filename: params.filename }),
          ...(params?.language && { language: params.language }),
          ...(params?.status && { status: params.status }),
          ...(params?.assignment_id && { assignment_id: params.assignment_id }),
          ...(params?.similarity_min !== undefined && { similarity_min: params.similarity_min }),
          ...(params?.similarity_max !== undefined && { similarity_max: params.similarity_max }),
          ...(params?.submitted_after && { submitted_after: params.submitted_after }),
          ...(params?.submitted_before && { submitted_before: params.submitted_before }),
        },
      });
      return response.data;
    },
    staleTime: 10_000,
    gcTime: 5 * 60_000,
  });
}

export function useDeleteFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (fileId: string) => {
      await api.delete(API_ENDPOINTS.DELETE_FILE(fileId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}

export function useFileContent(fileId: string | null) {
  return useQuery<FileContent>({
    queryKey: ['pairComparison', 'fileContent', fileId],
    queryFn: async () => {
      const response = await api.get<FileContent>(API_ENDPOINTS.FILE_CONTENT(fileId!));
      return response.data;
    },
    enabled: !!fileId,
    staleTime: 5 * 60_000,
    gcTime: 10 * 60_000,
  });
}

export function useFilePair(fileAId: string | null, fileBId: string | null) {
  return useQuery({
    queryKey: ['pairComparison', 'pair', fileAId, fileBId],
    queryFn: async () => {
      const response = await api.get(API_ENDPOINTS.FILE_PAIR, {
        params: { file_a: fileAId, file_b: fileBId },
      });
      return response.data;
    },
    enabled: !!fileAId && !!fileBId,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
}

export function useFilesByIds(ids: string[]) {
  return useQuery<FileInfo[]>({
    queryKey: ['pairComparison', 'filesByIds', ids],
    queryFn: async () => {
      const response = await api.get<FilesListResponse>(API_ENDPOINTS.FILES_LIST);
      return response.data.items.filter(f => ids.includes(f.id));
    },
    enabled: ids.length > 0,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
  });
}

interface FileEventItem {
  id: string;
  assignment_id: string | null;
  task_id: string | null;
  event_type: string;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

interface EventsParams {
  limit?: number;
  offset?: number;
  assignment_id?: string;
  task_id?: string;
  event_type?: string;
}

export function useFileEvents(params?: EventsParams) {
  return useQuery<PaginatedResponse<FileEventItem>>({
    queryKey: ['fileEvents', params],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<FileEventItem>>('/plagiarism/events', {
        params: {
          limit: params?.limit ?? 50,
          offset: params?.offset ?? 0,
          ...(params?.assignment_id && { assignment_id: params.assignment_id }),
          ...(params?.task_id && { task_id: params.task_id }),
          ...(params?.event_type && { event_type: params.event_type }),
        },
      });
      return response.data;
    },
    staleTime: 10_000,
    gcTime: 5 * 60_000,
  });
}

export function useFileIds(params?: Omit<AllFilesParams, 'limit' | 'offset'>) {
  return useQuery<string[]>({
    queryKey: ['fileIds', params],
    queryFn: async () => {
      const response = await api.get<string[]>('/plagiarism/files/ids', {
        params: {
          ...(params?.filename && { filename: params.filename }),
          ...(params?.language && { language: params.language }),
          ...(params?.status && { status: params.status }),
          ...(params?.assignment_id && { assignment_id: params.assignment_id }),
          ...(params?.similarity_min !== undefined && { similarity_min: params.similarity_min }),
          ...(params?.similarity_max !== undefined && { similarity_max: params.similarity_max }),
        },
      });
      return response.data;
    },
    enabled: false,
    staleTime: 0,
    gcTime: 0,
  });
}

interface TaskEventItem {
  id: string;
  event_type: string;
  assignment_id: string | null;
  assignment_name: string | null;
  task_id: string | null;
  task_name: string | null;
  user_id: string | null;
  user_email: string | null;
  metadata: Record<string, unknown> | null;
  files_count: number | null;
  created_at: string | null;
}

interface TaskEventsParams {
  limit?: number;
  offset?: number;
  event_type?: string;
  assignment_id?: string;
  user_id?: string;
  date_from?: string;
  date_to?: string;
}

export function useTaskEvents(params?: TaskEventsParams) {
  return useQuery<PaginatedResponse<TaskEventItem>>({
    queryKey: ['taskEvents', params],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<TaskEventItem>>(API_ENDPOINTS.TASK_EVENTS, {
        params: {
          limit: params?.limit ?? 50,
          offset: params?.offset ?? 0,
          ...(params?.event_type && { event_type: params.event_type }),
          ...(params?.assignment_id && { assignment_id: params.assignment_id }),
          ...(params?.user_id && { user_id: params.user_id }),
          ...(params?.date_from && { date_from: params.date_from }),
          ...(params?.date_to && { date_to: params.date_to }),
        },
      });
      return response.data;
    },
    staleTime: 10_000,
    gcTime: 5 * 60_000,
  });
}

export function useBulkMoveFiles() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ fileIds, targetTaskId }: { fileIds: string[]; targetTaskId: string }) => {
      const response = await api.post('/plagiarism/files/bulk/move', {
        file_ids: fileIds,
        target_task_id: targetTaskId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}

export function useBulkMoveByAssignment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ fileIds, targetAssignmentId }: { fileIds: string[]; targetAssignmentId: string }) => {
      const response = await api.post('/plagiarism/files/bulk/move-by-assignment', {
        file_ids: fileIds,
        target_assignment_id: targetAssignmentId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}
