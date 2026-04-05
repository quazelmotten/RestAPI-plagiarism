import { useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';
import type { FileInfo, FileContent, ApiError } from '../types';

interface FilesListResponse {
  items: FileInfo[];
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
