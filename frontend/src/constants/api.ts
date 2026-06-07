/**
 * API Endpoints
 * Centralized constant definitions for all API routes
 */

export const API_ENDPOINTS = {
  // Plagiarism checks (legacy)
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

  // Uploads (new API)
  UPLOADS: '/plagiarism/uploads',
  UPLOAD_DETAILS: (taskId: string) => `/plagiarism/uploads/${taskId}`,
  UPDATE_UPLOAD: (taskId: string) => `/plagiarism/uploads/${taskId}`,
  DELETE_UPLOAD: (taskId: string) => `/plagiarism/uploads/${taskId}`,
  REANALYZE_UPLOAD: (taskId: string) => `/plagiarism/uploads/${taskId}/reanalyze`,
  UPLOAD_FILES: (taskId: string) => `/plagiarism/uploads/${taskId}/files`,
  DELETE_UPLOAD_FILE: (taskId: string, fileId: string) => `/plagiarism/uploads/${taskId}/files/${fileId}`,
  UPDATE_UPLOAD_FILE: (taskId: string, fileId: string) => `/plagiarism/uploads/${taskId}/files/${fileId}`,

  // Results - Review workflow
  CONFIRM_PLAGIARISM: (resultId: string) => `/plagiarism/results/${resultId}/confirm`,
  CLEAR_PAIR: (resultId: string) => `/plagiarism/results/${resultId}/clear`,
  SKIP_PAIR: (resultId: string) => `/plagiarism/results/${resultId}/skip`,
  UNDO_REVIEW: (resultId: string) => `/plagiarism/results/${resultId}/undo`,
  BULK_CONFIRM: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/bulk-confirm`,
  BULK_CLEAR: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/bulk-clear`,
  GLOBAL_BULK_CONFIRM: '/plagiarism/bulk-confirm',
  GLOBAL_BULK_CLEAR: '/plagiarism/bulk-clear',
  REVIEW_QUEUE: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/review-queue`,
  REVIEW_STATUS: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/review-status`,
  PAIRS_BY_STATUS: (assignmentId: string, status: string, limit?: number, offset?: number) => 
    `/plagiarism/assignments/${assignmentId}/pairs?status=${status}${limit ? `&limit=${limit}` : ''}${offset ? `&offset=${offset}` : ''}`,
  CLEARED_PAIRS: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/cleared-pairs`,
  PLAGIARISM_PAIRS: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/plagiarism-pairs`,
  UNCONFIRM_FILE: (fileId: string) => `/plagiarism/files/${fileId}/unconfirm`,
  EXPORT_REVIEW: (assignmentId: string, threshold: number) =>
    `/plagiarism/assignments/${assignmentId}/export-review?threshold=${threshold}`,

  // Global Review Queue (new)
  GLOBAL_REVIEW_QUEUE: '/plagiarism/review-queue',
  REVIEW_QUEUE_COUNT: '/plagiarism/review-queue/count',
  ASSIGNMENT_REVIEW_QUEUE: (assignmentId: string) => `/plagiarism/assignments/${assignmentId}/review-queue`,

  // PDF Export
  EXPORT_PDF: (assignmentId: string, resultId: string) =>
    `/plagiarism/assignments/${assignmentId}/reports/${resultId}/pdf`,
  EXPORT_PDF_ZIP: (assignmentId: string, taskId?: string) =>
    `/plagiarism/assignments/${assignmentId}/reports/pdf-zip${taskId ? `?task_id=${taskId}` : ''}`,

  // File notes
  FILE_NOTES: (fileId: string) => `/plagiarism/files/${fileId}/notes`,
  DELETE_NOTE: (noteId: string) => `/plagiarism/notes/${noteId}`,

  // File moves
  FILE_MOVE: (fileId: string) => `/plagiarism/files/${fileId}/move`,
  BULK_MOVE_FILES: '/plagiarism/files/bulk/move',
  DELETE_FILE: (fileId: string) => `/plagiarism/files/${fileId}`,

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

  // Task lifecycle (legacy)
  SOFT_DELETE_TASK: (taskId: string) => `/plagiarism/tasks/${taskId}/soft-delete`,
  HARD_DELETE_TASK: (taskId: string) => `/plagiarism/tasks/${taskId}`,
  REASSIGN_TASK: (taskId: string) => `/plagiarism/tasks/${taskId}/reassign`,
  ORPHANED_TASKS: '/plagiarism/tasks/orphaned',
  CLEANUP_ORPHANED_TASKS: '/plagiarism/tasks/orphaned/cleanup',

  // Storage
  STORAGE_USAGE: '/plagiarism/storage/usage',
  ASSIGNMENT_STORAGE_USAGE: (assignmentId: string) => `/plagiarism/storage/usage/${assignmentId}`,

  // Quick Check
  QUICK_CHECK: '/plagiarism/quick-check',

  // Events
  TASK_EVENTS: '/plagiarism/task-events',
} as const;

export default API_ENDPOINTS;
