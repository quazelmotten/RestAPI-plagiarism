import type { FileSubmission, SubmissionsResponse } from '../types';
import api from '../../../services/api';

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
  }
): Promise<SubmissionsResponse> {
  const params: Record<string, unknown> = { limit, offset };

  if (filters.filename) params.filename = filters.filename;
  if (filters.language) params.language = filters.language;
  if (filters.status) params.status = filters.status;
  if (filters.task_id) params.task_id = filters.task_id;

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

  const response = await api.get<SubmissionsResponse>('/plagiarism/files', { params });
  return response.data;
}

export async function fetchSubmissionsMetadata(): Promise<{ taskIds: string[]; languages: string[] }> {
  try {
    const response = await api.get<Array<{ task_id: string; filename: string; language: string }>>('/plagiarism/files/list');
    const data = response.data as Array<{ task_id: string; filename: string; language: string }>;
    const taskIds = [...new Set(data.map((item) => item.task_id))].sort();
    const languages = [...new Set(data.map((item) => item.language))].sort();
    return { taskIds, languages };
  } catch (err) {
    console.error('Failed to fetch metadata:', err);
    return { taskIds: [], languages: [] };
  }
}
