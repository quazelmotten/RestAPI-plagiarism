import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardBody,
  Text,
  Button,
  VStack,
  HStack,
  Select,
  Spinner,
  Alert,
  AlertIcon,
  Badge,
  Skeleton,
  SkeletonText,
  useColorModeValue,
  Flex,
  Icon,
  Tooltip,
  IconButton,
} from '@chakra-ui/react';
import {
  FiCheckCircle,
  FiAlertCircle,
  FiActivity,
  FiLayers,
  FiRefreshCw,
  FiChevronDown,
  FiDownload,
  FiCopy,
  FiInbox,
  FiCheck,
} from 'react-icons/fi';
import { useCopyToClipboard } from '../hooks/useCopyToClipboard';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import type { TaskListItem, TaskDetails, PlagiarismResult } from '../types';
import { useTasksList, useTaskDetails } from '../hooks/useTaskQueries';
import { getSimilarityColor, getStatusColorScheme } from '../utils/statusColors';
import TaskStats from '../components/Results/TaskStats';
import TaskProgress from '../components/Results/TaskProgress';
import SimilarityDistribution from '../components/Results/SimilarityDistribution';

import ResultsList from '../components/Results/ResultsList';
import ErrorBoundary from '../components/ErrorBoundary';
import TaskPickerModal from '../components/Results/TaskPickerModal';

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <FiCheckCircle color="#48bb78" />;
    case 'failed':
      return <FiAlertCircle color="#f56565" />;
    case 'storing_results':
      return <FiActivity color="#ed8936" />;
    case 'indexing':
      return <FiLayers color="#4299e1" />;
    case 'finding_intra_pairs':
      return <FiLayers color="#9f7aea" />;
    case 'finding_cross_pairs':
      return <FiLayers color="#805ad5" />;
    default:
       return <FiLayers color="#a0aec0" />;
  }
};

const ACTIVE_STATUSES = ['pending', 'queued', 'indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results'];

