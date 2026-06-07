import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
  InputGroup,
  InputLeftElement,
  Input,
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
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  Card,
  CardBody,
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
  FiLayers,
  FiDownload,
  FiTrash2,
  FiHardDrive,
  FiChevronDown,
  FiChevronUp,
  FiFileText,
} from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS, getAssignmentStorageUsage } from '../../services/api';
import type { AssignmentFullResponse, PlagiarismResult } from '../../types';
import { getSimilarityColor, getStatusColorScheme } from '../../utils/statusColors';
import TaskProgress from '../../components/Results/TaskProgress';
import PairComparisonModal from '../../components/PairComparisonModal';
import { useAssignmentInfo } from '../../contexts/AssignmentContext';
import { useExportAllPdf } from '../../hooks/useGrading';
import {
  AssignmentReviewTab,
  AssignmentStatsTab,
  AssignmentFilesTab,
  AssignmentSettingsTab,
} from './tabs';
import EventsTab from './tabs/EventsTab';

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

const getFileExtension = (filename: string): string => {
  const parts = filename.split('.');
  return parts.length > 1 ? parts.pop()!.toLowerCase() : '';
};

const EXTENSION_TO_LANGUAGE: Record<string, string> = {
  '.py': 'python',
  '.java': 'java',
  '.js': 'javascript',
  '.ts': 'typescript',
  '.tsx': 'tsx',
  '.go': 'go',
  '.rs': 'rust',
  '.c': 'c',
  '.cpp': 'cpp',
  '.cc': 'cpp',
  '.cxx': 'cpp',
  '.h': 'cpp',
  '.hpp': 'cpp',
};

const detectLanguageFromExtension = (filename: string): string | null => {
  const ext = '.' + getFileExtension(filename);
  return EXTENSION_TO_LANGUAGE[ext] || null;
};

