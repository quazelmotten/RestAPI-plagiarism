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
  Skeleton,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import type { TaskListItem, TaskDetails, PlagiarismResult } from '../types';
import { useGraphTasks, useGraphTaskDetails } from '../hooks/useGraphQueries';
type Task = TaskDetails;

cytoscape.use(coseBilkent);

const PlagiarismGraph: React.FC = () => {
  const { t } = useTranslation(['graph', 'common', 'status', 'results']);
  const containerRef = useRef<HTMLDivElement>(null);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.75);
  const [, setCy] = useState<cytoscape.Core | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: tasksData, isLoading: loadingTasks } = useGraphTasks();
  const tasks = tasksData?.items ?? [];

  const [selectedTaskId, setSelectedTaskId] = useState<string>(() => {
    const completedTask = tasks.find((t: TaskListItem) => t.status === 'completed' && t.total_pairs > 0);
    return completedTask?.task_id || tasks[0]?.task_id || '';
  });

  const { data: selectedTaskDetails, isLoading: loadingDetails } = useGraphTaskDetails(selectedTaskId || undefined, 500);

  useEffect(() => {
    if (tasks.length > 0 && !selectedTaskId) {
      const completedTask = tasks.find((t: TaskListItem) => t.status === 'completed' && t.total_pairs > 0);
      setSelectedTaskId(completedTask?.task_id || tasks[0].task_id);
    }
  }, [tasks, selectedTaskId]);

  const selectedTask = selectedTaskDetails;

  useEffect(() => {
    if (!containerRef.current) return;
    if (!selectedTask || !selectedTask.files) return;

    const nodes: cytoscape.ElementDefinition[] = selectedTask.files.map((file: { id: string; filename: string; task_id?: string }) => ({
      data: {
        id: file.id,
        label: file.filename,
        group: 'file',
      },
    }));

    const validFileIds = new Set(selectedTask.files.map((file: { id: string; filename: string; task_id?: string }) => file.id));

    const edges: cytoscape.ElementDefinition[] = selectedTask.results
      .filter((result: PlagiarismResult) => {
        const sourceExists = validFileIds.has(result.file_a.id);
        const targetExists = validFileIds.has(result.file_b.id);
        const meetsThreshold = (result.ast_similarity || 0) >= similarityThreshold;
        return sourceExists && targetExists && meetsThreshold;
      })
      .map((result: PlagiarismResult) => ({
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
            'label': (ele: cytoscape.EdgeSingular) => `${(ele.data('similarity') * 100).toFixed(0)}%`,
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

  const filteredEdgesCount = selectedTask?.results.filter(
    (r: PlagiarismResult) => (r.ast_similarity || 0) >= similarityThreshold
  ).length || 0;

  if (loadingTasks) {
    return (
      <Box>
        <Card mb={6}>
          <CardBody>
            <Skeleton height="40px" />
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <Skeleton height="600px" />
          </CardBody>
        </Card>
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
      {tasks.length === 0 ? (
        <Card>
          <CardBody>
            <Text textAlign="center" color="gray.500" py={8}>
              {t('empty.noChecks')}
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
                    <Text fontWeight="semibold">{t('selectTask')}</Text>
                    <Select
                      value={selectedTaskId}
                      onChange={(e) => setSelectedTaskId(e.target.value)}
                      w="300px"
                    >
                      {tasks.map((task: TaskListItem) => {
                        const shortId = task.task_id.substring(0, 8);
                        return (
                          <option key={task.task_id} value={task.task_id}>
                            {t('taskOption', { 
                              id: shortId, 
                              status: t(`status:${task.status}`), 
                              count: task.total_pairs 
                            })}
                          </option>
                        );
                      })}
                    </Select>
                  </HStack>
                  {selectedTask && (
                    <Badge colorScheme={selectedTask.status === 'completed' ? 'green' : 'yellow'}>
                      {t(`status:${selectedTask.status}`)}
                    </Badge>
                  )}
                </HStack>

                {loadingDetails && (
                  <Box textAlign="center" py={2}>
                    <Spinner size="sm" />
                     <Text fontSize="sm" ml={2}>{t('loading')}</Text>
                  </Box>
                )}

                {!loadingDetails && selectedTaskDetails && (
                  <Box borderTop="1px" borderColor="gray.200" pt={4}>
                    <HStack justify="space-between" mb={2}>
                       <Text fontWeight="semibold">{t('similarityThreshold')}</Text>
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
                         {t('thresholdDescription')}
                       </Text>
                       <Text fontSize="sm" color="gray.500">
                         {t('showing', { count: filteredEdgesCount, total: selectedTask?.total_pairs ?? 0 })}
                       </Text>
                    </HStack>
                  </Box>
                )}


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
