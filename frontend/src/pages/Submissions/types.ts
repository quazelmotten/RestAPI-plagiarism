export interface FileSubmission {
  id: string;
  filename: string;
  language: string;
  created_at: string;
  task_id: string;
  status: 'queued' | 'indexing' | 'finding_pairs' | 'processing' | 'completed' | 'failed';
  similarity: number | null;
}

export interface SubmissionsResponse {
  files: FileSubmission[];
  total: number;
}

export interface Filters {
  filename: string;
  language: string;
  status: string;
  similarity: string;
  submittedAt: string;
  task_id: string;
}

export interface PaginationInfo {
  offset: number;
  limit: number;
  total: number;
  totalPages: number;
  showingStart: number;
  showingEnd: number;
}

export type SortDirection = 'asc' | 'desc';

export interface SortState {
  column: keyof FileSubmission;
  direction: SortDirection;
}
