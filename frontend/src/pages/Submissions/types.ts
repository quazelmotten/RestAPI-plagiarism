export interface FileSubmission {
  id: string;
  filename: string;
  language: string;
  created_at: string;
  task_id: string;
  status: string;
  similarity: number | null;
  assignment_id?: string | null;
  assignment_name?: string | null;
  subject_id?: string | null;
  subject_name?: string | null;
}

export interface SubmissionsResponse {
  items: FileSubmission[];
  total: number;
  limit: number;
  offset: number;
}

export interface Filters {
  filename: string;
  language: string;
  status: string;
  similarity: string;
  submittedAt: string;
  task_id: string;
  assignment_id: string;
  subject_id: string;
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
