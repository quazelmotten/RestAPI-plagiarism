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
  const { t } = useTranslation();
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
      toast({ title: 'Upload deleted', status: 'success', duration: 2000 });
      navigate('/dashboard/uploads');
    } catch {
      toast({ title: 'Failed to delete upload', status: 'error', duration: 3000 });
    }
    setDeleteConfirmOpen(false);
  };

  const handleReanalyze = async () => {
    if (!uploadId) return;
    try {
      await reanalyzeUpload.mutateAsync({ taskId: uploadId });
      toast({ title: 'Reanalysis started', status: 'info', duration: 2000 });
    } catch {
      toast({ title: 'Failed to reanalyze', status: 'error', duration: 3000 });
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    if (!uploadId) return;
    try {
      await deleteFile.mutateAsync({ taskId: uploadId, fileId });
      toast({ title: 'File deleted', status: 'success', duration: 2000 });
    } catch {
      toast({ title: 'Failed to delete file', status: 'error', duration: 3000 });
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
        <Text fontSize="lg" color="gray.500">Upload not found</Text>
        <Button mt={4} onClick={() => navigate('/dashboard/uploads')}>Back to Uploads</Button>
      </Flex>
    );
  }

  const isProcessing = ['queued', 'indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results', 'processing'].includes(upload.status);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return <Badge colorScheme="green">Completed</Badge>;
      case 'queued': return <Badge colorScheme="yellow">Queued</Badge>;
      case 'processing':
      case 'indexing':
      case 'finding_intra_pairs':
      case 'finding_cross_pairs':
      case 'storing_results': return <Badge colorScheme="blue">Processing</Badge>;
      case 'failed':
      case 'error': return <Badge colorScheme="red">Error</Badge>;
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
            aria-label="Back"
            size="sm"
            variant="ghost"
            onClick={() => navigate('/dashboard/uploads')}
          />
          <Text fontSize="2xl" fontWeight="bold" noOfLines={1}>
            {upload.name || `Upload ${upload.task_id.substring(0, 8)}`}
          </Text>
          {getStatusBadge(upload.status)}
        </HStack>
        <HStack>
          {upload.status === 'completed' && (
            <Button size="sm" leftIcon={<FiRefreshCw />} onClick={handleReanalyze}>
              Reanalyze
            </Button>
          )}
          <Button size="sm" colorScheme="red" leftIcon={<FiTrash2 />} onClick={() => setDeleteConfirmOpen(true)}>
            Delete
          </Button>
        </HStack>
      </Flex>

      {/* Stats row */}
      <HStack spacing={{ base: 2, md: 6 }} fontSize="sm" color="gray.500" wrap="wrap">
        <Text><strong>{files?.length || 0}</strong> files</Text>
        {upload.language && <Text><strong>{upload.language}</strong></Text>}
        {upload.total_pairs > 0 && <Text><strong>{upload.total_pairs}</strong> pairs</Text>}
        {upload.high_similarity_count > 0 && (
          <Text color="red.500"><strong>{upload.high_similarity_count}</strong> high similarity</Text>
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
          <Tab>Results</Tab>
          <Tab>Files</Tab>
          <Tab>Settings</Tab>
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
                <Text color="gray.500">No results available</Text>
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
            <AlertDialogHeader>Delete Upload</AlertDialogHeader>
            <AlertDialogBody>
              This will permanently delete {files?.length || 0} files and all similarity results. This cannot be undone.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={() => setDeleteConfirmOpen(false)}>Cancel</Button>
              <Button colorScheme="red" onClick={handleDelete} ml={3} isLoading={deleteUpload.isPending}>
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
};

const FilesTable: React.FC<{ files: UploadFile[]; onDelete: (fileId: string) => void }> = ({ files, onDelete }) => {
  const bg = useColorModeValue('white', 'gray.700');

  return (
    <Box flex={1} overflow="hidden" display="flex" flexDirection="column">
      <TableContainer flex={1} overflowY="auto" overflowX="auto" bg={bg} borderRadius="md">
        <Table size="sm" minW="500px">
          <Thead>
            <Tr>
              <Th>Filename</Th>
              <Th>Language</Th>
              <Th>Max Similarity</Th>
              <Th>Actions</Th>
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
                  <Button size="xs" colorScheme="red" onClick={() => onDelete(file.id)}>Delete</Button>
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
  const { t } = useTranslation();
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
      toast({ title: 'Settings saved', status: 'success', duration: 2000 });
      queryClient.invalidateQueries({ queryKey: ['uploads', 'details', upload.task_id] });
    } catch {
      toast({ title: 'Failed to save', status: 'error', duration: 3000 });
    }
  };

  const languageOptions = [
    { value: 'python', label: 'Python' },
    { value: 'java', label: 'Java' },
    { value: 'cpp', label: 'C++' },
    { value: 'c', label: 'C' },
    { value: 'javascript', label: 'JavaScript' },
    { value: 'go', label: 'Go' },
    { value: 'rust', label: 'Rust' },
  ];

  return (
    <VStack align="stretch" spacing={4} maxW="600px">
      <Box>
        <Text fontWeight="medium" mb={1}>Name</Text>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Upload name" />
      </Box>

      <Box>
        <Text fontWeight="medium" mb={1}>Language</Text>
        <Select value={language} onChange={(e) => setLanguage(e.target.value)}>
          {languageOptions.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </Select>
      </Box>

      <Box>
        <Text fontWeight="medium" mb={1}>Assignment</Text>
        <Select value={selectedAssignment} onChange={(e) => setSelectedAssignment(e.target.value)} placeholder="No assignment">
          {assignments.map((a: any) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </Select>
      </Box>

      <Button colorScheme="brand" onClick={handleSave} isLoading={updateUpload.isPending}>
        Save Changes
      </Button>

      <Box mt={4} pt={4} borderTopWidth={1} borderColor="gray.200">
        <Text fontSize="sm" color="gray.500">Created: {new Date(upload.created_at).toLocaleString()}</Text>
        <Text fontSize="sm" color="gray.500">Status: {upload.status}</Text>
        <Text fontSize="sm" color="gray.500">Upload ID: {upload.task_id}</Text>
      </Box>
    </VStack>
  );
};

export default UploadDetail;
