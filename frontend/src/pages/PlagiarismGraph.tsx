import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import {
  Box,
  Heading,
  Text,
  Card,
  CardBody,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  VStack,
  HStack,
  Badge,
  Select,
  Spinner,
  Alert,
  AlertIcon,
} from '@chakra-ui/react';
import api from '../services/api';

cytoscape.use(coseBilkent);

interface File {
  id: string;
  filename: string;
}

interface Match {
  file_a_start_line: number;
  file_a_end_line: number;
  file_b_start_line: number;
  file_b_end_line: number;
}

interface SimilarityResult {
  file_a: File;
  file_b: File;
  token_similarity: number;
  ast_similarity: number;
  matches: Match[];
  created_at: string;
}

interface Task {
  task_id: string;
  status: string;
  total_pairs: number;
  files: File[];
  results: SimilarityResult[];
}

const PlagiarismGraph: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.75);
  const [, setCy] = useState<cytoscape.Core | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasSetInitialTask, setHasSetInitialTask] = useState(false);

  // Fetch tasks and their results from API
  const fetchTasks = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/plagiarism/tasks');
      const taskList = response.data as Array<{ task_id: string; status: string }>;
      
      // Fetch detailed results for each task
      const tasksWithDetails = await Promise.all(
        taskList.map(async (task) => {
          try {
            const detailsResponse = await api.get(`/plagiarism/${task.task_id}/results`);
            return detailsResponse.data as Task;
          } catch (err) {
            console.error('Failed to fetch details for task %s', task.task_id, err);
            return null;
          }
        })
      );
      
      const validTasks = tasksWithDetails.filter((t): t is Task => t !== null);
      setTasks(validTasks);
      
      // Select the first completed task with results by default (only once)
      if (!hasSetInitialTask) {
        const completedTask = validTasks.find((t) => 
          t.status === 'completed' && t.results && t.results.length > 0
        );
        if (completedTask) {
          setSelectedTaskId(completedTask.task_id);
        } else if (validTasks.length > 0) {
          setSelectedTaskId(validTasks[0].task_id);
        }
        setHasSetInitialTask(true);
      }
    } catch (err) {
      setError('Failed to fetch plagiarism data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [hasSetInitialTask]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Get selected task data
  const selectedTask = tasks.find(t => t.task_id === selectedTaskId);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!selectedTask || !selectedTask.files) return;

    // Build nodes from files
    const nodes: cytoscape.ElementDefinition[] = selectedTask.files.map((file) => ({
      data: {
        id: file.id,
        label: file.filename,
        group: 'file',
      },
    }));

    // Build edges from similarity results
    const edges: cytoscape.ElementDefinition[] = selectedTask.results
      .filter((result) => (result.ast_similarity || 0) >= similarityThreshold)
      .map((result) => ({
        data: {
          source: result.file_a.id,
          target: result.file_b.id,
          similarity: result.ast_similarity || 0,
        },
      }));

    const elements: cytoscape.ElementDefinition[] = [...nodes, ...edges];

    const newCy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#4299e1',
            'label': 'data(label)',
            'width': 50,
            'height': 50,
            'font-size': '14px',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#fff',
            'text-outline-color': '#2b6cb0',
            'text-outline-width': 2,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 3,
            'line-color': '#718096',
            'target-arrow-color': '#718096',
            'curve-style': 'bezier',
            'label': (ele: cytoscape.EdgeSingular) => 
              `${(ele.data('similarity') * 100).toFixed(0)}%`,
            'font-size': '12px',
            'text-background-color': '#fff',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
          },
        },
        {
          selector: 'edge[similarity >= 0.8]',
          style: {
            'line-color': '#e53e3e',
            'target-arrow-color': '#e53e3e',
            'width': 4,
          },
        },
        {
          selector: 'edge[similarity >= 0.6][similarity < 0.8]',
          style: {
            'line-color': '#ecc94b',
            'target-arrow-color': '#ecc94b',
            'width': 3,
          },
        },
        {
          selector: 'edge[similarity < 0.6]',
          style: {
            'line-color': '#48bb78',
            'target-arrow-color': '#48bb78',
            'width': 2,
          },
        },
      ],
      layout: {
        name: 'cose-bilkent',
        padding: 10,
        nodeRepulsion: 4500,
        idealEdgeLength: 100,
        edgeElasticity: 0.45,
        nestingFactor: 0.1,
        gravity: 0.25,
        numIter: 2500,
        tile: true,
        tilingPaddingVertical: 10,
        tilingPaddingHorizontal: 10,
        gravityRangeCompound: 1.5,
        gravityCompound: 1.0,
        gravityRange: 3.8,
      } as cytoscape.LayoutOptions,
    });

    setCy(newCy);

    return () => {
      newCy.destroy();
    };
  }, [similarityThreshold, selectedTaskId, selectedTask]);

  // Filter out duplicate edges for display
  const filteredEdgesCount = selectedTask?.results.filter(
    (r) => (r.ast_similarity || 0) >= similarityThreshold
  ).length || 0;

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
      <Heading mb={6}>Plagiarism Network</Heading>

      {tasks.length === 0 ? (
        <Card>
          <CardBody>
            <Text textAlign="center" color="gray.500" py={8}>
              No plagiarism checks found. Upload files to get started!
            </Text>
          </CardBody>
        </Card>
      ) : (
        <>
          <Card mb={6}>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between" wrap="wrap" spacing={4}>
                  <HStack>
                    <Text fontWeight="semibold">Select Task:</Text>
                    <Select
                      value={selectedTaskId}
                      onChange={(e) => setSelectedTaskId(e.target.value)}
                      w="300px"
                    >
                      {tasks.map((task) => (
                        <option key={task.task_id} value={task.task_id}>
                          {task.task_id.substring(0, 8)}... ({task.status}) - {task.total_pairs} pairs
                        </option>
                      ))}
                    </Select>
                  </HStack>
                  <Badge colorScheme={selectedTask?.status === 'completed' ? 'green' : 'yellow'}>
                    {selectedTask?.status}
                  </Badge>
                </HStack>

                <Box borderTop="1px" borderColor="gray.200" pt={4}>
                  <HStack justify="space-between" mb={2}>
                    <Text fontWeight="semibold">Similarity Threshold</Text>
                    <Badge colorScheme="blue">{(similarityThreshold * 100).toFixed(0)}%</Badge>
                  </HStack>
                  <Slider
                    value={similarityThreshold}
                    onChange={setSimilarityThreshold}
                    min={0}
                    max={1}
                    step={0.05}
                  >
                    <SliderTrack>
                      <SliderFilledTrack />
                    </SliderTrack>
                    <SliderThumb />
                  </Slider>
                  <HStack justify="space-between" mt={2}>
                    <Text fontSize="sm" color="gray.500">
                      Only show connections with similarity score above the threshold
                    </Text>
                    <Text fontSize="sm" color="gray.500">
                      Showing {filteredEdgesCount} of {selectedTask?.total_pairs || 0} connections
                    </Text>
                  </HStack>
                </Box>

                <HStack spacing={4} fontSize="sm">
                  <HStack>
                    <Box w="3" h="3" bg="red.500" borderRadius="full" />
                    <Text>High (≥80%)</Text>
                  </HStack>
                  <HStack>
                    <Box w="3" h="3" bg="yellow.400" borderRadius="full" />
                    <Text>Medium (60-79%)</Text>
                  </HStack>
                  <HStack>
                    <Box w="3" h="3" bg="green.400" borderRadius="full" />
                    <Text>Low (&lt;60%)</Text>
                  </HStack>
                </HStack>
              </VStack>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Box
                ref={containerRef}
                height="600px"
                border="1px"
                borderColor="gray.200"
                borderRadius="md"
              />
            </CardBody>
          </Card>
        </>
      )}
    </Box>
  );
};

export default PlagiarismGraph;
