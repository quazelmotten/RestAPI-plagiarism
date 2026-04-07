import type { SubmissionsResponse } from '../types';
import api, { API_ENDPOINTS } from '../../../services/api';

interface FileMetadata {
  id: string;
  filename: string;
  language: string;
  task_id: string;
  assignment_id?: string | null;
  assignment_name?: string | null;
  subject_id?: string | null;
  subject_name?: string | null;
}

interface PaginatedFileMetadata {
  items: FileMetadata[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchSubmissions(
  offset: number,
  limit: number,
  filters: {
    filename?: string;
    language?: string;
    status?: string;
    similarity?: string;
    submittedAt?: string;
    task_id?: string;
    assignment_id?: string;
    subject_id?: string;
  }
): Promise<SubmissionsResponse> {
  const params: Record<string, unknown> = { limit, offset };

  if (filters.filename) params.filename = filters.filename;
  if (filters.language) params.language = filters.language;
  if (filters.status) params.status = filters.status;
  if (filters.task_id) params.task_id = filters.task_id;
  if (filters.assignment_id) params.assignment_id = filters.assignment_id;
  if (filters.subject_id) params.subject_id = filters.subject_id;

  if (filters.similarity) {
    const val = filters.similarity;
    let num: number | null = null;
    if (val.startsWith('>=')) num = parseFloat(val.slice(2));
    else if (val.startsWith('<=')) num = parseFloat(val.slice(2));
    else if (val.startsWith('>')) num = parseFloat(val.slice(1));
    else if (val.startsWith('<')) num = parseFloat(val.slice(1));
    else num = parseFloat(val);
    if (!isNaN(num)) {
      if (num > 1) num = num / 100;
      if (val.startsWith('>=')) params.similarity_min = num;
      else if (val.startsWith('<=')) params.similarity_max = num;
      else if (val.startsWith('>')) params.similarity_min = num;
      else if (val.startsWith('<')) params.similarity_max = num;
      else {
        params.similarity_min = num;
        params.similarity_max = num;
      }
    }
  }

  if (filters.submittedAt) {
    params.submitted_after = filters.submittedAt;
    params.submitted_before = filters.submittedAt;
  }

  const response = await api.get<SubmissionsResponse>(API_ENDPOINTS.FILES, { params });
  return response.data;
}

export async function fetchSubmissionsMetadata(): Promise<{ 
  taskIds: string[]; 
  languages: string[]; 
  assignments: Array<{ id: string; name: string }>; 
  subjects: Array<{ id: string; name: string }>; 
}> {
  try {
    const response = await api.get<PaginatedFileMetadata>(API_ENDPOINTS.FILES_LIST);
    const items = response.data.items;
    const taskIds = [...new Set(items.map((item) => item.task_id))].sort();
    const languages = [...new Set(items.map((item) => item.language))].sort();
    
    // Extract unique assignments (filter out null/undefined)
    const assignmentMap = new Map<string, string>();
    const subjectMap = new Map<string, string>();
    items.forEach(item => {
      if (item.assignment_id && item.assignment_name) {
        assignmentMap.set(item.assignment_id, item.assignment_name);
      }
      if (item.subject_id && item.subject_name) {
        subjectMap.set(item.subject_id, item.subject_name);
      }
    });
    const assignments = Array.from(assignmentMap.entries()).map(([id, name]) => ({ id, name })).sort((a,b) => a.name.localeCompare(b.name));
    const subjects = Array.from(subjectMap.entries()).map(([id, name]) => ({ id, name })).sort((a,b) => a.name.localeCompare(b.name));
    
    return { taskIds, languages, assignments, subjects };
  } catch (err) {
    console.error('Failed to fetch metadata:', err);
    return { taskIds: [], languages: [], assignments: [], subjects: [] };
  }
}
