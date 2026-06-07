/**
 * Data transformation utilities for converting between backend and frontend data formats
 */

import type { ResultItem, BackendFileInfo } from '../types';

/**
 * Transform backend ResultItem to frontend ReviewPair format
 * This handles the schema mismatch where backend returns nested file objects
 * but frontend expects flat file name fields
 */
export function transformResultItemToReviewPair(item: ResultItem): any {
  return {
    pair_id: item.id || '',
    task_id: item.file_a.task_id || item.file_b.task_id || '',
    file_a_id: item.file_a.id,
    file_a_name: item.file_a.filename,
    file_b_id: item.file_b.id,
    file_b_name: item.file_b.filename,
    ast_similarity: item.ast_similarity,
    embedding_similarity: item.embedding_similarity,
    review_disposition: item.review_disposition,
    reviewed_at: item.reviewed_at || null,
    assignment_id: null, // Will be populated by the component if needed
    assignment_name: null, // Will be populated by the component if needed
    upload_name: null, // Will be populated by the component if needed
    created_at: item.created_at,
  };
}

/**
 * Transform array of ResultItem to array of ReviewPair
 */
export function transformResultItemsToReviewPairs(items: ResultItem[]): any[] {
  return items.map(item => transformResultItemToReviewPair(item));
}

/**
 * Extract error details from 422 validation errors
 */
export function extractValidationErrorDetails(error: any): string {
  if (error.response?.status === 422) {
    const errorData = error.response.data;
    
    // Handle different error response formats
    if (errorData.detail) {
      // Single error detail
      return typeof errorData.detail === 'string' 
        ? errorData.detail 
        : JSON.stringify(errorData.detail);
    }
    
    if (errorData.errors) {
      // Multiple validation errors (Pydantic v2 format)
      return Object.entries(errorData.errors)
        .map(([field, errors]) => {
          const errorMessages = Array.isArray(errors) 
            ? errors.map((e: any) => e.msg || e.message || String(e)).join(', ')
            : String(errors);
          return `${field}: ${errorMessages}`;
        })
        .join('; ');
    }
    
    if (typeof errorData === 'string') {
      return errorData;
    }
  }
  
  return 'Invalid input parameters';
}