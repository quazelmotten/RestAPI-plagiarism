export interface User {
  id: string;
  username: string;
  email: string;
  role: 'teacher' | 'admin';
}

type TaskStatus = 'pending' | 'queued' | 'indexing' | 'finding_intra_pairs' | 'finding_cross_pairs' | 'storing_results' | 'processing' | 'completed' | 'failed';

export interface Submission {
  id: string;
  fileName: string;
  language: string;
  createdAt: string;
  status: TaskStatus;
  similarity?: number;
}

export interface PlagiarismMatch {
  file_a_start_line: number;
  file_a_end_line: number;
  file_b_start_line: number;
  file_b_end_line: number;
}

export interface PlagiarismResult {
  file_a: {
    id: string;
    filename: string;
    task_id?: string; // The task this file belongs to (may differ from selected task for cross-task)
  };
  file_b: {
    id: string;
    filename: string;
    task_id?: string;
  };
  ast_similarity: number;
  matches: PlagiarismMatch[];
  created_at: string;
}

export interface PlagiarismNetwork {
  nodes: Array<{
    id: string;
    label: string;
    group?: string;
  }>;
  edges: Array<{
    source: string;
    target: string;
    similarity: number;
  }>;
}

export interface TaskListItem {
  task_id: string;
  status: TaskStatus;
  total_pairs: number;
  progress?: {
    completed: number;
    total: number;
    percentage: number;
    display: string;
  };
  files_count?: number;
  high_similarity_count?: number;
  created_at?: string;
}

export interface TaskDetails extends TaskListItem {
  files: Array<{
    id: string;
    filename: string;
    task_id?: string; // Include task_id for each file (should match the task_id for intra-task files)
  }>;
  results: PlagiarismResult[];
  overall_stats?: {
    avg_similarity: number;
    high: number;
    medium: number;
    low: number;
    total_results: number;
  };
}

export interface FileInfo {
  id: string;
  filename: string;
  language: string;
  task_id: string;
  status: string;
  similarity?: number;
}

export interface FileContent {
  id: string;
  filename: string;
  content: string;
  language: string;
}

export interface ApiError {
  response?: {
    data: {
      detail?: string;
    };
    status?: number;
  };
  message?: string;
}

export type { PlagiarismMatch as Match };
