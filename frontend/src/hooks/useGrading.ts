import { useMutation, useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';
import type { ReviewQueueResponse, PlagiarismResult, ReviewStatusSummary } from '../types';

interface ReviewProgress {
  total_files: number;
  confirmed_files: number;
  remaining_files: number;
}

interface UseReviewQueueOptions {
  assignmentId: string;
  limit?: number;
}

export function useReviewQueue({ assignmentId, limit = 50 }: UseReviewQueueOptions) {
  return useQuery<ReviewQueueResponse>({
    queryKey: ['reviewQueue', assignmentId, limit],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.REVIEW_QUEUE(assignmentId), {
        params: { limit },
      });
      return res.data;
    },
    enabled: !!assignmentId,
  });
}

export function useConfirmPlagiarism() {
  return useMutation({
    mutationFn: async (resultId: string) => {
      const res = await api.post(API_ENDPOINTS.CONFIRM_PLAGIARISM(resultId));
      return res.data;
    },
  });
}

export function useSkipPair() {
  return useMutation({
    mutationFn: async (resultId: string) => {
      const res = await api.post(API_ENDPOINTS.SKIP_PAIR(resultId));
      return res.data;
    },
  });
}

export function useBulkConfirm() {
  return useMutation({
    mutationFn: async ({ assignmentId, threshold }: { assignmentId: string; threshold: number }) => {
      const res = await api.post(API_ENDPOINTS.BULK_CONFIRM(assignmentId), null, {
        params: { threshold },
      });
      return res.data;
    },
  });
}

export function useBulkClear() {
  return useMutation({
    mutationFn: async ({ assignmentId, threshold }: { assignmentId: string; threshold: number }) => {
      const res = await api.post(API_ENDPOINTS.BULK_CLEAR(assignmentId), null, {
        params: { threshold },
      });
      return res.data;
    },
  });
}

interface FileNote {
  id: string;
  file_id: string;
  assignment_id: string;
  content: string;
  created_at: string;
}

export function useFileNotes(fileId: string) {
  return useQuery<FileNote[]>({
    queryKey: ['fileNotes', fileId],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.FILE_NOTES(fileId));
      return res.data;
    },
    enabled: !!fileId,
  });
}

export function useAddNote() {
  return useMutation({
    mutationFn: async ({ fileId, content }: { fileId: string; content: string }) => {
      const res = await api.post(API_ENDPOINTS.FILE_NOTES(fileId), { content });
      return res.data;
    },
  });
}

export function useDeleteNote() {
  return useMutation({
    mutationFn: async (noteId: string) => {
      await api.delete(API_ENDPOINTS.DELETE_NOTE(noteId));
    },
  });
}

interface ExportReviewResponse {
  html_content: string;
  filename: string;
}

export function useExportReview() {
  return useMutation({
    mutationFn: async ({ assignmentId, threshold = 0.3 }: { assignmentId: string; threshold?: number }) => {
      const res = await api.get<ExportReviewResponse>(API_ENDPOINTS.EXPORT_REVIEW(assignmentId, threshold));
      return res.data;
    },
  });
}

export function useReviewStatus(assignmentId: string) {
  return useQuery<ReviewStatusSummary>({
    queryKey: ['reviewStatus', assignmentId],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.REVIEW_STATUS(assignmentId));
      return res.data;
    },
    enabled: !!assignmentId,
  });
}

export function usePairsByStatus(assignmentId: string, status: string, limit = 100, offset = 0) {
  return useQuery<{ items: PlagiarismResult[]; total: number; limit: number; offset: number }>({
    queryKey: ['pairsByStatus', assignmentId, status, limit, offset],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.PAIRS_BY_STATUS(assignmentId, status, limit, offset));
      return res.data;
    },
    enabled: !!assignmentId,
  });
}