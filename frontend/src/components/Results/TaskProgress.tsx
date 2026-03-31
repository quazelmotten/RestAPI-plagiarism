import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardBody, VStack, HStack, Heading, Text, Progress, Badge } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../../services/api';

const STAGE_META: Record<string, { phase: number; totalPhases: number }> = {
  indexing: { phase: 1, totalPhases: 4 },
  finding_intra_pairs: { phase: 2, totalPhases: 4 },
  finding_cross_pairs: { phase: 3, totalPhases: 4 },
  storing_results: { phase: 4, totalPhases: 4 },
};

interface TaskProgressProps {
  taskId: string;
  status: string;
  cardBg?: string;
  onCompleted?: () => void;
}

const getWebSocketUrl = (taskId: string): string => {
  const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const pathSegments = window.location.pathname.split('/').filter(Boolean);
  const basePath = pathSegments.length > 0 ? `/${pathSegments[0]}` : '';
  return `${wsProto}//${host}${basePath}/plagiarism/ws/tasks/${taskId}`;
};

const stageConfig: Record<string, {
  phase: number;
  totalPhases: number;
  label: string;
  color: string;
  description: string;
  unit: string;
  unitPlural: string;
}> = {
  indexing: {
    phase: 1,
    totalPhases: 4,
    label: 'Indexing Files',
    color: 'blue',
    description: 'Tokenizing source files and building the fingerprint index',
    unit: 'file',
    unitPlural: 'files',
  },
  finding_intra_pairs: {
    phase: 2,
    totalPhases: 4,
    label: 'Finding Intra-Task Pairs',
    color: 'purple',
    description: 'Comparing files within this batch for similarities',
    unit: 'file checked',
    unitPlural: 'files checked',
  },
  finding_cross_pairs: {
    phase: 3,
    totalPhases: 4,
    label: 'Finding Cross-Task Pairs',
    color: 'pink',
    description: 'Comparing new files against previously submitted files',
    unit: 'file checked',
    unitPlural: 'files checked',
  },
  storing_results: {
    phase: 4,
    totalPhases: 4,
    label: 'Storing Results',
    color: 'orange',
    description: 'Persisting similarity scores to the database',
    unit: 'pair',
    unitPlural: 'pairs',
  },
};

const ACTIVE_STATUSES = ['indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results'];

interface ProgressState {
  completed: number;
  total: number;
  percentage: number;
  status: string;
}

interface WSMessage {
  type: 'progress' | 'pong' | 'ping';
  task_id?: string;
  status?: string;
  processed_pairs?: number;
  total_pairs?: number;
  progress?: number;
  timestamp?: number;
}

const SMOOTHING_ALPHA = 0.12;

