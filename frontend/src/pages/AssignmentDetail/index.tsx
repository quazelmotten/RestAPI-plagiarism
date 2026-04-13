import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Flex,
  HStack,
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
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  InputGroup,
  InputLeftElement,
  Input,
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
  FiEye,
  FiFileText,
  FiChevronDown,
  FiChevronUp,
  FiChevronLeft,
  FiList,
} from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../../services/api';
import type { AssignmentFullResponse, PlagiarismResult, AssignmentFullFile } from '../../types';
import { getSimilarityColor, getStatusColorScheme } from '../../utils/statusColors';
import TaskProgress from '../../components/Results/TaskProgress';
import SimilarityDistribution from '../../components/Results/SimilarityDistribution';
import PairComparisonModal from '../../components/PairComparisonModal';
import ReviewQueue from '../../components/Review/ReviewQueue';

const MAX_FILE_SIZE = 1 * 1024 * 1024;
const MAX_FILES = 1000;
const LANG_STORAGE_KEY = 'upload_last_language';
const PAIRS_PER_PAGE = 20;

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

  // Task state
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [collapsed, setCollapsed] = useState(false);

  // Tab state
  const [activeTab, setActiveTab] = useState(0);

  // Results pagination & filters (search/filter are client-side on current page)
  const [resultsSearch, setResultsSearch] = useState('');
  const [similarityFilter, setSimilarityFilter] = useState<string>('all');
  const [pairsPage, setPairsPage] = useState(0);
  const [pairsGoPage, setPairsGoPage] = useState('');

  // Files tab
  const [filesPage, setFilesPage] = useState(0);
  const [filesGoPage, setFilesGoPage] = useState('');
  const FILES_PER_PAGE = 50;
  const [fileFilterName, setFileFilterName] = useState('');
  const [fileFilterTask, setFileFilterTask] = useState('');
  const [fileSortCol, setFileSortCol] = useState<'filename' | 'task_id' | 'max_similarity'>('filename');
  const [fileSortDir, setFileSortDir] = useState<'asc' | 'desc'>('asc');
  const [colWidths, setColWidths] = useState({ filename: 300, task: 120, maxSim: 120 });
  const [resizingCol, setResizingCol] = useState<string | null>(null);
  const [resizeStartX, setResizeStartX] = useState(0);
  const [resizeStartW, setResizeStartW] = useState(0);

  // Pair comparison
  const [pairModalOpen, setPairModalOpen] = useState(false);
  const [selectedPair, setSelectedPair] = useState<{
    file_a: { id: string; filename: string };
    file_b: { id: string; filename: string };
    ast_similarity: number;
  } | null>(null);
  const [reviewQueuePairs, setReviewQueuePairs] = useState<PlagiarismResult[]>([]);

  // File viewer
  const { isOpen: isFileViewerOpen, onOpen: onFileViewerOpen, onClose: onFileViewerClose } = useDisclosure();
  const [viewingFile, setViewingFile] = useState<{ id: string; filename: string } | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [loadingFileContent, setLoadingFileContent] = useState(false);

  // Fetch full assignment data (server-side paginated results and files)
