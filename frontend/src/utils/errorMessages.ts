/**
 * Maps an Axios error from the assignments API to a localized message
 * suitable for displaying in a toast or notification.
 *
 * The backend never returns localized messages, so the frontend owns
 * the user-facing copy. We pick a translation key based on the HTTP
 * status code, then fall back to the backend's `error_details` field,
 * then to a generic message.
 */
import type { TFunction } from 'i18next';

interface ApiErrorBody {
  error_details?: string;
  detail?: string;
}

interface MaybeAxiosError {
  response?: { status?: number; data?: ApiErrorBody };
}

export const formatAssignmentCreateError = (
  err: unknown,
  t: TFunction
): string => {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as MaybeAxiosError;
    const status = axiosErr.response?.status;
    if (status === 409) {
      return t('common:errors.assignmentNameExists');
    }
    const backendMessage =
      axiosErr.response?.data?.error_details ||
      axiosErr.response?.data?.detail;
    if (backendMessage) {
      return backendMessage;
    }
  }
  return t('common:errors.generic');
};
