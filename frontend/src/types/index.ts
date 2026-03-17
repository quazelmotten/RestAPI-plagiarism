export interface User {
  id: string;
  username: string;
  email: string;
  role: 'teacher' | 'admin';
}

export interface Submission {
  id: string;
  fileName: string;
  language: string;
  createdAt: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
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
  };
  file_b: {
    id: string;
    filename: string;
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
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_pairs: number;
  progress?: {
    completed: number;
    total: number;
    percentage: number;
    display: string;
  };
  files_count?: number;
  high_similarity_count?: number;
}

export interface TaskDetails extends TaskListItem {
  files: Array<{
    id: string;
    filename: string;
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
