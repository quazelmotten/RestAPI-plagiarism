import React, { useState, useCallback, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Flex,
  HStack,
  VStack,
  Text,
  Spinner,
  Badge,
  Button,
  Select,
  IconButton,
  useColorModeValue,
  useToast,
  Progress,
  Icon,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  SimpleGrid,
  Card,
  CardBody,
  Stat,
  StatLabel,
  StatNumber,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  Input,
  InputGroup,
  InputLeftElement,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
} from '@chakra-ui/react';
import {
  FiChevronRight,
  FiUploadCloud,
  FiFolder,
  FiRefreshCw,
  FiAlertCircle,
  FiCheckCircle,
  FiActivity,
  FiClock,
  FiX,
  FiSearch,
  FiLayers,
  FiArrowRight,
} from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../../services/api';
import type { AssignmentFullResponse, PlagiarismResult, TaskListItem } from '../../types';
import TaskProgress from '../../components/Results/TaskProgress';
import SimilarityDistribution from '../../components/Results/SimilarityDistribution';
import HeatmapView from '../../components/Results/HeatmapView';
import PairComparisonModal from '../../components/PairComparisonModal';

const MAX_FILE_SIZE = 1 * 1024 * 1024;
const MAX_FILES = 1000;
const LANG_STORAGE_KEY = 'upload_last_language';

const getFileKey = (file: File): string => `${file.name}-${file.size}-${file.lastModified}`;

const formatFileSize = (bytes: number): string => {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
};

const getLastLanguage = (): string => {
  try { return localStorage.getItem(LANG_STORAGE_KEY) || 'python'; }
  catch { return 'python'; }
};

const languageOptions = [
  { value: 'python', key: 'python' },
  { value: 'javascript', key: 'javascript' },
  { value: 'typescript', key: 'typescript' },
  { value: 'cpp', key: 'cpp' },
  { value: 'c', key: 'c' },
  { value: 'java', key: 'java' },
  { value: 'go', key: 'go' },
  { value: 'rust', key: 'rust' },
];

const getSimilarityColor = (similarity: number) => {
  if (similarity >= 0.8) return 'red';
  if (similarity >= 0.5) return 'orange';
  if (similarity >= 0.3) return 'yellow';
  return 'green';
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed': return <FiCheckCircle color="#48bb78" />;
    case 'failed': return <FiAlertCircle color="#f56565" />;
    case 'storing_results': return <FiActivity color="#ed8936" />;
    case 'indexing': return <FiLayers color="#4299e1" />;
    case 'finding_intra_pairs': case 'finding_cross_pairs': return <FiLayers color="#805ad5" />;
    default: return <FiClock color="#a0aec0" />;
  }
};

const getStatusColorScheme = (status: string) => {
  switch (status) {
    case 'completed': return 'green';
    case 'failed': return 'red';
    case 'storing_results': return 'orange';
    case 'indexing': return 'blue';
    case 'finding_intra_pairs': case 'finding_cross_pairs': return 'purple';
    default: return 'gray';
  }
};

const ACTIVE_STATUSES = ['indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results'];

