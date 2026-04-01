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
  useColorModeValue,
} from '@chakra-ui/react';
import {
  FiCheckCircle,
  FiAlertCircle,
  FiActivity,
  FiLayers,
  FiRefreshCw,
  FiChevronDown,
} from 'react-icons/fi';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../services/api';
import type { TaskListItem, TaskDetails, PlagiarismResult } from '../types';
import TaskStats from '../components/Results/TaskStats';
import TaskProgress from '../components/Results/TaskProgress';
import SimilarityDistribution from '../components/Results/SimilarityDistribution';
import HeatmapView from '../components/Results/HeatmapView';
import ResultsList from '../components/Results/ResultsList';
import ErrorBoundary from '../components/ErrorBoundary';
import TaskPickerModal from '../components/Results/TaskPickerModal';

const getSimilarityColor = (similarity: number) => {
  if (similarity >= 0.8) return 'red';
  if (similarity >= 0.5) return 'orange';
  if (similarity >= 0.3) return 'yellow';
  return 'green';
};

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

const getStatusColorScheme = (status: string) => {
  switch (status) {
    case 'completed':
      return 'green';
    case 'failed':
      return 'red';
    case 'storing_results':
      return 'orange';
    case 'indexing':
      return 'blue';
    case 'finding_intra_pairs':
      return 'purple';
    case 'finding_cross_pairs':
      return 'purple';
    default:
      return 'gray';
  }
};