const TaskProgress: React.FC<TaskProgressProps> = ({ taskId, status: initialStatus, cardBg, onCompleted }) => {
  const { t } = useTranslation('results');
  const [progress, setProgress] = useState<ProgressState>({
    completed: 0, total: 0, percentage: 0, status: initialStatus,
  });

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statusRef = useRef(initialStatus);
  const completedRef = useRef(false);

  // Smooth animation refs
  const targetRef = useRef({ completed: 0, total: 0, percentage: 0 });
  const displayedRef = useRef({ completed: 0, total: 0, percentage: 0 });
  const animFrameRef = useRef<number | null>(null);
  const animatingRef = useRef(false);

  // Keep statusRef always in sync
  useEffect(() => {
    statusRef.current = progress.status;
  }, [progress.status]);

  // Smooth animation loop — runs at ~60fps, blends toward target via EMA
  const startAnimation = useCallback(() => {
    if (animatingRef.current) return;
    animatingRef.current = true;

    const tick = () => {
      const t = targetRef.current;
      const d = displayedRef.current;
      const atTarget =
        Math.abs(d.completed - t.completed) < 0.5 &&
        Math.abs(d.total - t.total) < 0.5 &&
        Math.abs(d.percentage - t.percentage) < 0.1;

      if (!atTarget) {
        d.completed += (t.completed - d.completed) * SMOOTHING_ALPHA;
        d.total += (t.total - d.total) * SMOOTHING_ALPHA;
        d.percentage += (t.percentage - d.percentage) * SMOOTHING_ALPHA;

        setProgress(prev => ({
          ...prev,
          completed: Math.round(d.completed),
          total: Math.round(d.total),
          percentage: d.percentage,
        }));
      }

      animFrameRef.current = requestAnimationFrame(tick);
    };

    animFrameRef.current = requestAnimationFrame(tick);
  }, []);

  const stopAnimation = useCallback(() => {
    animatingRef.current = false;
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
  }, []);

  // Push a new target — the animation loop will smoothly interpolate toward it
  const setTarget = useCallback((updates: Partial<ProgressState>) => {
    const newCompleted = updates.completed ?? targetRef.current.completed;
    const newTotal = updates.total ?? targetRef.current.total;
    const newStatus = updates.status ?? statusRef.current;

    targetRef.current.completed = newCompleted;
    targetRef.current.total = newTotal;
    targetRef.current.percentage = newTotal > 0 ? (newCompleted / newTotal) * 100 : 0;
    statusRef.current = newStatus;

    // If status changed or 100% reached, snap displayed to target immediately
    const isStatusChange = newStatus !== progress.status;
    const isComplete = newTotal > 0 && newCompleted >= newTotal;
    if (isStatusChange || isComplete) {
      displayedRef.current = { ...targetRef.current };
      setProgress({
        completed: Math.round(targetRef.current.completed),
        total: Math.round(targetRef.current.total),
        percentage: targetRef.current.percentage,
        status: newStatus,
      });
      if (newStatus === 'completed' && !completedRef.current) {
        completedRef.current = true;
        onCompleted?.();
      }
    }
  }, [progress.status]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const disconnectWebSocket = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'Component unmount');
      wsRef.current = null;
    }
  }, []);

  // Connect once per taskId, manage lifecycle internally
  useEffect(() => {
    disconnectWebSocket();
    stopPolling();
    stopAnimation();

    if (!ACTIVE_STATUSES.includes(initialStatus)) return;

    // Initialize display state
    const initPct = 0;
    targetRef.current = { completed: 0, total: 0, percentage: initPct };
    displayedRef.current = { completed: 0, total: 0, percentage: initPct };

    // Start the smooth animation loop
    startAnimation();

     if ('WebSocket' in window) {
       if (wsRef.current?.readyState === WebSocket.OPEN) return;

       const wsUrl = getWebSocketUrl(taskId);
       const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        stopPolling();
      };

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          if (msg.type === 'progress' && msg.task_id === taskId) {
            setTarget({
              completed: msg.processed_pairs ?? 0,
              total: msg.total_pairs ?? 0,
              status: msg.status ?? statusRef.current,
            });
          } else if (msg.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' }));
          }
        } catch {}
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (ACTIVE_STATUSES.includes(statusRef.current)) {
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!pollingRef.current) {
              const poll = async () => {
                try {
                  const response = await api.get(API_ENDPOINTS.TASKS);
                  const task = response.data.items.find((t: any) => t.task_id === taskId);
                  if (task) {
                    setTarget({
                      completed: task.progress?.completed ?? 0,
                      total: task.progress?.total ?? 0,
                      status: task.status,
                    });
                    if (ACTIVE_STATUSES.includes(task.status)) {
                      stopPolling();
                       if (wsRef.current?.readyState !== WebSocket.OPEN) {
                         const retryWs = new WebSocket(wsUrl);
                        wsRef.current = retryWs;
                        retryWs.onopen = () => { stopPolling(); };
                        retryWs.onmessage = ws.onmessage;
                        retryWs.onclose = ws.onclose;
                        retryWs.onerror = ws.onerror;
                      }
                    } else {
                      stopPolling();
                    }
                  }
                } catch {}
              };
              poll();
              pollingRef.current = setInterval(poll, 2000);
            }
          }, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } else {
      const poll = async () => {
        try {
          const response = await api.get(API_ENDPOINTS.TASKS);
          const task = response.data.items.find((t: any) => t.task_id === taskId);
          if (task && ACTIVE_STATUSES.includes(task.status)) {
            setTarget({
              completed: task.progress?.completed ?? 0,
              total: task.progress?.total ?? 0,
              status: task.status,
            });
          } else if (task && !ACTIVE_STATUSES.includes(task.status)) {
            setTarget({ status: task.status });
            stopPolling();
          }
        } catch {}
      };
      poll();
      pollingRef.current = setInterval(poll, 2000);
    }

    return () => {
      disconnectWebSocket();
      stopPolling();
      stopAnimation();
    };
  }, [taskId]);

  const stage = stageConfig[progress.status];
  if (!stage) return null;

  const label = t(`results:taskProgress:stages:${progress.status}:label`);
  const description = t(`results:taskProgress:stages:${progress.status}:description`);
  const unit = progress.completed === 1
    ? t(`results:taskProgress:stages:${progress.status}:unit`)
    : t(`results:taskProgress:stages:${progress.status}:unitPlural`);

  const hasProgress = progress.total > 0;

  return (
    <Card bg={cardBg} borderColor={`${stage.color}.300`} borderWidth={2}>
      <CardBody>
        <VStack align="stretch" spacing={3}>
          <HStack justify="space-between">
            <HStack>
                <Badge colorScheme={stage.color} fontSize="sm" px={2} py={0.5}>
                  {t('taskProgress:stageBadge', { current: stage.phase, total: stage.totalPhases })}
                </Badge>
                <Heading size="sm" color={`${stage.color}.600`}>
                  {label}
                </Heading>
            </HStack>
            {hasProgress && (
              <Text fontWeight="bold" color={`${stage.color}.600`}>
                {progress.completed}/{progress.total} {unit}
              </Text>
            )}
          </HStack>

          {hasProgress ? (
            <>
              <Progress
                value={progress.percentage}
                max={100}
                colorScheme={stage.color}
                size="lg"
                borderRadius="full"
                hasStripe
                isAnimated
              />
               <HStack justify="space-between" fontSize="sm" color="gray.600">
                 <Text>{t('taskProgress:percentComplete', { percent: progress.percentage.toFixed(1) })}</Text>
                 <Text>{t('taskProgress:remaining', { count: progress.total - progress.completed })}</Text>
               </HStack>
            </>
          ) : (
            <Progress
              size="lg"
              colorScheme={stage.color}
              borderRadius="full"
              isIndeterminate
            />
          )}

          <Text fontSize="xs" color="gray.500" textAlign="center">
            {description}
          </Text>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default TaskProgress;
