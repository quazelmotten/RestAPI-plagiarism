/**
 * API Endpoints
 * Centralized constant definitions for all API routes
 */

export const API_ENDPOINTS = {
  // Plagiarism checks
  CHECK: '/plagiarism/check',
  TASKS: '/plagiarism/tasks',
  TASK_DETAILS: (taskId: string) => `/plagiarism/tasks/${taskId}/results`,
  TASK_HISTOGRAM: (taskId: string, bins: number) => `/plagiarism/tasks/${taskId}/histogram?bins=${bins}`,
  FILE_PAIR: '/plagiarism/file-pair',
  FILE_PAIR_ANALYZE: '/plagiarism/file-pair/analyze',
  FILES_LIST: '/plagiarism/files/list',
  FILES: '/plagiarism/files',
  FILE_CONTENT: (fileId: string) => `/plagiarism/files/${fileId}/content`,
  FILE_SIMILARITIES: (fileId: string) => `/plagiarism/files/${fileId}/similarities`,

  // Assignments
  ASSIGNMENTS: '/plagiarism/assignments',
  ASSIGNMENT_DETAILS: (id: string) => `/plagiarism/assignments/${id}`,
  ASSIGNMENT_FULL: (id: string) => `/plagiarism/assignments/${id}/full`,
  ASSIGNMENT_HISTOGRAM: (id: string, bins: number, taskId?: string) =>
    `/plagiarism/assignments/${id}/histogram?bins=${bins}${taskId ? `&task_id=${taskId}` : ''}`,

  // Health & version
  HEALTH: '/health',
  VERSION: '/version',
} as const;

export default API_ENDPOINTS;