const Results: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation(['results', 'common', 'status']);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [isTaskPickerOpen, setIsTaskPickerOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'cards' | 'heatmap'>('cards');
  const [selectedTaskDetails, setSelectedTaskDetails] = useState<TaskDetails | null>(null);
  const [loadingTaskDetails, setLoadingTaskDetails] = useState(false);

    const loadTasks = useCallback(async () => {
       try {
         setLoading(true);
         const response = await api.get<{ items: TaskListItem[] }>(API_ENDPOINTS.TASKS);
         const taskList = response.data.items;

         if (!Array.isArray(taskList)) {
           console.error('Expected array from /plagiarism/tasks, got:', typeof taskList, taskList);
           setError(t('invalidDataFormat'));
           setTasks([]);
           return;
         }

         // Sort by created_at descending (most recent first)
         taskList.sort((a, b) => {
           const dateA = new Date(a.created_at || 0).getTime();
           const dateB = new Date(b.created_at || 0).getTime();
           return dateB - dateA;
         });

         setTasks(taskList);
       } catch (err) {
         setError(t('failedToFetchTasks'));
         console.error(err);
       } finally {
         setLoading(false);
       }
     }, [t]);

   useEffect(() => {
     loadTasks();
    }, [loadTasks]);

    // Auto-select most recent task when tasks load
    useEffect(() => {
      if (tasks.length > 0) {
        const currentExists = tasks.find(t => t.task_id === selectedTaskId);
        if (!selectedTaskId || !currentExists) {
          setSelectedTaskId(tasks[0].task_id);
        }
      } else {
        setSelectedTaskId('');
      }
    }, [tasks, selectedTaskId]);

   // Load tasks when modal opens (lazy loading)
   useEffect(() => {
     if (isTaskPickerOpen && tasks.length === 0) {
       loadTasks();
     }
   }, [isTaskPickerOpen, tasks.length, loadTasks]);

    const fetchTaskDetails = useCallback(async () => {
      if (!selectedTaskId) return;
      try {
        setLoadingTaskDetails(true);
        setSelectedTaskDetails(null);

        // Fetch only top 50 results for performance
        const limitToUse = 50;

        const response = await api.get<TaskDetails>(API_ENDPOINTS.TASK_DETAILS(selectedTaskId), {
          params: {
            limit: limitToUse,
            offset: 0
          }
        });
        const data = response.data;

        const taskDetails: TaskDetails = {
          task_id: data.task_id,
          status: data.status,
          total_pairs: data.total_pairs,
          files: data.files,
          results: data.results,
          progress: data.progress || {
            completed: 0,
            total: 0,
            percentage: 0,
            display: '0%',
          },
          overall_stats: data.overall_stats
        };

        setSelectedTaskDetails(taskDetails);
      } catch (err) {
        console.error('Failed to fetch task details:', err);
      } finally {
        setLoadingTaskDetails(false);
      }
     }, [selectedTaskId]);

     useEffect(() => {
       if (selectedTaskId) {
         fetchTaskDetails();
       } else {
         setSelectedTaskDetails(null);
       }
     }, [selectedTaskId, fetchTaskDetails]);
   
    const selectedTaskListItem = tasks.find(t => t.task_id === selectedTaskId);
    const selectedTask = selectedTaskDetails;

    const handleRefresh = useCallback(async () => {
      await loadTasks();
      if (selectedTaskId) {
        await fetchTaskDetails();
      }
    }, [loadTasks, fetchTaskDetails, selectedTaskId]);

    const getStats = () => {
      if (!selectedTask) return { high: 0, medium: 0, low: 0, avg: 0 };
      
      // Use overall_stats from API if available (accurate for whole task)
      if (selectedTask.overall_stats) {
        return {
          high: selectedTask.overall_stats.high,
          medium: selectedTask.overall_stats.medium,
          low: selectedTask.overall_stats.low,
          avg: selectedTask.overall_stats.avg_similarity
        };
      }
      
      // Fallback: compute from loaded results only (partial)
      if (!selectedTask.results) return { high: 0, medium: 0, low: 0, avg: 0 };
      
      const similarities = selectedTask.results.map((r: PlagiarismResult) => r.ast_similarity || 0);
      const high = similarities.filter(s => s >= 0.5).length;
      const medium = similarities.filter(s => s >= 0.25 && s < 0.5).length;
      const low = similarities.filter(s => s < 0.25).length;
      const avg = similarities.length > 0 
        ? similarities.reduce((a, b) => a + b, 0) / similarities.length 
        : 0;
      
      return { high, medium, low, avg };
    };
   
    const stats = getStats();
   
    const handleCompare = (result: PlagiarismResult) => {
     // Navigate to pair comparison page with the selected files
     navigate(`/dashboard/pair-comparison?file_a=${result.file_a.id}&file_b=${result.file_b.id}`);
   };

   // Color mode values
   const cardBg = useColorModeValue('white', 'gray.800');
   const borderColor = useColorModeValue('gray.200', 'gray.700');
   const hoverBg = useColorModeValue('gray.50', 'gray.700');
  
    if (loading) {
      return (
        <Box display="flex" justifyContent="center" alignItems="center" h="400px">
          <Spinner size="xl" color="blue.500" />
        </Box>
      );
    }
    
    if (error) {
     return (
       <Alert status="error">
         <AlertIcon />
         {error}
       </Alert>
     );
   }
   
   return (
     <Box display="flex" flexDirection="column" flex={1} minH={0} overflowY="auto">
       {tasks.length === 0 ? (
         <Card bg={cardBg}>
           <CardBody>
             <Text textAlign="center" color="gray.500" py={8}>
               {t('noChecks')}
             </Text>
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
                      isLoading={loading}
                    >
                      {t('common:refresh')}
                    </Button>
                 </HStack>

                 <HStack>
                   <Text fontWeight="semibold">{t('view')}:</Text>
                   <Select
                     value={viewMode}
                     onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setViewMode(e.target.value as 'cards' | 'heatmap')}
                     w="150px"
                   >
                     <option value="cards">{t('cards')}</option>
                      <option value="heatmap">{t('heatmap.title')}</option>
                   </Select>
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
            loading={loading}
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
                {viewMode === 'heatmap' && selectedTask.files.length > 1 ? (
                  <HeatmapView
                    selectedTask={selectedTask}
                    handleCompare={handleCompare}
                    cardBg={cardBg}
                  />
                ) : (
                  <ResultsList
                    results={selectedTask.results}
                    totalPairs={selectedTask.total_pairs}
                    borderColor={borderColor}
                    hoverBg={hoverBg}
                    getSimilarityColor={getSimilarityColor}
                    handleCompare={handleCompare}
                    cardBg={cardBg}
                  />
                )}
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