const AssignmentDetail: React.FC = () => {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const { t } = useTranslation(['upload', 'results', 'common', 'assignments', 'overview', 'status', 'languages']);
  const toast = useToast();

  // Upload state
  const [files, setFiles] = useState<File[]>([]);
  const [language, setLanguage] = useState(getLastLanguage);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Task filter state
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');

  // Results state
  const [resultsSearch, setResultsSearch] = useState('');
  const [similarityFilter, setSimilarityFilter] = useState<string>('all');

  // Pair comparison modal
  const [pairModalOpen, setPairModalOpen] = useState(false);
  const [selectedPair, setSelectedPair] = useState<{
    file_a: { id: string; filename: string };
    file_b: { id: string; filename: string };
    ast_similarity: number;
  } | null>(null);

  // Fetch full assignment data
  const fetchAssignmentFull = useCallback(async (): Promise<AssignmentFullResponse> => {
    const params: Record<string, string> = {};
    if (selectedTaskId) params.task_id = selectedTaskId;
    const res = await api.get<AssignmentFullResponse>(API_ENDPOINTS.ASSIGNMENT_FULL(assignmentId!), { params });
    return res.data;
  }, [assignmentId, selectedTaskId]);

  const { data: assignmentData, isLoading, refetch } = useQuery<AssignmentFullResponse>({
    queryKey: ['assignmentFull', assignmentId, selectedTaskId],
    queryFn: fetchAssignmentFull,
    enabled: !!assignmentId,
  });

  // Find any active (processing) task
  const activeTask = assignmentData?.tasks.find(t => ACTIVE_STATUSES.includes(t.status));
  const isProcessing = !!activeTask;

  // Refresh after upload
  const refreshData = useCallback(() => {
    refetch();
  }, [refetch]);

  // Upload handler
  const onDrop = useCallback(
    (acceptedFiles: File[], rejected: { file: File }[]) => {
      if (rejected.length > 0) {
        toast({ title: `${rejected.length} ${t('rejected')}`, status: 'warning', duration: 4000 });
      }
      setFiles((prev) => {
        const existingKeys = new Set(prev.map(getFileKey));
        const newFiles: File[] = [];
        let duplicateCount = 0;
        for (const file of acceptedFiles) {
          const key = getFileKey(file);
          if (existingKeys.has(key)) { duplicateCount++; continue; }
          if (prev.length + newFiles.length >= MAX_FILES) break;
          newFiles.push(file);
          existingKeys.add(key);
        }
        if (duplicateCount > 0) {
          toast({ title: `${duplicateCount} ${t('duplicateSkipped')}`, status: 'info', duration: 3000 });
        }
        return [...prev, ...newFiles];
      });
    },
    [toast, t]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/plain': ['.txt', '.py', '.js', '.ts', '.cpp', '.c', '.java', '.go', '.rs'] },
    multiple: true,
    maxSize: MAX_FILE_SIZE,
  });

  const handleUpload = async () => {
    if (files.length === 0) {
      toast({ title: t('toasts.noFilesSelected'), status: 'warning', duration: 3000 });
      return;
    }
    setIsUploading(true);
    setUploadProgress(0);
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));
      formData.append('language', language);
      if (assignmentId) formData.append('assignment_id', assignmentId);

      await api.post(API_ENDPOINTS.CHECK, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          setUploadProgress(Math.round((e.loaded / (e.total || 1)) * 100));
        },
      });

      toast({ title: t('toasts.success'), status: 'success', duration: 3000 });
      setFiles([]);
      setTimeout(refreshData, 2000);
    } catch (err: unknown) {
      let msg = t('common:error');
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string; message?: string } } };
        msg = axiosErr.response?.data?.detail || axiosErr.response?.data?.message || msg;
      }
      toast({ title: t('toasts.failed'), description: msg, status: 'error', duration: 6000 });
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  // Filtered results
  const filteredResults = (() => {
    if (!assignmentData?.results) return [];
    let results = [...assignmentData.results];
    if (similarityFilter === 'high') results = results.filter(r => (r.ast_similarity || 0) >= 0.8);
    else if (similarityFilter === 'medium') results = results.filter(r => (r.ast_similarity || 0) >= 0.5 && (r.ast_similarity || 0) < 0.8);
    else if (similarityFilter === 'low') results = results.filter(r => (r.ast_similarity || 0) < 0.5);
    if (resultsSearch.trim()) {
      const q = resultsSearch.toLowerCase();
      results = results.filter(r =>
        r.file_a.filename.toLowerCase().includes(q) || r.file_b.filename.toLowerCase().includes(q)
      );
    }
    return results;
  })();

  // Stats from aggregated data
  const stats = (() => {
    if (!assignmentData?.overall_stats) return { high: 0, medium: 0, low: 0, avg: 0 };
    return {
      high: assignmentData.overall_stats.high,
      medium: assignmentData.overall_stats.medium,
      low: assignmentData.overall_stats.low,
      avg: assignmentData.overall_stats.avg_similarity,
    };
  })();

  const handleCompare = useCallback((result: PlagiarismResult) => {
    setSelectedPair({ file_a: result.file_a, file_b: result.file_b, ast_similarity: result.ast_similarity });
    setPairModalOpen(true);
  }, []);

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  // Colors
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const subtleBg = useColorModeValue('gray.50', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');
  const dropzoneHoverBg = useColorModeValue('brand.50', 'gray.600');
  const breadcrumbColor = useColorModeValue('gray.500', 'gray.400');
  const taskRowBg = useColorModeValue('gray.50', 'gray.700');

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" h="400px">
        <Spinner size="xl" color="blue.500" />
      </Box>
    );
  }

  if (!assignmentData) {
    return (
      <Box textAlign="center" py={12}>
        <Text fontSize="lg" color="red.500">Assignment not found</Text>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden" position="relative">
      {/* Breadcrumb */}
      <Breadcrumb spacing={1} separator={<FiChevronRight color={breadcrumbColor} />} mb={4} flexShrink={0}>
        <BreadcrumbItem>
          <BreadcrumbLink as={Link} to="/dashboard/assignments" fontSize="sm" color={breadcrumbColor}>
            {t('assignments:title')}
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem isCurrentPage>
          <Text fontSize="sm" fontWeight="semibold">{assignmentData.name}</Text>
        </BreadcrumbItem>
      </Breadcrumb>

      {/* Header */}
      <Flex justify="space-between" align="flex-start" mb={4} flexShrink={0} wrap="wrap" gap={3}>
        <Box>
          <HStack spacing={3} align="center">
            <Text fontSize="2xl" fontWeight="bold">{assignmentData.name}</Text>
            <Badge colorScheme="blue" fontSize="sm">{assignmentData.files_count} {t('common:files')}</Badge>
            <Badge colorScheme="purple" fontSize="sm">{assignmentData.tasks_count} {t('assignments:table.tasks') || 'tasks'}</Badge>
          </HStack>
          {assignmentData.description && (
            <Text fontSize="sm" color={mutedColor} mt={1}>{assignmentData.description}</Text>
          )}
        </Box>
        <HStack>
          {isProcessing && activeTask && (
            <HStack>
              {getStatusIcon(activeTask.status)}
              <Badge colorScheme={getStatusColorScheme(activeTask.status)}>
                {t(`status:${activeTask.status}`)}
              </Badge>
            </HStack>
          )}
          <Button size="sm" leftIcon={<FiRefreshCw />} onClick={refreshData} isLoading={isLoading}>
            {t('common:refresh')}
          </Button>
        </HStack>
      </Flex>

      {/* Upload section */}
      <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} p={4} mb={4} flexShrink={0}>
        <Flex direction={{ base: 'column', md: 'row' }} gap={4} align="flex-start">
          <HStack spacing={4} flexShrink={0}>
            <Box>
              <Text fontSize="xs" color={mutedColor} mb={1}>{t('language')}</Text>
              <Select
                value={language}
                onChange={(e) => { setLanguage(e.target.value); localStorage.setItem(LANG_STORAGE_KEY, e.target.value); }}
                size="sm"
                maxW="140px"
              >
                {languageOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{t(`languages:${opt.key}`)}</option>
                ))}
              </Select>
            </Box>
          </HStack>

          <Box
            {...getRootProps()}
            border="2px dashed"
            borderColor={isDragActive ? 'brand.500' : borderColor}
            borderRadius="lg"
            p={3}
            flex={1}
            w="100%"
            display="flex"
            alignItems="center"
            justifyContent="center"
            textAlign="center"
            cursor="pointer"
            bg={isDragActive ? dropzoneHoverBg : subtleBg}
            transition="all 0.2s"
            minH="60px"
            _hover={{ borderColor: 'brand.400', bg: dropzoneHoverBg }}
          >
            <input {...getInputProps()} />
            <HStack spacing={3}>
              <Icon as={FiUploadCloud} boxSize={5} color="brand.400" />
              <Text fontSize="sm" fontWeight="medium">
                {files.length > 0
                  ? `${files.length} file(s) (${formatFileSize(totalSize)})`
                  : t('dragAndDrop')
                }
              </Text>
            </HStack>
          </Box>

          {files.length > 0 && (
            <HStack flexShrink={0}>
              {isUploading && (
                <Box w="150px">
                  <Progress value={uploadProgress} size="sm" colorScheme="brand" borderRadius="full" hasStripe isAnimated />
                  <Text fontSize="xs" textAlign="center" mt={1}>{uploadProgress}%</Text>
                </Box>
              )}
              <Button
                colorScheme="brand"
                size="sm"
                onClick={handleUpload}
                isLoading={isUploading}
                loadingText={t('uploading')}
                leftIcon={<FiCheckCircle />}
              >
                {t('upload', { count: files.length, size: formatFileSize(totalSize) })}
              </Button>
              <IconButton
                aria-label="Clear files"
                icon={<FiX />}
                size="sm"
                variant="ghost"
                colorScheme="red"
                onClick={() => setFiles([])}
                isDisabled={isUploading}
              />
            </HStack>
          )}
        </Flex>
      </Box>

      {/* Tasks summary */}
      {assignmentData.tasks.length > 0 && (
        <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} p={4} mb={4} flexShrink={0}>
          <Flex justify="space-between" align="center" mb={3}>
            <Text fontSize="sm" fontWeight="semibold">Tasks ({assignmentData.tasks.length})</Text>
            <HStack>
              <Text fontSize="xs" color={mutedColor}>Filter by task:</Text>
              <Select
                size="xs"
                w="200px"
                value={selectedTaskId}
                onChange={(e) => setSelectedTaskId(e.target.value)}
              >
                <option value="">All tasks</option>
                {assignmentData.tasks.map((task) => (
                  <option key={task.task_id} value={task.task_id}>
                    {task.task_id.substring(0, 8)}... ({task.status})
                  </option>
                ))}
              </Select>
            </HStack>
          </Flex>
          <Box overflowX="auto">
            <Table size="xs" variant="simple">
              <Thead>
                <Tr>
                  <Th fontSize="xs">Task ID</Th>
                  <Th fontSize="xs">Status</Th>
                  <Th fontSize="xs" isNumeric>Files</Th>
                  <Th fontSize="xs" isNumeric>Pairs</Th>
                </Tr>
              </Thead>
              <Tbody>
                {assignmentData.tasks.map((task) => (
                  <Tr
                    key={task.task_id}
                    bg={selectedTaskId === task.task_id ? taskRowBg : undefined}
                    cursor="pointer"
                    onClick={() => setSelectedTaskId(selectedTaskId === task.task_id ? '' : task.task_id)}
                    _hover={{ bg: hoverBg }}
                  >
                    <Td fontSize="xs" fontFamily="monospace">{task.task_id.substring(0, 12)}...</Td>
                    <Td>
                      <HStack spacing={1}>
                        {getStatusIcon(task.status)}
                        <Badge colorScheme={getStatusColorScheme(task.status)} fontSize="xs">
                          {task.status}
                        </Badge>
                      </HStack>
                    </Td>
                    <Td fontSize="xs" isNumeric>{task.files_count ?? '-'}</Td>
                    <Td fontSize="xs" isNumeric>{task.total_pairs ?? 0}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        </Box>
      )}

      {/* Task progress - shown when actively processing */}
      {activeTask && (
        <Box mb={4} flexShrink={0}>
          <TaskProgress
            taskId={activeTask.task_id}
            status={activeTask.status}
            cardBg={cardBg}
            onCompleted={refreshData}
          />
        </Box>
      )}

      {/* Results */}
      {assignmentData.results.length > 0 || assignmentData.total_pairs > 0 ? (
        <Box flex={1} minH={0} display="flex" flexDirection="column" overflow="hidden">
          <Box flex={1} minH={0} display="flex" flexDirection="column" overflow="hidden">
            <Tabs variant="enclosed" display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
              <TabList flexShrink={0}>
                <Tab fontSize="sm">{t('results:resultsList.topSimilarities')}</Tab>
                <Tab fontSize="sm">{t('results:distribution.title')}</Tab>
                <Tab fontSize="sm">{t('results:heatmap.title')}</Tab>
              </TabList>

              <TabPanels flex={1} display="flex" flexDirection="column" minH={0} overflow="hidden">
                {/* Top Similarities */}
                <TabPanel flex={1} display="flex" flexDirection="column" minH={0} overflow="hidden" p={0} pt={4}>
                  <VStack align="stretch" spacing={3} flexShrink={0}>
                    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3}>
                      <Card bg={cardBg} size="sm"><CardBody py={3}>
                        <Stat size="sm"><StatLabel fontSize="xs">{t('results:taskStats.files')}</StatLabel>
                          <StatNumber fontSize="lg">{assignmentData.files.length}</StatNumber></Stat>
                      </CardBody></Card>
                      <Card bg={cardBg} size="sm"><CardBody py={3}>
                        <Stat size="sm"><StatLabel fontSize="xs">{t('results:taskStats.comparisons')}</StatLabel>
                          <StatNumber fontSize="lg">{assignmentData.total_pairs}</StatNumber></Stat>
                      </CardBody></Card>
                      <Card bg={cardBg} size="sm"><CardBody py={3}>
                        <Stat size="sm"><StatLabel fontSize="xs">{t('overview:highSimilarity')}</StatLabel>
                          <StatNumber fontSize="lg" color="red.500">{stats.high}</StatNumber></Stat>
                      </CardBody></Card>
                      <Card bg={cardBg} size="sm"><CardBody py={3}>
                        <Stat size="sm"><StatLabel fontSize="xs">{t('results:taskStats.avgSimilarity')}</StatLabel>
                          <StatNumber fontSize="lg" color={getSimilarityColor(stats.avg)}>
                            {(stats.avg * 100).toFixed(1)}%
                          </StatNumber></Stat>
                      </CardBody></Card>
                    </SimpleGrid>

                    <HStack>
                      <InputGroup size="sm" maxW="300px">
                        <InputLeftElement pointerEvents="none">
                          <Icon as={FiSearch} color={mutedColor} />
                        </InputLeftElement>
                        <Input placeholder={t('results:taskPicker.search')} value={resultsSearch} onChange={(e) => setResultsSearch(e.target.value)} />
                      </InputGroup>
                      <Select size="sm" w="160px" value={similarityFilter} onChange={(e) => setSimilarityFilter(e.target.value)}>
                        <option value="all">{t('common:all')}</option>
                        <option value="high">High (&ge;80%)</option>
                        <option value="medium">Medium (50-80%)</option>
                        <option value="low">Low (&lt;50%)</option>
                      </Select>
                      <Text fontSize="sm" color={mutedColor}>
                        {filteredResults.length} of {assignmentData.total_pairs}
                      </Text>
                    </HStack>
                  </VStack>

                  <Box flex={1} minH={0} overflowY="auto" mt={3}>
                    <TableContainer>
                      <Table variant="simple" size="sm">
                        <Thead position="sticky" top={0} bg={cardBg} zIndex={1}>
                          <Tr>
                            <Th>{t('results:resultsList.topSimilarities')}</Th>
                            <Th isNumeric>Similarity</Th>
                            <Th w="100px"></Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {filteredResults.map((result, idx) => (
                            <Tr key={idx} _hover={{ bg: hoverBg }}>
                              <Td>
                                <HStack spacing={2}>
                                  <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="220px">
                                    {result.file_a.filename}
                                  </Text>
                                  <Text fontSize="xs" color={mutedColor}>vs</Text>
                                  <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="220px">
                                    {result.file_b.filename}
                                  </Text>
                                </HStack>
                              </Td>
                              <Td isNumeric>
                                <Badge colorScheme={getSimilarityColor(result.ast_similarity || 0)} fontSize="sm" px={2} py={0.5}>
                                  {((result.ast_similarity || 0) * 100).toFixed(1)}%
                                </Badge>
                              </Td>
                              <Td>
                                <Button size="xs" rightIcon={<FiArrowRight />} variant="outline" colorScheme={getSimilarityColor(result.ast_similarity || 0)} onClick={() => handleCompare(result)}>
                                  Review
                                </Button>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </TableContainer>

                    {filteredResults.length === 0 && (
                      <Box textAlign="center" py={8} color={mutedColor}>
                        <Text>{assignmentData.total_pairs === 0 ? t('results:noChecks') : t('results:taskPicker.noMatches')}</Text>
                      </Box>
                    )}
                  </Box>
                </TabPanel>

                {/* Distribution */}
                <TabPanel flex={1} display="flex" flexDirection="column" minH={0} overflowY="auto" p={0} pt={4}>
                  <SimilarityDistribution
                    results={assignmentData.results}
                    totalPairs={assignmentData.total_pairs}
                    cardBg={cardBg}
                    taskId={selectedTaskId || undefined}
                    stats={stats}
                  />
                </TabPanel>

                {/* Heatmap */}
                <TabPanel flex={1} display="flex" flexDirection="column" minH={0} overflowY="auto" p={0} pt={4}>
                  <HeatmapView
                    selectedTask={{
                      task_id: selectedTaskId || assignmentData.id,
                      status: 'completed',
                      total_pairs: assignmentData.total_pairs,
                      files: assignmentData.files.map(f => ({ id: f.id, filename: f.filename, task_id: f.task_id || undefined })),
                      results: assignmentData.results,
                      overall_stats: assignmentData.overall_stats || undefined,
                    }}
                    handleCompare={handleCompare}
                    cardBg={cardBg}
                  />
                </TabPanel>
              </TabPanels>
            </Tabs>
          </Box>
        </Box>
      ) : (
        <Flex flex={1} align="center" justify="center" direction="column" color={mutedColor} py={12}>
          <Icon as={FiFolder} boxSize={10} mb={3} />
          <Text fontWeight="medium">{t('results:noChecks')}</Text>
          <Text fontSize="sm" mt={1}>Upload files above to start analysis</Text>
        </Flex>
      )}

      <PairComparisonModal
        isOpen={pairModalOpen}
        onClose={() => { setPairModalOpen(false); setSelectedPair(null); }}
        initialFileA={selectedPair?.file_a}
        initialFileB={selectedPair?.file_b}
        assignmentName={assignmentData.name}
      />
    </Box>
  );
};

export default AssignmentDetail;
