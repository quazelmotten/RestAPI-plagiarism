import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import { useFileEvents } from '../../../hooks/useFileQueries';

const EVENT_ICONS: Record<string, string> = {
  upload_queued: '🔄',
  upload_completed: '✅',
  upload_failed: '❌',
  file_uploaded: '📄',
  file_deleted: '🗑️',
  file_moved: '📦',
  reanalysis_triggered: '🔁',
};

const EVENT_COLORS: Record<string, string> = {
  upload_queued: 'text-blue-600 bg-blue-50 border-blue-200',
  upload_completed: 'text-green-600 bg-green-50 border-green-200',
  upload_failed: 'text-red-600 bg-red-50 border-red-200',
  file_uploaded: 'text-indigo-600 bg-indigo-50 border-indigo-200',
  file_deleted: 'text-orange-600 bg-orange-50 border-orange-200',
  file_moved: 'text-purple-600 bg-purple-50 border-purple-200',
  reanalysis_triggered: 'text-yellow-600 bg-yellow-50 border-yellow-200',
};

export default function EventsTab() {
  const { t } = useTranslation('assignments');
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const { data, isLoading } = useFileEvents({ assignment_id: assignmentId, limit: 200 });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  const events = data?.items ?? [];

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-500">
        <div className="mb-2 text-4xl">📋</div>
        <p>{t('noEvents')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {events.map((event) => {
        const icon = EVENT_ICONS[event.event_type] || '📌';
        const color = EVENT_COLORS[event.event_type] || 'text-gray-600 bg-gray-50 border-gray-200';
        const meta = event.metadata ?? {};

        return (
          <div
            key={event.id}
            className={`flex items-start gap-3 rounded-lg border p-3 ${color}`}
          >
            <div className="text-lg">{icon}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-sm">
                  {t(`eventTypes.${event.event_type}`, event.event_type)}
                </span>
                {event.created_at && (
                  <span className="text-xs text-gray-500 whitespace-nowrap">
                    {new Date(event.created_at).toLocaleString()}
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-xs text-gray-600 space-y-0.5">
                {!!meta.filename && <div>{t('assignments:meta.file')}{String(meta.filename)}</div>}
                {!!meta.name && <div>{t('assignments:meta.name')}{String(meta.name)}</div>}
                {meta.files_count !== undefined && <div>{t('assignments:meta.files')}{String(meta.files_count)}</div>}
                {!!meta.error && <div>{t('assignments:meta.error')}{String(meta.error)}</div>}
                {!!meta.language && <div>{t('assignments:meta.language')}{String(meta.language)}</div>}
                {!!meta.source_task_id && (
                  <div>
                    {t('assignments:meta.movedFrom')}{String(meta.source_task_id).substring(0, 8)}...
                  </div>
                )}
                {!!meta.target_task_id && (
                  <div>
                    {t('assignments:meta.movedTo')}{String(meta.target_task_id).substring(0, 8)}...
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
