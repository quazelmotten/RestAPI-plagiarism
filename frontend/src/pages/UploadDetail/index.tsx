import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  Badge,
  Button,
  IconButton,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  useColorModeValue,
  useToast,
  Spinner,
  Icon,
  Progress,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  Input,
  Select,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiArrowLeft, FiTrash2, FiRefreshCw, FiFolder, FiEdit2 } from 'react-icons/fi';
import { useQueryClient } from '@tanstack/react-query';
import { useUploadDetails, useDeleteUpload, useReanalyzeUpload, useUpdateUpload, useUploadFiles, useDeleteUploadFile } from '../../hooks/useUploadQueries';
import { useTaskDetails } from '../../hooks/useTaskQueries';
import { useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../../services/api';
import TaskProgress from '../../components/Results/TaskProgress';
import ResultsList from '../../components/Results/ResultsList';
import type { UploadFile } from '../../types';

const UploadDetail: React.FC = () => {
  const { uploadId } = useParams<{ uploadId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation(['common', 'upload', 'status']);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tabIndex, setTabIndex] = useState(0);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const { data: upload, isLoading: uploadLoading } = useUploadDetails(uploadId);
  const { data: taskDetails, isLoading: taskLoading } = useTaskDetails(uploadId);
  const { data: files } = useUploadFiles(uploadId);
  const deleteUpload = useDeleteUpload();
  const reanalyzeUpload = useReanalyzeUpload();
  const deleteFile = useDeleteUploadFile();

  const handleDelete = async () => {
    if (!uploadId) return;
    try {
      await deleteUpload.mutateAsync(uploadId);
      toast({ title: t('upload:uploadDeleted'), status: 'success', duration: 2000 });
      navigate('/dashboard/uploads');
    } catch {
      toast({ title: t('upload:failedToDelete'), status: 'error', duration: 3000 });
    }
    setDeleteConfirmOpen(false);
  };

  const handleReanalyze = async () => {
    if (!uploadId) return;
    try {
      await reanalyzeUpload.mutateAsync({ taskId: uploadId });
      toast({ title: t('upload:reanalysisStarted'), status: 'info', duration: 2000 });
    } catch {
      toast({ title: t('upload:failedToReanalyze'), status: 'error', duration: 3000 });
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    if (!uploadId) return;
    try {
      await deleteFile.mutateAsync({ taskId: uploadId, fileId });
      toast({ title: t('upload:fileDeleted'), status: 'success', duration: 2000 });
    } catch {
      toast({ title: t('upload:failedToDeleteFile'), status: 'error', duration: 3000 });
    }
  };

  const handleCompare = (result: any) => {
    navigate(`/dashboard/pair-comparison?file_a=${result.file_a.id}&file_b=${result.file_b.id}&task=${uploadId}`);
  };

  const getSimilarityColor = (similarity: number) => {
    if (similarity >= 0.8) return 'red';
    if (similarity >= 0.5) return 'yellow';
    return 'green';
  };

  if (uploadLoading) {
    return <Flex justify="center" py={8}><Spinner size="lg" /></Flex>;
  }

  if (!upload) {
    return (
      <Flex justify="center" py={8} flexDirection="column" align="center">
        <Text fontSize="lg" color="gray.500">{t('upload:notFound')}</Text>
        <Button mt={4} onClick={() => navigate('/dashboard/uploads')}>{t('upload:backToUploads')}</Button>
      </Flex>
    );
  }

  const isProcessing = ['queued', 'indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results', 'processing'].includes(upload.status);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return <Badge colorScheme="green">{t('status:completed')}</Badge>;
      case 'queued': return <Badge colorScheme="yellow">{t('status:queued')}</Badge>;
      case 'processing':
      case 'indexing':
      case 'finding_intra_pairs':
      case 'finding_cross_pairs':
      case 'storing_results': return <Badge colorScheme="blue">{t('status:processing')}</Badge>;
      case 'failed':
      case 'error': return <Badge colorScheme="red">{t('status:error')}</Badge>;
      default: return <Badge colorScheme="gray">{status}</Badge>;
    }
  };

  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const hoverBg = useColorModeValue('gray.50', 'gray.600');
  const cardBg = useColorModeValue('white', 'gray.700');

  return (
    <VStack align="stretch" spacing={6} flex={1} overflow="hidden">
      {/* Header */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={2}>
        <HStack>
          <IconButton
            icon={<FiArrowLeft />}
            aria-label={t('back')}
            size="sm"
            variant="ghost"
            onClick={() => navigate('/dashboard/uploads')}
          />
          <Text fontSize="2xl" fontWeight="bold" noOfLines={1}>
            {upload.name || `${t('upload:uploadName')} ${upload.task_id.substring(0, 8)}`}
          </Text>
          {getStatusBadge(upload.status)}
        </HStack>
        <HStack>
          {upload.status === 'completed' && (
            <Button size="sm" leftIcon={<FiRefreshCw />} onClick={handleReanalyze}>
              {t('upload:reanalyze')}
            </Button>
          )}
          <Button size="sm" colorScheme="red" leftIcon={<FiTrash2 />} onClick={() => setDeleteConfirmOpen(true)}>
            {t('delete')}
          </Button>
        </HStack>
      </Flex>

      {/* Stats row */}
      <HStack spacing={{ base: 2, md: 6 }} fontSize="sm" color="gray.500" wrap="wrap">
        <Text><strong>{files?.length || 0}</strong> {t('files')}</Text>
        {upload.language && <Text><strong>{upload.language}</strong></Text>}
        {upload.total_pairs > 0 && <Text><strong>{upload.total_pairs}</strong> {t('pairs')}</Text>}
        {upload.high_similarity_count > 0 && (
          <Text color="red.500"><strong>{upload.high_similarity_count}</strong> {t('upload:highSimilarity')}</Text>
        )}
        {upload.assignment_name && (
          <HStack>
            <Icon as={FiFolder} boxSize={3} color="purple.500" />
            <Text color="purple.600">{upload.assignment_name}</Text>
          </HStack>
        )}
      </HStack>

      {/* Progress bar for processing uploads */}
      {isProcessing && uploadId && (
        <TaskProgress taskId={uploadId} status={upload.status} />
      )}

      {/* Tabs */}
      <Tabs index={tabIndex} onChange={setTabIndex} flex={1} overflow="hidden" display="flex" flexDirection="column">
        <TabList>
          <Tab>{t('upload:tabs.results')}</Tab>
          <Tab>{t('upload:tabs.files')}</Tab>
          <Tab>{t('upload:tabs.settings')}</Tab>
        </TabList>

        <TabPanels flex={1} overflow="hidden">
          {/* Results Tab */}
          <TabPanel p={0} pt={4} overflow="hidden" display="flex" flexDirection="column">
            {upload.status === 'completed' && taskDetails && taskDetails.results && (
              <ResultsList
                results={taskDetails.results}
                totalPairs={taskDetails.total_pairs || 0}
                borderColor={borderColor}
                hoverBg={hoverBg}
                getSimilarityColor={getSimilarityColor}
                handleCompare={handleCompare}
                cardBg={cardBg}
                loading={taskLoading}
              />
            )}
            {upload.status === 'completed' && (!taskDetails || !taskDetails.results) && (
              <Flex justify="center" py={8}>
                <Text color="gray.500">{t('upload:noResults')}</Text>
              </Flex>
            )}
          </TabPanel>

          {/* Files Tab */}
          <TabPanel p={0} pt={4} overflow="hidden" display="flex" flexDirection="column">
            <FilesTable files={files || []} onDelete={handleDeleteFile} />
          </TabPanel>

          {/* Settings Tab */}
          <TabPanel p={0} pt={4} overflow="hidden" display="flex" flexDirection="column">
            <SettingsPanel upload={upload} />
          </TabPanel>
        </TabPanels>
      </Tabs>

      {/* Delete confirmation */}
      <AlertDialog
        isOpen={deleteConfirmOpen}
        leastDestructiveRef={cancelRef}
        onClose={() => setDeleteConfirmOpen(false)}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader>{t('upload:deleteTitle')}</AlertDialogHeader>
            <AlertDialogBody>
              {t('upload:deleteDescription', { count: files?.length || 0 })}
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={() => setDeleteConfirmOpen(false)}>{t('cancel')}</Button>
              <Button colorScheme="red" onClick={handleDelete} ml={3} isLoading={deleteUpload.isPending}>
                {t('delete')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
};

const FilesTable: React.FC<{ files: UploadFile[]; onDelete: (fileId: string) => void }> = ({ files, onDelete }) => {
  const { t } = useTranslation(['common', 'upload']);
  const bg = useColorModeValue('white', 'gray.700');

  return (
    <Box flex={1} overflow="hidden" display="flex" flexDirection="column">
      <TableContainer flex={1} overflowY="auto" overflowX="auto" bg={bg} borderRadius="md">
        <Table size="sm" minW="500px">
          <Thead>
            <Tr>
              <Th>{t('upload:filesTable.filename')}</Th>
              <Th>{t('upload:filesTable.language')}</Th>
              <Th>{t('upload:filesTable.maxSimilarity')}</Th>
              <Th>{t('upload:filesTable.actions')}</Th>
            </Tr>
          </Thead>
          <Tbody>
            {files.map(file => (
              <Tr key={file.id}>
                <Td maxW="200px"><Text isTruncated>{file.filename}</Text></Td>
                <Td>{file.language}</Td>
                <Td>
                  {file.max_similarity != null ? (
                    <Badge colorScheme={file.max_similarity >= 0.8 ? 'red' : file.max_similarity >= 0.5 ? 'yellow' : 'green'}>
                      {(file.max_similarity * 100).toFixed(1)}%
                    </Badge>
                  ) : '—'}
                </Td>
                <Td>
                  <Button size="xs" colorScheme="red" onClick={() => onDelete(file.id)}>{t('delete')}</Button>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </TableContainer>
    </Box>
  );
};

const SettingsPanel: React.FC<{ upload: any }> = ({ upload }) => {
  const { t } = useTranslation(['common', 'upload', 'languages']);
  const toast = useToast();
  const queryClient = useQueryClient();
  const updateUpload = useUpdateUpload();
  const [name, setName] = useState(upload.name || '');
  const [language, setLanguage] = useState(upload.language || 'python');
  const [selectedAssignment, setSelectedAssignment] = useState(upload.assignment_id || '');

  const { data: assignmentsData } = useQuery({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data;
    },
  });
  const assignments = assignmentsData?.items || [];

  const handleSave = async () => {
    try {
      await updateUpload.mutateAsync({
        taskId: upload.task_id,
        name: name || undefined,
        language: language || undefined,
        assignment_id: selectedAssignment || undefined,
      });
      toast({ title: t('upload:settingsSaved'), status: 'success', duration: 2000 });
      queryClient.invalidateQueries({ queryKey: ['uploads', 'details', upload.task_id] });
    } catch {
      toast({ title: t('upload:failedToSaveSettings'), status: 'error', duration: 3000 });
    }
  };

  const languageOptions = [
    { value: 'python', label: t('languages:python') },
    { value: 'java', label: t('languages:java') },
    { value: 'cpp', label: t('languages:cpp') },
    { value: 'c', label: t('languages:c') },
    { value: 'javascript', label: t('languages:javascript') },
    { value: 'go', label: t('languages:go') },
    { value: 'rust', label: t('languages:rust') },
  ];

  return (
    <VStack align="stretch" spacing={4} maxW="600px">
      <Box>
        <Text fontWeight="medium" mb={1}>{t('upload:nameLabel')}</Text>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('upload:uploadName')} />
      </Box>

      <Box>
        <Text fontWeight="medium" mb={1}>{t('upload:languageLabel')}</Text>
        <Select value={language} onChange={(e) => setLanguage(e.target.value)}>
          {languageOptions.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </Select>
      </Box>

      <Box>
        <Text fontWeight="medium" mb={1}>{t('upload:assignmentLabel')}</Text>
        <Select value={selectedAssignment} onChange={(e) => setSelectedAssignment(e.target.value)} placeholder={t('upload:noAssignment')}>
          {assignments.map((a: any) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </Select>
      </Box>

      <Button colorScheme="brand" onClick={handleSave} isLoading={updateUpload.isPending}>
        {t('upload:saveChanges')}
      </Button>

      <Box mt={4} pt={4} borderTopWidth={1} borderColor="gray.200">
        <Text fontSize="sm" color="gray.500">{t('upload:createdLabel')}{new Date(upload.created_at).toLocaleString()}</Text>
        <Text fontSize="sm" color="gray.500">{t('upload:statusLabel')}{upload.status}</Text>
        <Text fontSize="sm" color="gray.500">{t('upload:uploadIdLabel')}{upload.task_id}</Text>
      </Box>
    </VStack>
  );
};

export default UploadDetail;
