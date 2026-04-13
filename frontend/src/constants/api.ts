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
  TOP_SIMILAR_PAIRS: (fileId: string) => `/plagiarism/files/${fileId}/top-similar-pairs`,

  // Results - Review workflow
  CONFIRM_PLAGIARISM: (resultId: string) => `/plagiarism/results/${resultId}/confirm`,
  CLEAR_PAIR: (resultId: string) => `/plagiarism/results/${resultId}/clear`,
  SKIP_PAIR: (resultId: string) => `/plagiarism/results/${resultId}/skip`,
  UNDO_REVIEW: (resultId: string) => `/plagiarism/results/${resultId}/undo`,
  BULK_CONFIRM: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/bulk-confirm`,
  BULK_CLEAR: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/bulk-clear`,
  REVIEW_QUEUE: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/review-queue`,
  REVIEW_STATUS: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/review-status`,
  PAIRS_BY_STATUS: (assignmentId: string, status: string, limit?: number, offset?: number) => 
    `/plagiarism/assignments/${assignmentId}/pairs?status=${status}${limit ? `&limit=${limit}` : ''}${offset ? `&offset=${offset}` : ''}`,
  CLEARED_PAIRS: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/cleared-pairs`,
  PLAGIARISM_PAIRS: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/plagiarism-pairs`,
  UNCONFIRM_FILE: (fileId: string) => `/plagiarism/files/${fileId}/unconfirm`,
  EXPORT_REVIEW: (assignmentId: string, threshold: number) => 
    `/plagiarism/assignments/${assignmentId}/export-review?threshold=${threshold}`,

  // File notes
  FILE_NOTES: (fileId: string) => `/plagiarism/files/${fileId}/notes`,
  DELETE_NOTE: (noteId: string) => `/plagiarism/notes/${noteId}`,

  // Assignments
  ASSIGNMENTS: '/plagiarism/assignments',
  ASSIGNMENT_DETAILS: (id: string) => `/plagiarism/assignments/${id}`,
  ASSIGNMENT_FULL: (id: string) => `/plagiarism/assignments/${id}/full`,
  ASSIGNMENT_HISTOGRAM: (id: string, bins: number, taskId?: string) =>
    `/plagiarism/assignments/${id}/histogram?bins=${bins}${taskId ? `&task_id=${taskId}` : ''}`,
  ASSIGNMENT_RESTORE: (id: string) => `/plagiarism/assignments/${id}/restore`,

  // Subjects
  SUBJECTS: '/plagiarism/subjects',
  SUBJECT_WITH_ASSIGNMENTS: (id: string) => `/plagiarism/subjects/${id}/assignments`,
  SUBJECT_GRANT: (id: string) => `/plagiarism/subjects/${id}/grant`,
  SUBJECT_MEMBERS: (id: string) => `/plagiarism/subjects/${id}/members`,
  SUBJECT_REVOKE: (id: string, userId: string) => `/plagiarism/subjects/${id}/access/${userId}`,
  UNCATEGORIZED_ASSIGNMENTS: '/plagiarism/assignments/uncategorized',
  SUBJECT_RESTORE: (id: string) => `/plagiarism/subjects/${id}/restore`,

  // Health & version
  HEALTH: '/health',
  VERSION: '/version',
} as const;

export default API_ENDPOINTS;
