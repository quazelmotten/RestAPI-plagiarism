export interface User {
  id: string;
  username: string;
  email: string;
  role: 'teacher' | 'admin';
}

export interface Student {
  id: string;
  username: string;
  email: string;
  fullName: string;
  createdAt: string;
  submissionsCount: number;
}

export interface Submission {
  id: string;
  studentId: string;
  studentName: string;
  fileName: string;
  language: string;
  createdAt: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  similarity?: number;
}

export interface PlagiarismMatch {
  file1: string;
  file2: string;
  similarity: number;
  matches: Array<{
    startLine1: number;
    endLine1: number;
    startLine2: number;
    endLine2: number;
    text: string;
  }>;
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