const languageOptions = [
  { value: 'auto', key: 'auto' },
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
  const [detectedLanguage, setDetectedLanguage] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadName, setUploadName] = useState('');

  // Task state
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [collapsed, setCollapsed] = useState(false);

  // Tab state
  const [activeTab, setActiveTab] = useState(0);

  // Results pagination
  const [pairsPage, setPairsPage] = useState(0);

  // Files tab
  const [filesPage, setFilesPage] = useState(0);
  const FILES_PER_PAGE = 50;

  // Pair comparison
  const [pairModalOpen, setPairModalOpen] = useState(false);
  const [selectedPair, setSelectedPair] = useState<{
    id?: string;
    file_a: { id: string; filename: string };
    file_b: { id: string; filename: string };
    ast_similarity: number;
  } | null>(null);
  const [reviewQueuePairs, setReviewQueuePairs] = useState<PlagiarismResult[]>([]);
  const { setAssignmentInfo } = useAssignmentInfo();

  // File viewer
  const { isOpen: isFileViewerOpen, onOpen: onFileViewerOpen, onClose: onFileViewerClose } = useDisclosure();
  const [viewingFile, setViewingFile] = useState<{ id: string; filename: string } | null>(null);
  const [fileContent, setFileContent] = useState<string>('');

  // Task deletion
  const queryClient = useQueryClient();
  const { isOpen: isDeleteTaskOpen, onOpen: onDeleteTaskOpen, onClose: onDeleteTaskClose } = useDisclosure();
  const [taskToDelete, setTaskToDelete] = useState<string | null>(null);
  const cancelDeleteRef = React.useRef<HTMLButtonElement>(null);
  const [loadingFileContent, setLoadingFileContent] = useState(false);

  const deleteTaskMutation = useMutation({
    mutationFn: async (taskId: string) => {
      const res = await api.delete(API_ENDPOINTS.HARD_DELETE_TASK(taskId));
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignmentFull', assignmentId] });
      toast({
        title: t('common:success'),
        description: t('sessions:taskDeleted'),
        status: 'success',
        duration: 3000,
      });
    },
    onError: () => {
      toast({
        title: t('common:error'),
        description: t('sessions:deleteFailed'),
        status: 'error',
        duration: 4000,
      });
    },
  });

  const handleDeleteTask = (taskId: string) => {
    setTaskToDelete(taskId);
    onDeleteTaskOpen();
  };

  const confirmDeleteTask = () => {
    if (taskToDelete) {
      deleteTaskMutation.mutate(taskToDelete);
      if (selectedTaskId === taskToDelete) {
        setSelectedTaskId('');
      }
    }
    onDeleteTaskClose();
  };

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
        const msg = axiosErr.response?.data?.error_details || t('common:errors.noAccess');
        throw new Error(msg);
      }
    },
    enabled: !!assignmentId,
  });

  const { data: storageData } = useQuery({
    queryKey: ['storage', 'assignment', assignmentId],
    queryFn: async () => {
      const res = await getAssignmentStorageUsage(assignmentId!);
      return res.data;
    },
    enabled: !!assignmentId,
  });

  useEffect(() => {
    if (queryError) {
      const msg = queryError instanceof Error ? queryError.message : t('common:errors.noAccess');
      toast({ title: t('common:error'), description: msg, status: 'error', duration: 5000 });
    }
  }, [queryError, toast, t]);

  useEffect(() => {
    setPairModalOpen(false);
    setSelectedPair(null);
  }, [assignmentId]);

  useEffect(() => {
    if (assignmentData?.name) {
      setAssignmentInfo({
        name: assignmentData.name,
        filesCount: assignmentData.files_count ?? 0,
        tasksCount: assignmentData.tasks_count ?? 0,
      });
    }
    return () => setAssignmentInfo(null);
  }, [assignmentData?.name, assignmentData?.files_count, assignmentData?.tasks_count, setAssignmentInfo]);

  const exportAllPdfMutation = useExportAllPdf();

  const totalFiles = assignmentData?.total_files ?? 0;

  const activeTask = assignmentData?.tasks.find(t => ACTIVE_STATUSES.includes(t.status));
  const isProcessing = !!activeTask;
  const refreshData = useCallback(() => refetch(), [refetch]);

  // Reset page when task changes
  React.useEffect(() => { setPairsPage(0); setFilesPage(0); }, [selectedTaskId]);

  // Upload
  const onDrop = useCallback(
    (acceptedFiles: File[], rejected: { file: File }[]) => {
      if (rejected.length > 0) {
        toast({ title: `${rejected.length} ${t('upload:rejected')}`, description: t('upload:fileLimitDescription', { max: MAX_FILES }), status: 'warning', duration: 4000 });
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

    // Use detected language if auto, otherwise use selected language
    const languageToSubmit = language === 'auto' && detectedLanguage ? detectedLanguage : language;

    setIsUploading(true);
    setUploadProgress(0);
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));
      formData.append('language', languageToSubmit);
      if (assignmentId) formData.append('assignment_id', assignmentId);
      if (uploadName.trim()) formData.append('name', uploadName.trim());
      await api.post(API_ENDPOINTS.CHECK, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => { setUploadProgress(Math.round((e.loaded / (e.total || 1)) * 100)); },
      });
      toast({ title: t('toasts.success'), status: 'success', duration: 3000 });
      setFiles([]);
      setUploadName('');
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
    const pair = {
      id: result.id,
      file_a: result.file_a,
      file_b: result.file_b,
      ast_similarity: result.ast_similarity,
      matches: result.matches,
      created_at: result.created_at,
    };
    setSelectedPair(pair);
    setReviewQueuePairs(prev => {
      if (prev.some(p => p.id === result.id)) return prev;
      return [pair, ...prev];
    });
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
      setFileContent(t('common:errors.failedToLoad'));
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
    const errorMessage = queryError instanceof Error ? queryError.message : t('common:errors.noAccess');
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
    t('assignments:files'),
    t('assignments:review'),
    t('results:distribution.title'),
    t('assignments:events'),
    t('common:settings'),
  ];

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden" position="relative">
      {/* Storage Usage Widget */}
      {storageData && (
        <Card bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} mb={3} flexShrink={0}>
          <CardBody py={3}>
            <HStack justify="space-between" spacing={4} wrap="wrap">
              <HStack spacing={3}>
                <Icon as={FiHardDrive} boxSize={4} color="brand.500" />
                <Text fontSize="sm" fontWeight="semibold">{t('storage:storageUsage')}</Text>
                <Text fontSize="sm" color={mutedColor}>
                  {storageData.total_human} · {storageData.file_count} {t('common:files')}
                </Text>
              </HStack>
              <Button
                size="xs"
                variant="ghost"
                leftIcon={<FiRefreshCw />}
                onClick={() => queryClient.invalidateQueries({ queryKey: ['storage', 'assignment', assignmentId] })}
                isLoading={queryClient.isFetching({ queryKey: ['storage', 'assignment', assignmentId] }) > 0}
              >
                {t('common:refresh')}
              </Button>
            </HStack>
          </CardBody>
        </Card>
      )}

      {/* Task selection table */}
      {assignmentData.tasks.length > 0 && (
        <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} mb={3} flexShrink={0} overflow="hidden">
          <Box overflowX="auto">
            <Table size="sm" variant="simple">
              <Thead>
                 <Tr>
                   <Th fontSize="xs" w="30px"></Th>
                   <Th fontSize="xs">{t('assignments:taskId')}</Th>
                   <Th fontSize="xs">{t('assignments:status')}</Th>
                   <Th fontSize="xs" isNumeric>{t('assignments:files')}</Th>
                   <Th fontSize="xs" isNumeric>{t('assignments:pairs')}</Th>
                   <Th fontSize="xs" isNumeric>{t('assignments:high')}</Th>
                    <Th fontSize="xs" isNumeric>{t('assignments:avgSim')}</Th>
                    <Th fontSize="xs" isNumeric>{t('results:exportPdf')}</Th>
                    <Th fontSize="xs" w="40px"></Th>
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
                    <Td fontSize="sm">{t('assignments:allTasksAggregated')}</Td>
                    <Td><Badge colorScheme="blue" fontSize="xs">{t(`status:combined`)}</Badge></Td>
                   <Td fontSize="sm" isNumeric>{aggFilesCount}</Td>
                   <Td fontSize="sm" isNumeric>{assignmentData.total_pairs}</Td>
                   <Td fontSize="sm" isNumeric color={aggHighCount > 0 ? 'red.500' : undefined}>{aggHighCount}</Td>
                   <Td fontSize="sm" isNumeric>
                     <Badge colorScheme={getSimilarityColor(aggAvgSim)} fontSize="xs">{(aggAvgSim * 100).toFixed(1)}%</Badge>
                   </Td>
                   <Td isNumeric>
                     <IconButton
                       aria-label={t('results:exportPdf')}
                       icon={<FiDownload />}
                       size="xs"
                       variant="ghost"
                       colorScheme="blue"
                       isLoading={exportAllPdfMutation.isPending}
                       isDisabled={assignmentData.total_pairs === 0}
                       onClick={(e) => {
                         e.stopPropagation();
                         exportAllPdfMutation.mutate({ assignmentId: assignmentId! });
                       }}
                     />
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
                         <Badge colorScheme={getStatusColorScheme(task.status)} fontSize="xs">{t(`status:${task.status}`)}</Badge>
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
                    <Td isNumeric>
                      <IconButton
                        aria-label={t('results:exportPdf')}
                        icon={<FiDownload />}
                        size="xs"
                        variant="ghost"
                        colorScheme="blue"
                        isLoading={exportAllPdfMutation.isPending}
                        isDisabled={(task.total_pairs ?? 0) === 0}
                        onClick={(e) => {
                          e.stopPropagation();
                          exportAllPdfMutation.mutate({ assignmentId: assignmentId!, taskId: task.task_id });
                        }}
                      />
                    </Td>
                    <Td>
                      <IconButton
                        aria-label="Delete task"
                        icon={<FiTrash2 />}
                        size="xs"
                        variant="ghost"
                        colorScheme="red"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteTask(task.task_id);
                        }}
                      />
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        </Box>
      )}

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
          </HStack>

          {/* Tab content */}
          <Box flex={1} minH={0} display="flex" flexDirection="column" overflow="hidden">
            {/* Files Tab (with upload form) */}
            {activeTab === 0 && (
              <Box flex={1} display="flex" flexDirection="column" minH={0} overflow="hidden">
                {/* Collapsible upload form */}
                <Box
                  bg={cardBg}
                  borderRadius="lg"
                  borderWidth="1px"
                  borderColor={borderColor}
                  mb={3}
                  flexShrink={0}
                  overflow="hidden"
                >
                  {!collapsed && (
                    <Box p={3} pb={2}>
                      <Flex direction={{ base: 'column', md: 'row' }} gap={3} align="flex-start">
                        <HStack spacing={3} flexShrink={0}>
                          <Box>
                            <Text fontSize="xs" color={mutedColor} mb={1}>
                              {t('language')}
                              {detectedLanguage && <Badge ml={1} colorScheme="green" fontSize="xs">{t('languages:autoDetected')}</Badge>}
                            </Text>
                            <Select
                              value={detectedLanguage || language}
                              onChange={(e) => {
                                const lang = e.target.value;
                                setLanguage(lang);
                                if (lang !== 'auto') {
                                  setDetectedLanguage(null);
                                }
                                localStorage.setItem(LANG_STORAGE_KEY, lang);
                              }}
                              size="sm" maxW="130px"
                            >
                              {languageOptions.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {detectedLanguage && opt.value === 'auto' ? `${t(`languages:${detectedLanguage}`)} (${t('languages:auto')})` : t(`languages:${opt.key}`)}
                                </option>
                              ))}
                            </Select>
                          </Box>
                          <Box>
                            <Text fontSize="xs" color={mutedColor} mb={1}>
                              {t('uploadName')}
                            </Text>
                            <Input
                              value={uploadName}
                              onChange={(e) => setUploadName(e.target.value)}
                              size="sm"
                              maxW="200px"
                              placeholder={t('uploadNamePlaceholder')}
                            />
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
                            <IconButton aria-label={t('common:aria.clearFiles')} icon={<FiX />} size="xs" variant="ghost" colorScheme="red" onClick={() => setFiles([])} isDisabled={isUploading} />
                          </HStack>
                        )}
                      </Flex>
                    </Box>
                  )}
                  <Flex
                    justify="center" py={0.5} cursor="pointer"
                    onClick={() => setCollapsed(!collapsed)}
                    _hover={{ bg: subtleBg }} transition="background 0.15s"
                  >
                    <Icon as={collapsed ? FiChevronDown : FiChevronUp} color={mutedColor} boxSize={3} opacity={0.5} />
                  </Flex>
                </Box>

                <AssignmentFilesTab
                  files={assignmentData.files ?? []}
                  totalFiles={totalFiles}
                  tasks={assignmentData.tasks}
                  isLoading={isLoading}
                  isFetching={isFetching}
                  page={filesPage}
                  onPageChange={setFilesPage}
                  filesPerPage={FILES_PER_PAGE}
                  onViewFile={handleViewFile}
                />
              </Box>
            )}

            {/* Review Tab */}
            {activeTab === 1 && (
              <AssignmentReviewTab
                assignmentId={assignmentId!}
                onReviewPair={(pair, allPairs) => {
                  setSelectedPair({ file_a: pair.file_a, file_b: pair.file_b, ast_similarity: pair.ast_similarity });
                  setReviewQueuePairs(allPairs || []);
                  setPairModalOpen(true);
                }}
              />
            )}

            {/* Stats Tab */}
            {activeTab === 2 && (
              <AssignmentStatsTab
                results={assignmentData.results}
                totalPairs={assignmentData.total_pairs}
                stats={stats}
                assignmentId={assignmentId}
                taskId={selectedTaskId || undefined}
              />
            )}

            {/* Events Tab */}
            {activeTab === 3 && <EventsTab />}

            {/* Settings Tab */}
            {activeTab === 4 && (
              <AssignmentSettingsTab
                assignmentId={assignmentId!}
                assignmentName={assignmentData.name}
                assignmentDescription={assignmentData.description}
                onRefetch={refreshData}
              />
            )}
          </Box>
        </Box>
      ) : (
        <Flex flex={1} align="center" justify="center" direction="column" color={mutedColor} py={12}>
          <Icon as={FiFolder} boxSize={10} mb={3} />
          <Text fontWeight="medium">{t('results:noChecks')}</Text>
          <Text fontSize="sm" mt={1}>{t('review:uploadFilesToStartAnalysis')}</Text>
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

      <AlertDialog
        isOpen={isDeleteTaskOpen}
        leastDestructiveRef={cancelDeleteRef}
        onClose={onDeleteTaskClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('common:delete')} {t('common:session')}
            </AlertDialogHeader>
            <AlertDialogBody>
              {t('sessions:deleteSessionConfirm')}
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelDeleteRef} onClick={onDeleteTaskClose}>
                {t('common:cancel')}
              </Button>
              <Button
                colorScheme="red"
                onClick={confirmDeleteTask}
                ml={3}
                isLoading={deleteTaskMutation.isPending}
                leftIcon={<FiTrash2 />}
              >
                {t('common:delete')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default AssignmentDetail;