const { data: assignmentData, isLoading, refetch, isFetching, error: queryError } = useQuery<AssignmentFullResponse>({
    queryKey: ['assignmentFull', assignmentId, selectedTaskId, pairsPage, filesPage],
    retry: 0,
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (selectedTaskId) params.task_id = selectedTaskId;
      params.limit = String(PAIRS_PER_PAGE);
      params.offset = String(pairsPage * PAIRS_PER_PAGE);
      params.file_limit = String(FILES_PER_PAGE);
      params.file_offset = String(filesPage * FILES_PER_PAGE);
      try {
        const res = await api.get<AssignmentFullResponse>(API_ENDPOINTS.ASSIGNMENT_FULL(assignmentId!), { params });
        return res.data;
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { error_details?: string } } };
        const msg = axiosErr.response?.data?.error_details || 'No access to this assignment';
        throw new Error(msg);
      }
    },
    enabled: !!assignmentId,
  });

  useEffect(() => {
    if (queryError) {
      const msg = queryError instanceof Error ? queryError.message : 'No access to this assignment';
      toast({ title: t('common:error'), description: msg, status: 'error', duration: 5000 });
    }
  }, [queryError, toast, t]);

  // Files are server-paginated, with client-side filter/sort on the current page
  const displayedFiles = useMemo((): AssignmentFullFile[] => {
    const files = assignmentData?.files ?? [];
    let result = [...files];
    if (fileFilterName.trim()) {
      const q = fileFilterName.toLowerCase();
      result = result.filter(f => f.filename.toLowerCase().includes(q));
    }
    if (fileFilterTask) result = result.filter(f => f.task_id === fileFilterTask);
    result.sort((a, b) => {
      if (fileSortCol === 'max_similarity') {
        const aVal = a.max_similarity ?? 0;
        const bVal = b.max_similarity ?? 0;
        return fileSortDir === 'asc' ? aVal - bVal : bVal - aVal;
      }
      const aVal = (a[fileSortCol] || '') as string;
      const bVal = (b[fileSortCol] || '') as string;
      const cmp = aVal.localeCompare(bVal);
      return fileSortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [assignmentData?.files, fileFilterName, fileFilterTask, fileSortCol, fileSortDir]);

  const totalFiles = assignmentData?.total_files ?? 0;
  const totalFilePages = Math.max(1, Math.ceil(totalFiles / FILES_PER_PAGE));

  const handleFileSort = (col: 'filename' | 'task_id' | 'max_similarity') => {
    if (fileSortCol === col) setFileSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setFileSortCol(col); setFileSortDir('asc'); }
  };

  const handlePairsGoToPage = () => {
    const pageNum = parseInt(pairsGoPage, 10);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      setPairsPage(pageNum - 1);
      setPairsGoPage('');
    }
  };

  const handleFilesGoToPage = () => {
    const pageNum = parseInt(filesGoPage, 10);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalFilePages) {
      setFilesPage(pageNum - 1);
      setFilesGoPage('');
    }
  };

  const activeTask = assignmentData?.tasks.find(t => ACTIVE_STATUSES.includes(t.status));
  const isProcessing = !!activeTask;
  const refreshData = useCallback(() => refetch(), [refetch]);

  // Column resize
  const handleResizeStart = useCallback((col: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setResizingCol(col);
    setResizeStartX(e.clientX);
    setResizeStartW(colWidths[col as keyof typeof colWidths]);
  }, [colWidths]);

  React.useEffect(() => {
    if (!resizingCol) return;
    const handleMove = (e: MouseEvent) => {
      const diff = e.clientX - resizeStartX;
      setColWidths(prev => ({ ...prev, [resizingCol]: Math.max(60, resizeStartW + diff) }));
    };
    const handleUp = () => setResizingCol(null);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [resizingCol, resizeStartX, resizeStartW]);

  // Reset page when task changes
  React.useEffect(() => { setPairsPage(0); setFilesPage(0); }, [selectedTaskId]);

  // Upload
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
        onUploadProgress: (e) => { setUploadProgress(Math.round((e.loaded / (e.total || 1)) * 100)); },
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

  // Results (client-side filter on current page)
  const currentPageResults = assignmentData?.results ?? [];
  const filteredResults = (() => {
    let results = [...currentPageResults];
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

  const totalPairsCount = assignmentData?.total_results ?? assignmentData?.total_pairs ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalPairsCount / PAIRS_PER_PAGE));

  // Stats
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

  const handleViewFile = useCallback(async (fileId: string, filename: string) => {
    setViewingFile({ id: fileId, filename });
    setFileContent('');
    onFileViewerOpen();
    setLoadingFileContent(true);
    try {
      const res = await api.get(API_ENDPOINTS.FILE_CONTENT(fileId));
      setFileContent(res.data.content ?? '');
    } catch {
      setFileContent('// Failed to load file content');
    } finally {
      setLoadingFileContent(false);
    }
  }, [onFileViewerOpen]);

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  // Colors
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const subtleBg = useColorModeValue('gray.50', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');
  const dropzoneHoverBg = useColorModeValue('brand.50', 'gray.600');
  const breadcrumbColor = useColorModeValue('gray.500', 'gray.400');
  const codeBg = useColorModeValue('gray.900', 'gray.900');
  const selectedRowBg = useColorModeValue('brand.50', 'whiteAlpha.100');
  const selectedRowHoverBg = useColorModeValue('brand.100', 'whiteAlpha.200');

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" h="400px">
        <Spinner size="xl" color="blue.500" />
      </Box>
    );
  }

  if (!assignmentData) {
    const errorMessage = queryError instanceof Error ? queryError.message : (t('common:noAccess') || 'No access to this assignment');
    return (
      <Box textAlign="center" py={12}>
        <Text fontSize="lg" color="red.500">{errorMessage}</Text>
      </Box>
    );
  }

  const aggFilesCount = totalFiles;
  const aggHighCount = stats.high;
  const aggAvgSim = stats.avg;
  const selectedTask = selectedTaskId ? assignmentData.tasks.find(t => t.task_id === selectedTaskId) : null;

  const tabLabels = [
    t('results:resultsList.topSimilarities'),
    t('results:distribution.title'),
    'Files',
  ];

  const renderResizeHandle = (col: string) => (
    <Box
      position="absolute" right={0} top={0} bottom={0} w="4px" cursor="col-resize" zIndex={2}
      bg={resizingCol === col ? 'brand.400' : 'transparent'}
      _hover={{ bg: 'brand.300' }}
      onMouseDown={(e: React.MouseEvent) => handleResizeStart(col, e)}
    />
  );

  // Compute current page display range
  const pageStart = pairsPage * PAIRS_PER_PAGE + 1;
  const pageEnd = Math.min((pairsPage + 1) * PAIRS_PER_PAGE, totalPairsCount);

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden" position="relative">
      {/* Breadcrumb */}
      <Breadcrumb spacing={1} separator={<FiChevronRight color={breadcrumbColor} />} mb={1} flexShrink={0}>
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
      <Flex justify="space-between" align="flex-start" mb={3} flexShrink={0} wrap="wrap" gap={3}>
        <Box>
          <HStack spacing={3} align="center">
            <Text fontSize="2xl" fontWeight="bold">{assignmentData.name}</Text>
            <Badge colorScheme="blue" fontSize="sm">{assignmentData.files_count} {t('common:files')}</Badge>
            <Badge colorScheme="purple" fontSize="sm">{assignmentData.tasks_count} tasks</Badge>
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
          <Button size="sm" leftIcon={<FiRefreshCw />} onClick={refreshData} isLoading={isFetching}>
            {t('common:refresh')}
          </Button>
        </HStack>
      </Flex>

      {/* Combined Tasks + Upload section */}
      <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} mb={3} flexShrink={0} overflow="hidden">
        {/* Expanded view: upload + task table */}
        {!collapsed && (
          <>
            {/* Upload area */}
            <Box p={3} pb={2}>
              <Flex direction={{ base: 'column', md: 'row' }} gap={3} align="flex-start">
                <HStack spacing={3} flexShrink={0}>
                  <Box>
                    <Text fontSize="xs" color={mutedColor} mb={1}>{t('language')}</Text>
                    <Select
                      value={language}
                      onChange={(e) => { setLanguage(e.target.value); localStorage.setItem(LANG_STORAGE_KEY, e.target.value); }}
                      size="sm" maxW="130px"
                    >
                      {languageOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>{t(`languages:${opt.key}`)}</option>
                      ))}
                    </Select>
                  </Box>
                </HStack>
                <Box
                  {...getRootProps()}
                  border="2px dashed" borderColor={isDragActive ? 'brand.500' : borderColor}
                  borderRadius="lg" p={2} flex={1} w="100%"
                  display="flex" alignItems="center" justifyContent="center"
                  textAlign="center" cursor="pointer"
                  bg={isDragActive ? dropzoneHoverBg : subtleBg}
                  transition="all 0.2s" minH="48px"
                  _hover={{ borderColor: 'brand.400', bg: dropzoneHoverBg }}
                >
                  <input {...getInputProps()} />
                  <HStack spacing={2}>
                    <Icon as={FiUploadCloud} boxSize={4} color="brand.400" />
                    <Text fontSize="xs" fontWeight="medium">
                      {files.length > 0 ? `${files.length} file(s) (${formatFileSize(totalSize)})` : t('dragAndDrop')}
                    </Text>
                  </HStack>
                </Box>
                {files.length > 0 && (
                  <HStack flexShrink={0}>
                    {isUploading && (
                      <Box w="120px">
                        <Progress value={uploadProgress} size="sm" colorScheme="brand" borderRadius="full" hasStripe isAnimated />
                        <Text fontSize="xs" textAlign="center" mt={1}>{uploadProgress}%</Text>
                      </Box>
                    )}
                    <Button colorScheme="brand" size="xs" onClick={handleUpload} isLoading={isUploading} loadingText={t('uploading')} leftIcon={<FiCheckCircle />}>
                      {t('upload', { count: files.length, size: formatFileSize(totalSize) })}
                    </Button>
                    <IconButton aria-label="Clear files" icon={<FiX />} size="xs" variant="ghost" colorScheme="red" onClick={() => setFiles([])} isDisabled={isUploading} />
                  </HStack>
                )}
              </Flex>
            </Box>

            {/* Task table */}
            {assignmentData.tasks.length > 0 && (
              <Box overflowX="auto">
                <Table size="sm" variant="simple">
                  <Thead>
                    <Tr>
                      <Th fontSize="xs" w="30px"></Th>
                      <Th fontSize="xs">Task ID</Th>
                      <Th fontSize="xs">Status</Th>
                      <Th fontSize="xs" isNumeric>Files</Th>
                      <Th fontSize="xs" isNumeric>Pairs</Th>
                      <Th fontSize="xs" isNumeric>High</Th>
                      <Th fontSize="xs" isNumeric>Avg Sim</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    <Tr
                      bg={selectedTaskId === '' ? selectedRowBg : undefined}
                      cursor="pointer"
                      onClick={() => setSelectedTaskId('')}
                      _hover={{ bg: selectedTaskId === '' ? selectedRowHoverBg : hoverBg }}
                      fontWeight={selectedTaskId === '' ? 'semibold' : 'normal'}
                    >
                      <Td px={2}>{selectedTaskId === '' && <Icon as={FiCheckCircle} color="brand.500" boxSize={3} />}</Td>
                      <Td fontSize="sm">All tasks (aggregated)</Td>
                      <Td><Badge colorScheme="blue" fontSize="xs">combined</Badge></Td>
                      <Td fontSize="sm" isNumeric>{aggFilesCount}</Td>
                      <Td fontSize="sm" isNumeric>{assignmentData.total_pairs}</Td>
                      <Td fontSize="sm" isNumeric color={aggHighCount > 0 ? 'red.500' : undefined}>{aggHighCount}</Td>
                      <Td fontSize="sm" isNumeric>
                        <Badge colorScheme={getSimilarityColor(aggAvgSim)} fontSize="xs">{(aggAvgSim * 100).toFixed(1)}%</Badge>
                      </Td>
                    </Tr>
                    {assignmentData.tasks.map((task) => (
                      <Tr
                        key={task.task_id}
                        bg={selectedTaskId === task.task_id ? selectedRowBg : undefined}
                        cursor="pointer"
                        onClick={() => setSelectedTaskId(task.task_id)}
                        _hover={{ bg: selectedTaskId === task.task_id ? selectedRowHoverBg : hoverBg }}
                        fontWeight={selectedTaskId === task.task_id ? 'semibold' : 'normal'}
                      >
                        <Td px={2}>{selectedTaskId === task.task_id && <Icon as={FiCheckCircle} color="brand.500" boxSize={3} />}</Td>
                        <Td fontSize="xs" fontFamily="monospace">{task.task_id.substring(0, 12)}...</Td>
                        <Td>
                          <HStack spacing={1}>
                            {getStatusIcon(task.status)}
                            <Badge colorScheme={getStatusColorScheme(task.status)} fontSize="xs">{task.status}</Badge>
                          </HStack>
                        </Td>
                        <Td fontSize="sm" isNumeric>{task.files_count ?? '-'}</Td>
                        <Td fontSize="sm" isNumeric>{task.total_pairs ?? 0}</Td>
                        <Td fontSize="sm" isNumeric color={(task.high_similarity_count ?? 0) > 0 ? 'red.500' : undefined}>
                          {task.high_similarity_count ?? 0}
                        </Td>
                        <Td fontSize="sm" isNumeric>
                          <Badge colorScheme={getSimilarityColor(task.avg_similarity ?? 0)} fontSize="xs">
                            {((task.avg_similarity ?? 0) * 100).toFixed(1)}%
                          </Badge>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            )}
          </>
        )}

        {/* Collapsed view: just the selected task summary + upload toggle */}
        {collapsed && (
          <Box px={3} py={2}>
            <HStack justify="space-between" spacing={3}>
              <HStack spacing={3}>
                <Icon as={FiCheckCircle} color="brand.500" boxSize={3} />
                {selectedTaskId === '' ? (
                  <>
                    <Text fontSize="sm" fontWeight="semibold">All tasks</Text>
                    <Badge colorScheme="blue" fontSize="xs">{aggFilesCount} files</Badge>
                    <Badge fontSize="xs">{assignmentData.total_pairs} pairs</Badge>
                    {aggHighCount > 0 && <Badge colorScheme="red" fontSize="xs">{aggHighCount} high</Badge>}
                    <Badge colorScheme={getSimilarityColor(aggAvgSim)} fontSize="xs">{(aggAvgSim * 100).toFixed(1)}% avg</Badge>
                  </>
                ) : (
                  <>
                    <Text fontSize="xs" fontFamily="monospace" fontWeight="medium">{selectedTaskId.substring(0, 12)}...</Text>
                    {selectedTask && (
                      <>
                        <Badge colorScheme={getStatusColorScheme(selectedTask.status)} fontSize="xs">{selectedTask.status}</Badge>
                        <Badge fontSize="xs">{selectedTask.files_count ?? '-'} files</Badge>
                        <Badge fontSize="xs">{selectedTask.total_pairs ?? 0} pairs</Badge>
                        {(selectedTask.high_similarity_count ?? 0) > 0 && (
                          <Badge colorScheme="red" fontSize="xs">{selectedTask.high_similarity_count} high</Badge>
                        )}
                        <Badge colorScheme={getSimilarityColor(selectedTask.avg_similarity ?? 0)} fontSize="xs">
                          {((selectedTask.avg_similarity ?? 0) * 100).toFixed(1)}% avg
                        </Badge>
                      </>
                    )}
                  </>
                )}
              </HStack>
              <Button
                size="xs"
                variant="outline"
                leftIcon={<FiUploadCloud />}
                onClick={() => setCollapsed(false)}
              >
                Add files
              </Button>
            </HStack>
          </Box>
        )}

        {/* Toggle */}
        <Flex
          justify="center" py={0.5} cursor="pointer"
          onClick={() => setCollapsed(!collapsed)}
          _hover={{ bg: subtleBg }} transition="background 0.15s"
        >
          <Icon as={collapsed ? FiChevronDown : FiChevronUp} color={mutedColor} boxSize={3} opacity={0.5} />
        </Flex>
      </Box>

      {/* Task progress */}
      {activeTask && (
        <Box mb={3} flexShrink={0}>
          <TaskProgress taskId={activeTask.task_id} status={activeTask.status} cardBg={cardBg} onCompleted={refreshData} />
        </Box>
      )}

      {/* Results area */}
      {totalPairsCount > 0 || true ? (
        <Box flex={1} minH={0} display="flex" flexDirection="column" overflow="hidden">
          {/* Tabs */}
          <HStack spacing={1} mb={3} flexShrink={0} flexWrap="wrap">
            {tabLabels.map((label, i) => (
              <Button key={i} size="sm" variant={activeTab === i ? 'solid' : 'ghost'} colorScheme={activeTab === i ? 'brand' : 'gray'} onClick={() => setActiveTab(i)} fontSize="xs">
                {label}
              </Button>
            ))}
            <Button size="sm" variant={activeTab === 3 ? 'solid' : 'ghost'} colorScheme={activeTab === 3 ? 'brand' : 'gray'} onClick={() => setActiveTab(3)} fontSize="xs">
              <HStack spacing={1}>
                <Icon as={FiList} boxSize={3} />
                <Text>Review</Text>
              </HStack>
            </Button>
          </HStack>

          {/* Tab content */}
          <Box flex={1} minH={0} display="flex" flexDirection="column" overflow="hidden">
            {/* Top Similarities */}
            {activeTab === 0 && (
              <Box flex={1} display="flex" flexDirection="column" minH={0} overflow="hidden">
                <HStack mb={3} flexShrink={0}>
                  <InputGroup size="sm" maxW="300px">
                    <InputLeftElement pointerEvents="none"><Icon as={FiSearch} color={mutedColor} /></InputLeftElement>
                    <Input placeholder={t('results:taskPicker.search')} value={resultsSearch} onChange={(e) => setResultsSearch(e.target.value)} />
                  </InputGroup>
                  <Select size="sm" w="160px" value={similarityFilter} onChange={(e) => setSimilarityFilter(e.target.value)}>
                    <option value="all">{t('common:all')}</option>
                    <option value="high">High (&ge;80%)</option>
                    <option value="medium">Medium (50-80%)</option>
                    <option value="low">Low (&lt;50%)</option>
                  </Select>
                  <Text fontSize="sm" color={mutedColor}>
                    {pageStart}–{pageEnd} of {totalPairsCount}
                  </Text>
                </HStack>

                <Box flex={1} minH={0} overflowY="auto">
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
                                <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="220px">{result.file_a.filename}</Text>
                                <Text fontSize="xs" color={mutedColor}>vs</Text>
                                <Text fontSize="sm" fontWeight="medium" noOfLines={1} maxW="220px">{result.file_b.filename}</Text>
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
                  {filteredResults.length === 0 && !isFetching && (
                    <Box textAlign="center" py={8} color={mutedColor}>
                      <Text>{t('results:taskPicker.noMatches')}</Text>
                    </Box>
                  )}
                  {isFetching && (
                    <Flex justify="center" py={4}><Spinner size="sm" /></Flex>
                  )}
                </Box>

                {/* Server-side pagination */}
                <HStack justify="center" py={2} flexShrink={0} spacing={2}>
                  <IconButton
                    aria-label="First page"
                    icon={<Icon as={FiChevronLeft} />}
                    size="sm" variant="ghost"
                    isDisabled={pairsPage === 0 || isFetching}
                    onClick={() => setPairsPage(0)}
                  />
                  <IconButton
                    aria-label="Previous page"
                    icon={<Icon as={FiChevronLeft} transform="rotate(0deg)" />}
                    size="sm" variant="ghost"
                    isDisabled={pairsPage === 0 || isFetching}
                    onClick={() => setPairsPage(p => Math.max(0, p - 1))}
                  />
                  <Text fontSize="xs" color={mutedColor} minW="100px" textAlign="center">
                    Page {pairsPage + 1} / {totalPages}
                  </Text>
                  <IconButton
                    aria-label="Next page"
                    icon={<Icon as={FiChevronLeft} transform="rotate(180deg)" />}
                    size="sm" variant="ghost"
                    isDisabled={pairsPage >= totalPages - 1 || isFetching}
                    onClick={() => setPairsPage(p => Math.min(totalPages - 1, p + 1))}
                  />
                  <IconButton
                    aria-label="Last page"
                    icon={<Icon as={FiChevronLeft} transform="rotate(180deg)" />}
                    size="sm" variant="ghost"
                    isDisabled={pairsPage >= totalPages - 1 || isFetching}
                    onClick={() => setPairsPage(totalPages - 1)}
                  />
                  <HStack spacing={1} ml={2}>
                    <Input
                      size="xs"
                      w="60px"
                      placeholder="Go to..."
                      value={pairsGoPage}
                      onChange={(e) => setPairsGoPage(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handlePairsGoToPage(); }}
                    />
                    <Button size="xs" onClick={handlePairsGoToPage} isDisabled={!pairsGoPage || isFetching}>
                      Go
                    </Button>
                  </HStack>
                </HStack>
              </Box>
            )}

            {/* Distribution */}
            {activeTab === 1 && (
              <Box flex={1} display="flex" flexDirection="column" minH={0} overflowY="auto">
                <SimilarityDistribution
                  results={assignmentData.results}
                  totalPairs={assignmentData.total_pairs}
                  cardBg={cardBg}
                  assignmentId={assignmentId}
                  taskId={selectedTaskId || undefined}
                  stats={stats}
                />
              </Box>
            )}

            {/* Files */}
            {activeTab === 2 && (
              <Box flex={1} display="flex" flexDirection="column" minH={0} overflow="hidden">
                <HStack spacing={3} mb={3} flexShrink={0} flexWrap="wrap">
                  <InputGroup size="sm" maxW="250px">
                    <InputLeftElement pointerEvents="none"><Icon as={FiSearch} color={mutedColor} /></InputLeftElement>
                    <Input placeholder="Filter by filename..." value={fileFilterName} onChange={(e) => setFileFilterName(e.target.value)} />
                  </InputGroup>
                  <Select size="sm" w="180px" value={fileFilterTask} onChange={(e) => { setFileFilterTask(e.target.value); setFilesPage(0); }}>
                    <option value="">All tasks</option>
                    {assignmentData.tasks.map((task) => (
                      <option key={task.task_id} value={task.task_id}>{task.task_id.substring(0, 8)}...</option>
                    ))}
                  </Select>
                  <Text fontSize="xs" color={mutedColor}>{totalFiles} files</Text>
                </HStack>

                <Box flex={1} overflowY="auto">
                  <TableContainer>
                    <Table variant="simple" size="sm">
                      <colgroup>
                        <col style={{ width: `${colWidths.filename}px` }} />
                        <col style={{ width: `${colWidths.task}px` }} />
                        <col style={{ width: `${colWidths.maxSim}px` }} />
                        <col style={{ width: '80px' }} />
                      </colgroup>
                      <Thead position="sticky" top={0} bg={cardBg} zIndex={1}>
                        <Tr>
                          <Th position="relative" cursor="pointer" userSelect="none" _hover={{ bg: hoverBg }} onClick={() => handleFileSort('filename')} pr="20px">
                            <HStack spacing={1}>
                              <Text as="span">Filename</Text>
                              {fileSortCol === 'filename' && <Icon as={fileSortDir === 'asc' ? FiChevronUp : FiChevronDown} boxSize={3} />}
                            </HStack>
                            {renderResizeHandle('filename')}
                          </Th>
                          <Th position="relative" cursor="pointer" userSelect="none" _hover={{ bg: hoverBg }} onClick={() => handleFileSort('task_id')} pr="20px">
                            <HStack spacing={1}>
                              <Text as="span">Task</Text>
                              {fileSortCol === 'task_id' && <Icon as={fileSortDir === 'asc' ? FiChevronUp : FiChevronDown} boxSize={3} />}
                            </HStack>
                            {renderResizeHandle('task')}
                          </Th>
                          <Th position="relative" cursor="pointer" userSelect="none" _hover={{ bg: hoverBg }} onClick={() => handleFileSort('max_similarity')} pr="20px">
                            <HStack spacing={1}>
                              <Text as="span">Max Sim</Text>
                              {fileSortCol === 'max_similarity' && <Icon as={fileSortDir === 'asc' ? FiChevronUp : FiChevronDown} boxSize={3} />}
                            </HStack>
                            {renderResizeHandle('maxSim')}
                          </Th>
                          <Th></Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {displayedFiles.map((file) => (
                          <Tr key={file.id} _hover={{ bg: hoverBg }}>
                            <Td fontSize="sm" fontWeight="medium" overflow="hidden" textOverflow="ellipsis" whiteSpace="nowrap">{file.filename}</Td>
                            <Td fontSize="xs" fontFamily="monospace" color={mutedColor}>
                              {file.task_id ? file.task_id.substring(0, 8) + '...' : '-'}
                            </Td>
                            <Td isNumeric>
                              <Badge colorScheme={getSimilarityColor(file.max_similarity ?? 0)} fontSize="xs">
                                {((file.max_similarity ?? 0) * 100).toFixed(1)}%
                              </Badge>
                            </Td>
                            <Td>
                              <Button size="xs" leftIcon={<FiEye />} variant="ghost" onClick={() => handleViewFile(file.id, file.filename)}>View</Button>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </TableContainer>
                  {displayedFiles.length === 0 && (
                    <Box textAlign="center" py={8} color={mutedColor}><Text>No files in this assignment</Text></Box>
                  )}
                </Box>

                {totalFilePages > 1 && (
                  <HStack spacing={2} mt={3} flexShrink={0} justifyContent="center">
                    <Button size="xs" leftIcon={<FiChevronLeft />} onClick={() => setFilesPage(p => Math.max(0, p - 1))} isDisabled={filesPage === 0}>
                      Previous
                    </Button>
                    <Text fontSize="xs" color={mutedColor}>
                      Page {filesPage + 1} of {totalFilePages}
                    </Text>
                    <Button size="xs" rightIcon={<FiChevronRight />} onClick={() => setFilesPage(p => Math.min(totalFilePages - 1, p + 1))} isDisabled={filesPage >= totalFilePages - 1}>
                      Next
                    </Button>
                    <HStack spacing={1} ml={2}>
                      <Input
                        size="xs"
                        w="60px"
                        placeholder="Go to..."
                        value={filesGoPage}
                        onChange={(e) => setFilesGoPage(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleFilesGoToPage(); }}
                      />
                      <Button size="xs" onClick={handleFilesGoToPage} isDisabled={!filesGoPage}>
                        Go
                      </Button>
                    </HStack>
                  </HStack>
                )}
              </Box>
            )}

            {/* Review */}
            {activeTab === 3 && (
              <Box flex={1} display="flex" flexDirection="column" minH={0} overflow="hidden">
                <ReviewQueue
                  assignmentId={assignmentId!}
                  onReviewPair={(pair, allPairs) => {
                    setSelectedPair({ file_a: pair.file_a, file_b: pair.file_b, ast_similarity: pair.ast_similarity });
                    setReviewQueuePairs(allPairs || []);
                    setPairModalOpen(true);
                  }}
                />
              </Box>
            )}
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
        pairs={reviewQueuePairs}
        assignmentName={assignmentData.name}
        onActionComplete={() => {
          refreshData();
        }}
      />

      <Modal isOpen={isFileViewerOpen} onClose={onFileViewerClose} size="4xl" scrollBehavior="inside">
        <ModalOverlay />
        <ModalContent maxH="80vh">
          <ModalHeader fontSize="md">
            <HStack><Icon as={FiFileText} /><Text>{viewingFile?.filename}</Text></HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody p={0}>
            {loadingFileContent ? (
              <Box textAlign="center" py={12}><Spinner /></Box>
            ) : (
              <Box as="pre" bg={codeBg} color="gray.100" p={4} fontSize="sm" fontFamily="monospace"
                overflowX="auto" overflowY="auto" maxH="60vh" whiteSpace="pre" borderRadius="md">
                {fileContent}
              </Box>
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default AssignmentDetail;
