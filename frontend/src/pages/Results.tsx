import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Heading,
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
  useColorModeValue,
} from '@chakra-ui/react';
import { 
  FiCheckCircle, 
  FiAlertCircle, 
  FiActivity,
  FiLayers,
  FiRefreshCw
} from 'react-icons/fi';
import { useNavigate } from 'react-router';
import api, { API_ENDPOINTS } from '../services/api';
import type { TaskListItem, TaskDetails, PlagiarismResult } from '../types';
import TaskStats from '../components/Results/TaskStats';
import TaskProgress from '../components/Results/TaskProgress';
import SimilarityDistribution from '../components/Results/SimilarityDistribution';
import HeatmapView from '../components/Results/HeatmapView';
import ResultsList from '../components/Results/ResultsList';
import ErrorBoundary from '../components/ErrorBoundary';

const getSimilarityColor = (similarity: number) => {
  if (similarity >= 0.8) return 'red';
  if (similarity >= 0.5) return 'orange';
  if (similarity >= 0.3) return 'yellow';
  return 'green';
};

const getSimilarityGradient = (similarity: number) => {
  if (similarity >= 0.8) return 'linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%)';
  if (similarity >= 0.5) return 'linear-gradient(135deg, #ffa726 0%, #fb8c00 100%)';
  if (similarity >= 0.3) return 'linear-gradient(135deg, #ffca28 0%, #ffb300 100%)';
  return 'linear-gradient(135deg, #66bb6a 0%, #4caf50 100%)';
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <FiCheckCircle color="#48bb78" />;
    case 'failed':
      return <FiAlertCircle color="#f56565" />;
    case 'processing':
      return <FiActivity color="#ed8936" />;
    default:
      return <FiLayers color="#a0aec0" />;
  }
};

const Results: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'cards' | 'heatmap'>('cards');
  const [selectedTaskDetails, setSelectedTaskDetails] = useState<TaskDetails | null>(null);
  const [loadingTaskDetails, setLoadingTaskDetails] = useState(false);
  const [loadingMoreResults, setLoadingMoreResults] = useState(false);
  
  // Use a ref to capture the initial selectedTaskId to avoid triggering re-fetch
  const initialSelectedTaskIdRef = useRef(selectedTaskId);
  
   const loadTasks = useCallback(async () => {
     try {
       setLoading(true);
       const response = await api.get<TaskListItem[]>(API_ENDPOINTS.TASKS);
       const taskList = response.data;

       if (!Array.isArray(taskList)) {
         console.error('Expected array from /plagiarism/tasks, got:', typeof taskList, taskList);
         setError('Invalid data format received from server');
         setTasks([]);
         return;
       }

       setTasks(taskList);

       if (taskList.length > 0 && !initialSelectedTaskIdRef.current) {
         setSelectedTaskId(taskList[0].task_id);
       }
     } catch (err) {
       setError('Failed to fetch plagiarism tasks');
       console.error(err);
     } finally {
       setLoading(false);
     }
   }, []);

   useEffect(() => {
     loadTasks();
   }, [loadTasks]);
  
    const fetchTaskDetails = useCallback(async (offset: number, isLoadMore: boolean = false) => {
      if (!selectedTaskId) return;
      try {
        if (!isLoadMore) {
          setLoadingTaskDetails(true);
          setSelectedTaskDetails(null);
        } else {
          setLoadingMoreResults(true);
        }
        
        const response = await api.get<TaskDetails>(API_ENDPOINTS.TASK_DETAILS(selectedTaskId), {
          params: {
            limit: 50,
            offset
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

       if (offset === 0) {
          setSelectedTaskDetails(taskDetails);
        } else {
          setSelectedTaskDetails((prev: TaskDetails | null) => prev ? { ...prev, results: [...prev.results, ...data.results] } : null);
        }
     } catch (err) {
       console.error('Failed to fetch task details:', err);
     } finally {
       if (!isLoadMore) {
         setLoadingTaskDetails(false);
       } else {
         setLoadingMoreResults(false);
       }
     }
   }, [selectedTaskId]);

   useEffect(() => {
     if (selectedTaskId) {
       fetchTaskDetails(0);
     } else {
       setSelectedTaskDetails(null);
     }
   }, [selectedTaskId, fetchTaskDetails]);
  
  const selectedTaskListItem = tasks.find(t => t.task_id === selectedTaskId);
  const selectedTask = selectedTaskDetails;

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
     const high = similarities.filter(s => s >= 0.8).length;
     const medium = similarities.filter(s => s >= 0.5 && s < 0.8).length;
     const low = similarities.filter(s => s < 0.5).length;
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
    <Box>
      <Heading mb={6}>Plagiarism Results</Heading>
      
      {tasks.length === 0 ? (
        <Card bg={cardBg}>
          <CardBody>
            <Text textAlign="center" color="gray.500" py={8}>
              No plagiarism checks found. Upload files to get started!
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
                  <Text fontWeight="semibold">Select Task:</Text>
                  <Select
                    value={selectedTaskId}
                    onChange={(e) => setSelectedTaskId(e.target.value)}
                    w="400px"
                  >
                    {tasks.map((task) => (
                      <option key={task.task_id} value={task.task_id}>
                        {task.task_id.substring(0, 8)}... ({task.status}) - {task.progress?.display || `${task.total_pairs} pairs`}
                      </option>
                    ))}
                  </Select>
                  {selectedTaskListItem?.status === 'processing' && (
                    <Spinner size="sm" color="orange.500" speed="0.8s" />
                  )}
                  <Button
                    size="sm"
                    leftIcon={<FiRefreshCw />}
                    onClick={loadTasks}
                    isLoading={loading}
                  >
                    Refresh
                  </Button>
                </HStack>
                
                <HStack>
                  <Text fontWeight="semibold">View:</Text>
                  <Select
                    value={viewMode}
                    onChange={(e) => setViewMode(e.target.value as 'cards' | 'heatmap')}
                    w="150px"
                  >
                    <option value="cards">Cards</option>
                    <option value="heatmap">Heatmap</option>
                  </Select>
                </HStack>
              </HStack>
            </CardBody>
          </Card>
          
           {selectedTask ? (
              <ErrorBoundary>
                <TaskStats
                  selectedTask={selectedTask}
                  avgSimilarity={stats.avg}
                  getSimilarityColor={getSimilarityColor}
                  getStatusIcon={getStatusIcon}
                  cardBg={cardBg}
                />
                
                <TaskProgress selectedTask={selectedTask} cardBg={cardBg} />
                
                <SimilarityDistribution
                  totalPairs={selectedTask.total_pairs}
                  stats={stats}
                  cardBg={cardBg}
                />
                
                {/* Results View */}
                {viewMode === 'heatmap' && selectedTask.files.length > 1 ? (
                  <HeatmapView
                    selectedTask={selectedTask}
                    getSimilarityGradient={getSimilarityGradient}
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
                    loadingMoreResults={loadingMoreResults}
                    onLoadMore={() => fetchTaskDetails(selectedTask.results.length, true)}
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