const Results: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation(['results', 'common', 'status']);
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [isTaskPickerOpen, setIsTaskPickerOpen] = useState(false);
  const userSelectedRef = React.useRef(false);


  const { data: tasksData, isLoading: loadingTasks, isFetching: isRefetchingTasks, refetch: refetchTasks } = useTasksList({ selectedTaskId });
  const tasks = tasksData?.items ?? [];

  const { data: selectedTaskDetails, isLoading: loadingTaskDetails, isFetching: isRefetchingDetails } = useTaskDetails(selectedTaskId || undefined);

  useEffect(() => {
    if (tasks.length > 0) {
      const currentExists = tasks.find(t => t.task_id === selectedTaskId);
      if (!selectedTaskId || !currentExists) {
        userSelectedRef.current = false;
        const activeTask = tasks.find(t => ACTIVE_STATUSES.includes(t.status));
        setSelectedTaskId(activeTask ? activeTask.task_id : tasks[0].task_id);
      }
    } else {
      setSelectedTaskId('');
    }
  }, [tasks]);

  const selectedTaskListItem = tasks.find(t => t.task_id === selectedTaskId);
  const selectedTask = selectedTaskDetails;

  const handleRefresh = useCallback(async () => {
    await refetchTasks();
  }, [refetchTasks]);

  const { copied: taskIdCopied, copy: copyTaskId } = useCopyToClipboard();

  const getStats = () => {
    if (!selectedTask) return { high: 0, medium: 0, low: 0, avg: 0 };

    if (selectedTask.overall_stats) {
      return {
        high: selectedTask.overall_stats.high,
        medium: selectedTask.overall_stats.medium,
        low: selectedTask.overall_stats.low,
        avg: selectedTask.overall_stats.avg_similarity
      };
    }

    if (!selectedTask.results) return { high: 0, medium: 0, low: 0, avg: 0 };

    const similarities = selectedTask.results.map((r: PlagiarismResult) => r.ast_similarity || 0);
    const high = similarities.filter((s: number) => s >= 0.5).length;
    const medium = similarities.filter((s: number) => s >= 0.25 && s < 0.5).length;
    const low = similarities.filter((s: number) => s < 0.25).length;
    const avg = similarities.length > 0
      ? similarities.reduce((a: number, b: number) => a + b, 0) / similarities.length
      : 0;

    return { high, medium, low, avg };
  };

  const stats = getStats();

  const handleCompare = (result: PlagiarismResult) => {
    navigate(`/dashboard/pair-comparison?file_a=${result.file_a.id}&file_b=${result.file_b.id}`);
  };

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');

  if (loadingTasks) {
    return (
      <Box display="flex" flexDirection="column" flex={1} minH={0} overflowY="auto">
        <Card bg={cardBg}>
          <CardBody>
            <Skeleton height="40px" />
          </CardBody>
        </Card>
        <VStack spacing={6} align="stretch" mt={6}>
          <Skeleton height="120px" />
          <Skeleton height="200px" />
          <SkeletonText noOfLines={4} spacing={4} />
        </VStack>
      </Box>
    );
  }
   
   return (
     <Box display="flex" flexDirection="column" flex={1} minH={0} overflowY="auto">
        {tasks.length === 0 ? (
          <Card bg={cardBg}>
            <CardBody>
              <Flex direction="column" align="center" justify="center" py={16} color="gray.500">
                <Icon as={FiInbox} boxSize={16} mb={4} opacity={0.5} />
                <Text fontWeight="medium" fontSize="lg">{t('noChecks')}</Text>
                <Text fontSize="sm">Upload files to get started</Text>
              </Flex>
            </CardBody>
          </Card>
        ) : (
         <VStack spacing={6} align="stretch">
           {/* Task Selector */}
           <Card bg={cardBg}>
             <CardBody>
               <HStack justify="space-between" wrap="wrap" spacing={4}>
                 <HStack>
                   <Text fontWeight="semibold">{t('selectTask')}</Text>
                    <Button
                      size="sm"
                      rightIcon={<FiChevronDown />}
                      onClick={() => setIsTaskPickerOpen(true)}
                      minW="320px"
                      variant="outline"
                    >
                      {selectedTaskListItem ? (
                        <HStack spacing={2} isTruncated>
                          {getStatusIcon(selectedTaskListItem.status)}
                          <Text isTruncated fontSize="sm">
                            {selectedTaskListItem.task_id.substring(0, 12)}...
                          </Text>
                          <Tooltip label={taskIdCopied ? 'Copied!' : 'Copy task ID'} placement="top">
                            <Tooltip label={taskIdCopied ? 'Copied!' : 'Copy task ID'} placement="top">
                              <IconButton
                                aria-label="Copy task ID"
                                icon={taskIdCopied ? <FiCheck color="green.500" /> : <FiCopy />}
                                size="xs"
                                variant="ghost"
                                onClick={(e: React.MouseEvent) => {
                                  e.stopPropagation();
                                  copyTaskId(selectedTaskListItem.task_id);
                                }}
                                isDisabled={taskIdCopied}
                              />
                            </Tooltip>
                          </Tooltip>
                          <Badge size="sm" colorScheme={getStatusColorScheme(selectedTaskListItem.status)}>
                            {t(`status:${selectedTaskListItem.status}`)}
                          </Badge>
                          {['indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results'].includes(selectedTaskListItem.status) && selectedTaskListItem.progress && (
                            <Text fontSize="xs" color="gray.500">
                              {selectedTaskListItem.progress.display}
                            </Text>
                          )}
                        </HStack>
                      ) : (
                        t('selectTaskPrompt')
                      )}
                    </Button>
                    {selectedTaskListItem && ['indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results'].includes(selectedTaskListItem.status) && (
                       <Spinner size="sm" color="orange.500" speed="0.8s" />
                    )}
                      <Button
                        size="sm"
                        leftIcon={<FiRefreshCw />}
                        onClick={handleRefresh}
                        isLoading={isRefetchingTasks}
                      >
                        {t('common:refresh')}
                      </Button>
                      {selectedTask && selectedTask.results.length > 0 && (
                        <Button
                          size="sm"
                          leftIcon={<FiDownload />}
                          variant="outline"
                          onClick={() => {
                            const headers = ['File A', 'File B', 'Similarity', 'Task ID'];
                            const rows = selectedTask.results.map(r => [
                              r.file_a.filename,
                              r.file_b.filename,
                              ((r.ast_similarity || 0) * 100).toFixed(2) + '%',
                              r.file_a.task_id || '',
                            ]);
                            const csvContent = [
                              headers.join(','),
                              ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
                            ].join('\n');
                            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                            const url = URL.createObjectURL(blob);
                            const link = document.createElement('a');
                            link.href = url;
                            link.download = `plagiarism-results-${selectedTask.task_id.substring(0, 8)}.csv`;
                            link.click();
                            URL.revokeObjectURL(url);
                          }}
                        >
                          Export CSV
                        </Button>
                      )}
                  </HStack>


               </HStack>
             </CardBody>
           </Card>

          <TaskPickerModal
            isOpen={isTaskPickerOpen}
            onClose={() => setIsTaskPickerOpen(false)}
            onSelect={(task) => setSelectedTaskId(task.task_id)}
            tasks={tasks}
            selectedTaskId={selectedTaskId}
            loading={loadingTasks}
          />
          
           {selectedTask ? (
              <ErrorBoundary>
                 <TaskStats
                   selectedTask={selectedTask}
                   avgSimilarity={stats.avg}
                   getSimilarityColor={getSimilarityColor}
                   getStatusIcon={getStatusIcon}
                   getStatusColorScheme={getStatusColorScheme}
                   cardBg={cardBg}
                 />
                
                <TaskProgress taskId={selectedTask.task_id} status={selectedTask.status} cardBg={cardBg} onCompleted={handleRefresh} />
                
                 <SimilarityDistribution
                   results={selectedTask.results}
                   totalPairs={selectedTask.total_pairs}
                   cardBg={cardBg}
                   taskId={selectedTask.task_id}
                   stats={stats}
                 />
                
                  {/* Results View */}
                  <ResultsList
                    results={selectedTask.results}
                    totalPairs={selectedTask.total_pairs}
                    borderColor={borderColor}
                    hoverBg={hoverBg}
                    getSimilarityColor={getSimilarityColor}
                    handleCompare={handleCompare}
                    cardBg={cardBg}
                    loading={loadingTaskDetails || isRefetchingDetails}
                  />
              </ErrorBoundary>
           ) : loadingTaskDetails ? (
            <Box textAlign="center" py={8}>
              <Spinner size="lg" />
            </Box>
          ) : null}
        </VStack>
      )}
    </Box>
  );
};

export default Results;