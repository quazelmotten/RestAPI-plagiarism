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
  plagiarism_type?: number; // 1=exact, 2=renamed, 3=reordered, 4=semantic
  similarity?: number;
  details?: Record<string, any> | null;
  description?: string | null;
}

export const PLAGIARISM_TYPE_COLORS: Record<number, string> = {
  1: 'rgba(76, 175, 80, 0.3)',    // green - exact copy
  2: 'rgba(255, 235, 59, 0.35)',   // yellow - renamed identifiers
  3: 'rgba(33, 150, 243, 0.3)',    // blue - reordered code
  4: 'rgba(244, 67, 54, 0.3)',     // red - semantic equivalent
};

export const PLAGIARISM_TYPE_COLORS_HOVER: Record<number, string> = {
  1: 'rgba(76, 175, 80, 0.6)',
  2: 'rgba(255, 235, 59, 0.7)',
  3: 'rgba(33, 150, 243, 0.6)',
  4: 'rgba(244, 67, 54, 0.6)',
};

export const PLAGIARISM_TYPE_BORDERS: Record<number, string> = {
  1: '#388E3C',
  2: '#FBC02D',
  3: '#1976D2',
  4: '#D32F2F',
};

export const PLAGIARISM_TYPE_LABELS: Record<number, string> = {
  1: 'Exact copy',
  2: 'Renamed identifiers',
  3: 'Reordered code',
  4: 'Semantic equivalent',
};

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
  avg_similarity?: number;
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

export interface AssignmentFullFile {
  id: string;
  filename: string;
  task_id: string | null;
  max_similarity?: number;
}

export interface AssignmentFullStats {
  avg_similarity: number;
  high: number;
  medium: number;
  low: number;
  total_results: number;
}

export interface AssignmentFullResponse {
  id: string;
  name: string;
  description: string | null;
  created_at: string | null;
  tasks_count: number;
  files_count: number;
  tasks: TaskListItem[];
  files: AssignmentFullFile[];
  total_files: number;
  results: PlagiarismResult[];
  total_pairs: number;
  total_results: number;
  overall_stats: AssignmentFullStats | null;
}

export type { PlagiarismMatch as Match };

export interface HeatmapFile {
  id: string;
  filename: string;
  max_similarity: number;
}

export interface HeatmapPair {
  file_a_id: string;
  file_b_id: string;
  ast_similarity: number;
}

export interface HeatmapData {
  files: HeatmapFile[];
  pairs: HeatmapPair[];
  threshold: number;
  total_files_in_task: number;
}
