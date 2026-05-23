import React, { useState, useCallback, useMemo } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router';
import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  Badge,
  Button,
  IconButton,
  Select,
  Input,
  InputGroup,
  InputLeftElement,
  Progress,
  Card,
  CardBody,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  useColorModeValue,
  useToast,
  Spinner,
  Icon,
  Collapse,
  Checkbox,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Alert,
  AlertIcon,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiUploadCloud, FiFile, FiX, FiSearch, FiMoreVertical, FiTrash2, FiRefreshCw, FiFolder, FiEdit2, FiDownload, FiChevronDown, FiChevronUp, FiHardDrive } from 'react-icons/fi';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../../services/api';
import { useUploads, useDeleteUpload, useReanalyzeUpload, useUpdateUpload, useUploadFiles, useDeleteUploadFile, useMoveFile } from '../../hooks/useUploadQueries';
import type { UploadListItem } from '../../types';
import TaskProgress from '../../components/Results/TaskProgress';

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const MAX_FILES = 1000;

const getFileExtension = (filename: string): string => {
  const parts = filename.split('.');
  return parts.length > 1 ? parts.pop()!.toLowerCase() : '';
};

const getFileKey = (file: File): string => `${file.name}-${file.size}-${file.lastModified}`;

const formatFileSize = (bytes: number): string => {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
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
};

const languageOptions = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'cpp', label: 'C++' },
  { value: 'c', label: 'C' },
  { value: 'java', label: 'Java' },
  { value: 'go', label: 'Go' },
  { value: 'rust', label: 'Rust' },
];

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

const getSimilarityBadge = (similarity: number | null) => {
  if (similarity == null) return <Text fontSize="xs" color="gray.400">—</Text>;
  if (similarity >= 0.8) return <Badge colorScheme="red">{(similarity * 100).toFixed(1)}%</Badge>;
  if (similarity >= 0.5) return <Badge colorScheme="yellow">{(similarity * 100).toFixed(1)}%</Badge>;
  return <Badge colorScheme="green">{(similarity * 100).toFixed(1)}%</Badge>;
};

const getLanguageBadge = (language: string | null | undefined) => {
  if (!language) return null;
  return <Badge variant="subtle" colorScheme="gray" fontSize="xs">{language}</Badge>;
};

const COLUMN_ICONS = {
  filename: FiFile,
  language: null,
  similarity: null,
  confirmed: null,
  actions: null,
} as const;

// --- Expanded file list for an upload ---

interface ExpandedUploadFilesProps {
  files: any[];
  upload: UploadListItem;
  reanalyzeUpload: (taskId: string) => void;
}

const ExpandedUploadFiles: React.FC<ExpandedUploadFilesProps> = ({ files, upload, reanalyzeUpload }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const deleteFile = useDeleteUploadFile();
  const moveFile = useMoveFile();
  const { isOpen: isBulkDeleteOpen, onOpen: onBulkDeleteOpen, onClose: onBulkDeleteClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [moveTargetUpload, setMoveTargetUpload] = useState('');
  const { data: allUploadsData } = useQuery({
    queryKey: ['uploads-list-all'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.UPLOADS, { params: { limit: 500 } });
      return res.data;
    },
  });
  const allUploads = allUploadsData?.items || [];
  const otherUploads: UploadListItem[] = allUploads.filter((u: UploadListItem) => u.task_id !== upload.task_id && u.status === 'completed');

  const handleSelectFile = useCallback((fileId: string, selected: boolean) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (selected) next.add(fileId);
      else next.delete(fileId);
      return next;
    });
  }, []);

  const handleSelectAllFiles = useCallback(() => {
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(files.map((f: any) => f.id)));
    }
  }, [files, selectedFiles.size]);

  const handleSingleDelete = async (fileId: string) => {
    try {
      await deleteFile.mutateAsync({ taskId: upload.task_id, fileId });
      toast({ title: 'File deleted', status: 'success', duration: 2000 });
    } catch {
      toast({ title: 'Failed to delete file', status: 'error', duration: 3000 });
    }
  };

  const handleSingleMove = (fileId: string, targetTaskId: string) => {
    moveFile.mutate(
      { fileId, targetTaskId },
      {
        onSuccess: () => {
          toast({ title: 'File moved — reanalyzing destination upload…', status: 'success', duration: 3000 });
          reanalyzeUpload(targetTaskId);
        },
        onError: () => toast({ title: 'Failed to move file', status: 'error', duration: 3000 }),
      }
    );
  };

  const handleBulkDelete = () => {
    onBulkDeleteOpen();
  };

  const confirmBulkDelete = async () => {
    for (const fileId of selectedFiles) {
      try {
        await deleteFile.mutateAsync({ taskId: upload.task_id, fileId });
      } catch {
        // continue
      }
    }
    setSelectedFiles(new Set());
    toast({ title: `${selectedFiles.size} files deleted`, status: 'success', duration: 3000 });
    onBulkDeleteClose();
  };

  const handleBulkMove = () => {
    if (!moveTargetUpload) return;
    for (const fileId of selectedFiles) {
      handleSingleMove(fileId, moveTargetUpload);
    }
    setSelectedFiles(new Set());
    setMoveTargetUpload('');
  };

  return (
    <Box mt={3} borderTop="1px" borderColor="gray.200" pt={3}>
      {/* File count info */}
      <HStack spacing={4} mb={2} fontSize="sm" color="gray.500">
        <HStack spacing={1}>
          <Icon as={FiFile} boxSize={3} />
          <Text>{files.length} file{files.length !== 1 ? 's' : ''}</Text>
        </HStack>
      </HStack>

      {/* File table */}
      <Box overflowX="auto" maxH="400px" overflowY="auto" borderWidth="1px" borderColor="gray.200" borderRadius="md" mb={2}>
        <Table size="sm">
          <Thead position="sticky" top={0} bg={useColorModeValue('gray.50', 'gray.700')} zIndex={1}>
            <Tr>
              <Th w="40px">
                <Checkbox isChecked={files.length > 0 && selectedFiles.size === files.length} onChange={handleSelectAllFiles} />
              </Th>
              <Th>Filename</Th>
              <Th>Language</Th>
              <Th>Similarity</Th>
              <Th>Confirmed</Th>
              <Th w="160px">Actions</Th>
            </Tr>
          </Thead>
          <Tbody>
            {files.map((file: any) => (
              <Tr key={file.id}>
                <Td>
                  <Checkbox isChecked={selectedFiles.has(file.id)} onChange={(e) => handleSelectFile(file.id, e.target.checked)} />
                </Td>
                <Td>
                  <HStack spacing={2}>
                    <Icon as={FiFile} boxSize={3.5} color="gray.400" />
                    <Text fontSize="xs" isTruncated maxW="400px" title={file.filename}>{file.filename}</Text>
                  </HStack>
                </Td>
                <Td>{getLanguageBadge(file.language)}</Td>
                <Td>{getSimilarityBadge(file.max_similarity)}</Td>
                <Td>
                  {file.is_confirmed ? (
                    <Badge colorScheme="green" variant="subtle" fontSize="xs">Confirmed</Badge>
                  ) : (
                    <Badge colorScheme="gray" variant="subtle" fontSize="xs">Unreviewed</Badge>
                  )}
                </Td>
                <Td>
                  <HStack spacing={1}>
                    <Select
                      size="xs"
                      w="150px"
                      placeholder="Move to..."
                      onChange={(e) => {
                        if (e.target.value) handleSingleMove(file.id, e.target.value);
                        e.currentTarget.value = '';
                      }}
                      isDisabled={moveFile.isPending}
                    >
                      {otherUploads.map(u => (
                        <option key={u.task_id} value={u.task_id}>
                          {u.name || `Upload ${u.task_id.substring(0, 8)}`}
                        </option>
                      ))}
                    </Select>
                    <IconButton as={FiTrash2} size="xs" variant="ghost" color="red.500" aria-label="Delete file" onClick={() => handleSingleDelete(file.id)} />
                  </HStack>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>

      {files.length === 0 && (
        <Alert status="info" borderRadius="md" mb={3}>
          <AlertIcon />
          <Text fontSize="sm">No files in this upload</Text>
        </Alert>
      )}

      {/* Selected files bar - fixed position */}
      {selectedFiles.size > 0 && (
        <Box
          mt={2}
          bg="brand.50"
          borderColor="brand.200"
          borderWidth={1}
          borderRadius="md"
        >
          <HStack spacing={3} p={2} wrap="wrap" align="center">
            <Text fontSize="sm" fontWeight="bold" color="brand.700">
              {selectedFiles.size} file{selectedFiles.size > 1 ? 's' : ''} selected
            </Text>
            <Button
              size="xs"
              colorScheme="red"
              leftIcon={<FiTrash2 />}
              onClick={handleBulkDelete}
              isLoading={deleteFile.isPending}
            >
              Delete
            </Button>
            <HStack spacing={2}>
              <Select
                size="xs"
                w="200px"
                placeholder="Move to upload..."
                value={moveTargetUpload}
                onChange={(e) => setMoveTargetUpload(e.target.value)}
              >
                {otherUploads.map(u => (
                  <option key={u.task_id} value={u.task_id}>
                    {u.name || `Upload ${u.task_id.substring(0, 8)}`}
                  </option>
                ))}
              </Select>
              <Button
                size="xs"
                colorScheme="purple"
                leftIcon={<FiFolder />}
                onClick={handleBulkMove}
                isDisabled={!moveTargetUpload}
                isLoading={moveFile.isPending}
              >
                Move
              </Button>
            </HStack>
            <Button size="xs" variant="ghost" onClick={() => setSelectedFiles(new Set())}>
              Clear
            </Button>
          </HStack>
        </Box>
      )}

      {/* Bulk delete confirmation dialog */}
      <AlertDialog
        isOpen={isBulkDeleteOpen}
        leastDestructiveRef={cancelRef as React.RefObject<HTMLButtonElement>}
        onClose={onBulkDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete {selectedFiles.size} File{selectedFiles.size > 1 ? 's' : ''}
            </AlertDialogHeader>
            <AlertDialogBody>
              This will permanently delete {selectedFiles.size} file{selectedFiles.size > 1 ? 's' : ''} and their analysis data from this upload. This action cannot be undone.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkDeleteClose} isDisabled={deleteFile.isPending}>Cancel</Button>
              <Button colorScheme="red" onClick={confirmBulkDelete} ml={3} isLoading={deleteFile.isPending}>Delete</Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

// --- Upload Card ---

const UploadCard: React.FC<{
  upload: UploadListItem;
  isSelected?: boolean;
  onSelect?: (taskId: string, selected: boolean) => void;
  onManageFiles?: (taskId: string) => void;
  expandedTaskId: string | null;
  onManageExpand?: (taskId: string) => void;
}> = ({ upload, isSelected, onSelect, expandedTaskId, onManageExpand }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const deleteUpload = useDeleteUpload();
  const reanalyzeUpload = useReanalyzeUpload();
  const updateUpload = useUpdateUpload();
  const [showActions, setShowActions] = useState(false);

  const isExpanded = expandedTaskId === upload.task_id;
  const isProcessing = ['queued', 'indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results', 'processing'].includes(upload.status);

  const handleDelete = async () => {
    try {
      await deleteUpload.mutateAsync(upload.task_id);
      toast({ title: 'Upload deleted', status: 'success', duration: 2000 });
    } catch {
      toast({ title: 'Failed to delete upload', status: 'error', duration: 3000 });
    }
  };

  const handleReanalyze = async () => {
    try {
      await reanalyzeUpload.mutateAsync({ taskId: upload.task_id });
      toast({ title: 'Reanalysis started', status: 'info', duration: 2000 });
    } catch {
      toast({ title: 'Failed to reanalyze', status: 'error', duration: 3000 });
    }
  };

  const handleMove = async (assignmentId: string) => {
    try {
      await updateUpload.mutateAsync({
        taskId: upload.task_id,
        assignment_id: assignmentId,
      });
      toast({ title: 'Upload moved', status: 'success', duration: 2000 });
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    } catch {
      toast({ title: 'Failed to move upload', status: 'error', duration: 3000 });
    }
  };

  const toggleExpand = () => {
    onManageExpand?.(isExpanded ? '' : upload.task_id);
  };

  return (
    <Card mb={2} borderColor={isProcessing ? 'blue.300' : 'gray.200'} borderWidth={isProcessing ? 2 : 1} bg={isSelected ? 'brand.50' : undefined} py={1}>
      <CardBody py={2}>
        <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" align="center" gap={2}>
          {onSelect && (
            <Checkbox
              isChecked={isSelected}
              onChange={(e) => onSelect(upload.task_id, e.target.checked)}
            />
          )}
          <Box flex={1} minW={0}>
            <HStack spacing={2} cursor={onManageExpand ? 'pointer' : 'default'} onClick={onManageExpand ? toggleExpand : undefined}>
              <Text fontWeight="semibold" fontSize="sm" noOfLines={1}>
                {upload.name || `Upload ${upload.task_id.substring(0, 8)}`}
              </Text>
              {getStatusBadge(upload.status)}
              {getSimilarityBadge(upload.similarity)}
              {onManageExpand && (
                <Icon as={isExpanded ? FiChevronUp : FiChevronDown} boxSize={3} color="gray.400" />
              )}
            </HStack>

            <HStack spacing={3} fontSize="xs" color="gray.500" mt={1} wrap="wrap">
              <HStack spacing={1} cursor={onManageExpand ? 'pointer' : 'default'} onClick={onManageExpand ? toggleExpand : undefined}>
                <Icon as={FiHardDrive} boxSize={2.5} />
                <Text>{upload.files_count} files</Text>
              </HStack>
              {upload.language && <Text>{upload.language}</Text>}
              {upload.total_pairs > 0 && <Text>{upload.total_pairs} pairs</Text>}
              {upload.high_similarity_count > 0 && (
                <Text color="red.500" fontWeight="medium">{upload.high_similarity_count} high</Text>
              )}
              {upload.assignment_name && (
                <>
                  <Icon as={FiFolder} boxSize={2} color="purple.500" />
                  <Text fontSize="xs" color="purple.600">{upload.assignment_name}</Text>
                </>
              )}
            </HStack>

            {isProcessing && (
              <Box mt={1}>
                <TaskProgress
                  taskId={upload.task_id}
                  status={upload.status}
                  onCompleted={() => queryClient.invalidateQueries({ queryKey: ['uploads'] })}
                />
              </Box>
            )}

            {upload.error && (
              <Text fontSize="xs" color="red.500" mt={1}>{upload.error}</Text>
            )}
          </Box>

          <HStack spacing={1} flexShrink={0}>
            <Menu>
              <MenuButton
                as={IconButton}
                icon={<FiMoreVertical />}
                size="xs"
                variant="ghost"
                aria-label="Actions"
              />
              <MenuList>
                <MenuItem onClick={toggleExpand}>
                  {isExpanded ? '▲ Hide files' : '▼ Manage files'}
                </MenuItem>
                <MenuItem icon={<FiRefreshCw />} onClick={handleReanalyze}>
                  Reanalyze
                </MenuItem>
                <MenuItem icon={<FiTrash2 />} color="red.500" onClick={handleDelete}>
                  Delete
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </Flex>
      </CardBody>
    </Card>
  );
};

// --- New Upload Inline ---

const NewUploadInline: React.FC<{ onSuccess: () => void; assignments?: { id: string; name: string }[] }> = ({ onSuccess, assignments }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [files, setFiles] = useState<File[]>([]);
  const [language, setLanguage] = useState('auto');
  const [uploadName, setUploadName] = useState('');
  const [selectedAssignment, setSelectedAssignment] = useState('');
  const [uploading, setUploading] = useState(false);

  const onDrop = useCallback((accepted: File[], rejected: { file: File }[]) => {
    const newFiles = [...files];
    for (const file of accepted) {
      if (newFiles.length >= MAX_FILES) break;
      if (file.size > MAX_FILE_SIZE) {
        toast({ title: `File too large: ${file.name}`, status: 'warning', duration: 3000 });
        continue;
      }
      const key = getFileKey(file);
      if (!newFiles.some(f => getFileKey(f) === key)) {
        newFiles.push(file);
      }
    }
    for (const rej of rejected) {
      toast({ title: `Rejected: ${rej.file.name}`, status: 'error', duration: 3000 });
    }
    setFiles(newFiles);
  }, [files, toast]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/x-python': ['.py'],
      'text/x-java-source': ['.java'],
      'text/javascript': ['.js'],
      'text/x-c': ['.c', '.cpp', '.h'],
      'text/x-go': ['.go'],
      'text/x-rust': ['.rs'],
    },
  });

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    try {
      const formData = new FormData();
      for (const file of files) {
        formData.append('files', file);
      }
      if (uploadName) formData.append('name', uploadName);
      if (language !== 'auto') formData.append('language', language);
      if (selectedAssignment) formData.append('assignment_id', selectedAssignment);

      await api.post(API_ENDPOINTS.UPLOADS, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      toast({ title: 'Upload started', status: 'success', duration: 2000 });
      setFiles([]);
      setUploadName('');
      onSuccess();
    } catch (err: any) {
      toast({ title: err.response?.data?.detail || 'Upload failed', status: 'error', duration: 3000 });
    } finally {
      setUploading(false);
    }
  };

  const cardBg = useColorModeValue('white', 'gray.700');
  const dropBg = useColorModeValue('gray.50', 'gray.600');
  const dropBorder = useColorModeValue('gray.300', 'gray.500');

  return (
    <Card mb={4} bg={cardBg}>
      <CardBody>
        <VStack spacing={4} align="stretch">
          <HStack spacing={3} wrap="wrap">
            <Input
              placeholder="Upload name (optional)"
              value={uploadName}
              onChange={(e) => setUploadName(e.target.value)}
              size="sm"
              flex={{ base: 1, md: 'auto' }}
              minW={{ base: 'full', md: '200px' }}
            />
            <Select value={language} onChange={(e) => setLanguage(e.target.value)} size="sm" w={{ base: 'full', md: '180px' }}>
              {languageOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </Select>
            {assignments && assignments.length > 0 && (
              <Select
                value={selectedAssignment}
                onChange={(e) => setSelectedAssignment(e.target.value)}
                size="sm"
                w={{ base: 'full', md: '220px' }}
                placeholder="Link to assignment..."
              >
                {assignments.map(a => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </Select>
            )}
          </HStack>

          <Box
            {...getRootProps()}
            p={6}
            bg={isDragActive ? 'brand.50' : dropBg}
            border="2px dashed"
            borderColor={isDragActive ? 'brand.400' : dropBorder}
            borderRadius="md"
            textAlign="center"
            cursor="pointer"
            transition="all 0.2s"
          >
            <input {...getInputProps()} />
            <Icon as={FiUploadCloud} boxSize={8} color="brand.500" mb={2} />
            <Text fontWeight="medium">
              {isDragActive ? 'Drop files here' : 'Drag files here or click to browse'}
            </Text>
            <Text fontSize="xs" color="gray.500">
              Max {MAX_FILES} files, {formatFileSize(MAX_FILE_SIZE)} each
            </Text>
          </Box>

          {files.length > 0 && (
            <VStack align="stretch" maxH="200px" overflowY="auto">
              {files.map((file, i) => (
                <HStack key={i} justify="space-between" px={2} py={1} bg="gray.50" borderRadius="sm">
                  <HStack>
                    <Icon as={FiFile} boxSize={4} color="gray.500" />
                    <Text fontSize="sm" noOfLines={1}>{file.name}</Text>
                    <Text fontSize="xs" color="gray.400">{formatFileSize(file.size)}</Text>
                  </HStack>
                  <IconButton
                    icon={<FiX />}
                    size="xs"
                    variant="ghost"
                    aria-label="Remove"
                    onClick={() => removeFile(i)}
                  />
                </HStack>
              ))}
            </VStack>
          )}

          <Flex justify="flex-end">
            <Button
              colorScheme="brand"
              onClick={handleUpload}
              isDisabled={files.length === 0 || uploading}
              isLoading={uploading}
            >
              Start Analysis ({files.length} files)
            </Button>
          </Flex>
        </VStack>
      </CardBody>
    </Card>
  );
};

// --- Main Uploads Page ---

const Uploads: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [assignmentFilter, setAssignmentFilter] = useState('');
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkMoveAssignment, setBulkMoveAssignment] = useState('');
  const [bulkReanalyzeLanguage, setBulkReanalyzeLanguage] = useState('auto');
  const { data: uploadsData, isLoading } = useUploads({ limit: 100, assignment_id: assignmentFilter || undefined });
  const { data: uploadFilesQuery } = useUploadFiles(expandedTaskId || undefined);
  const { data: assignmentsData } = useQuery({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data;
    },
  });

  const { isOpen: isBulkDeleteOpen, onOpen: onBulkDeleteOpen, onClose: onBulkDeleteClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const [showUpload, setShowUpload] = useState(false);

  const uploads = uploadsData?.items || [];
  const assignments = assignmentsData?.items || [];
  const expandedFiles = uploadFilesQuery || [];
  const expandedUpload = uploads.find((u: UploadListItem) => u.task_id === expandedTaskId);

  const filtered = useMemo(() => {
    if (!search) return uploads;
    const q = search.toLowerCase();
    return uploads.filter(u =>
      (u.name || '').toLowerCase().includes(q) ||
      u.task_id.toLowerCase().includes(q) ||
      (u.assignment_name || '').toLowerCase().includes(q)
    );
  }, [uploads, search]);

  const handleSelect = useCallback((taskId: string, selectedState: boolean) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (selectedState) next.add(taskId);
      else next.delete(taskId);
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    if (selected.size === filtered.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filtered.map((u: UploadListItem) => u.task_id)));
    }
  }, [filtered, selected.size]);

  const bulkDeleteMutation = useMutation({
    mutationFn: async (taskIds: string[]) => {
      const results = await Promise.allSettled(
        taskIds.map(id => api.delete(API_ENDPOINTS.DELETE_UPLOAD(id)))
      );
      const failed = results.filter(r => r.status === 'rejected');
      if (failed.length > 0) throw new Error(`${failed.length} deletions failed`);
      return { count: taskIds.length };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      setSelected(new Set());
      if (expandedTaskId && selected.has(expandedTaskId)) setExpandedTaskId(null);
      toast({
        title: `${data.count} upload${data.count > 1 ? 's' : ''} deleted`,
        status: 'success',
        duration: 3000,
      });
      onBulkDeleteClose();
    },
    onError: () => {
      toast({ title: 'Some deletions failed', status: 'error', duration: 3000 });
    },
  });

  const bulkMoveMutation = useMutation({
    mutationFn: async ({ taskIds, assignmentId }: { taskIds: string[]; assignmentId: string }) => {
      let moved = 0;
      for (const id of taskIds) {
        await api.patch(API_ENDPOINTS.UPDATE_UPLOAD(id), { assignment_id: assignmentId });
        moved++;
      }
      return { count: moved };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      setSelected(new Set());
      toast({
        title: `${data.count} upload${data.count > 1 ? 's' : ''} moved`,
        status: 'success',
        duration: 3000,
      });
    },
    onError: () => {
      toast({ title: 'Some moves failed', status: 'error', duration: 3000 });
    },
  });

  const bulkReanalyzeMutation = useMutation({
    mutationFn: async ({ taskIds, language }: { taskIds: string[]; language?: string }) => {
      let reanalyzed = 0;
      for (const id of taskIds) {
        await api.post(API_ENDPOINTS.REANALYZE_UPLOAD(id), language !== 'auto' ? { language } : {});
        reanalyzed++;
      }
      return { count: reanalyzed };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      setSelected(new Set());
      toast({
        title: `${data.count} upload${data.count > 1 ? 's' : ''} reanalyzing`,
        status: 'info',
        duration: 3000,
      });
    },
    onError: () => {
      toast({ title: 'Some reanalyses failed', status: 'error', duration: 3000 });
    },
  });

  const handleBulkDelete = () => {
    bulkDeleteMutation.mutate(Array.from(selected));
  };

  const handleBulkMove = () => {
    if (!bulkMoveAssignment) {
      toast({ title: 'Select an assignment', status: 'warning', duration: 2000 });
      return;
    }
    bulkMoveMutation.mutate({ taskIds: Array.from(selected), assignmentId: bulkMoveAssignment });
  };

  const handleBulkReanalyze = () => {
    bulkReanalyzeMutation.mutate({
      taskIds: Array.from(selected),
      language: bulkReanalyzeLanguage === 'auto' ? undefined : bulkReanalyzeLanguage,
    });
  };

  const handleExpand = useCallback((taskId: string) => {
    setExpandedTaskId(prev => prev === taskId ? null : taskId);
  }, []);

  const handleReanalyzeDestination = useCallback((taskId: string) => {
    const reanalyze = useReanalyzeUpload();
    reanalyze.mutate(
      { taskId },
      {
        onSuccess: () => {
          toast({ title: 'Reanalyzing destination upload…', status: 'info', duration: 3000 });
          queryClient.invalidateQueries({ queryKey: ['uploads'] });
        },
        onError: () => toast({ title: 'Failed to reanalyze destination upload', status: 'error', duration: 3000 }),
      }
    );
  }, [queryClient, toast]);

  const isAnyBulkLoading = bulkDeleteMutation.isPending || bulkMoveMutation.isPending || bulkReanalyzeMutation.isPending;

  return (
    <VStack align="stretch" spacing={6} flex={1} overflow="hidden">
      <Flex justify="space-between" align="center">
        <Text fontSize="2xl" fontWeight="bold">{t('uploads')}</Text>
        <Button colorScheme="brand" leftIcon={<FiUploadCloud />} onClick={() => setShowUpload(!showUpload)}>
          {showUpload ? 'Hide' : 'New Upload'}
        </Button>
      </Flex>

      {showUpload && (
        <NewUploadInline
          onSuccess={() => setShowUpload(false)}
          assignments={assignments}
        />
      )}

      {selected.size > 0 && (
        <Card bg="brand.50" borderColor="brand.200" borderWidth={1}>
          <CardBody py={3}>
            <HStack spacing={3} wrap="wrap">
              <Text fontSize="sm" fontWeight="medium">{selected.size} selected</Text>
              <Button size="sm" colorScheme="red" leftIcon={<FiTrash2 />} onClick={onBulkDeleteOpen} isLoading={bulkDeleteMutation.isPending}>
                Delete
              </Button>
              <HStack wrap="wrap">
                <Select size="sm" w={{ base: 'full', md: '200px' }} value={bulkMoveAssignment} onChange={(e) => setBulkMoveAssignment(e.target.value)} placeholder="Move to assignment...">
                  {assignments.map((a: any) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </Select>
                <Button size="sm" colorScheme="purple" leftIcon={<FiFolder />} onClick={handleBulkMove} isLoading={bulkMoveMutation.isPending} isDisabled={!bulkMoveAssignment}>
                  Move
                </Button>
              </HStack>
              <HStack wrap="wrap">
                <Select size="sm" w={{ base: 'full', md: '160px' }} value={bulkReanalyzeLanguage} onChange={(e) => setBulkReanalyzeLanguage(e.target.value)}>
                  <option value="auto">Auto-detect</option>
                  <option value="python">Python</option>
                  <option value="javascript">JavaScript</option>
                  <option value="cpp">C++</option>
                  <option value="java">Java</option>
                  <option value="go">Go</option>
                  <option value="rust">Rust</option>
                </Select>
                <Button size="sm" leftIcon={<FiRefreshCw />} onClick={handleBulkReanalyze} isLoading={bulkReanalyzeMutation.isPending}>
                  Reanalyze
                </Button>
              </HStack>
              <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>Clear</Button>
            </HStack>
          </CardBody>
        </Card>
      )}

      <HStack justify="space-between" wrap="wrap" spacing={2}>
        <HStack spacing={2} flex={{ base: 1, md: 'auto' }}>
          <InputGroup maxW={{ base: 'full', md: '250px' }}>
            <InputLeftElement pointerEvents="none">
              <Icon as={FiSearch} color="gray.400" />
            </InputLeftElement>
            <Input placeholder="Search uploads..." value={search} onChange={(e) => setSearch(e.target.value)} size="sm" />
          </InputGroup>
          <Select size="sm" w={{ base: 'full', md: '180px' }} placeholder="All assignments" value={assignmentFilter} onChange={(e) => setAssignmentFilter(e.target.value)}>
            {assignments.map((a: any) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </Select>
        </HStack>
        {filtered.length > 0 && (
          <Checkbox isChecked={selected.size === filtered.length && filtered.length > 0} onChange={handleSelectAll}>
            Select all
          </Checkbox>
        )}
      </HStack>

      <Box flex={1} overflowY="auto" css={{ '&::-webkit-scrollbar': { width: '6px' }, '&::-webkit-scrollbar-thumb': { bg: 'gray.300', borderRadius: '3px' } }}>
        {isLoading ? (
          <Flex justify="center" py={8}><Spinner size="lg" /></Flex>
        ) : filtered.length === 0 ? (
          <Flex justify="center" py={8} flexDirection="column" align="center">
            <Icon as={FiUploadCloud} boxSize={12} color="gray.300" mb={4} />
            <Text color="gray.500" fontSize="lg">No uploads yet</Text>
            <Text color="gray.400" fontSize="sm">Click "New Upload" to get started</Text>
          </Flex>
        ) : (
          filtered.map(upload => (
            <React.Fragment key={upload.task_id}>
              <UploadCard
                upload={upload}
                isSelected={selected.has(upload.task_id)}
                onSelect={handleSelect}
                onManageExpand={handleExpand}
                expandedTaskId={expandedTaskId}
              />
              {expandedTaskId === upload.task_id && (
                <ExpandedUploadFiles upload={upload} files={expandedFiles as any} reanalyzeUpload={handleReanalyzeDestination} />
              )}
            </React.Fragment>
          ))
        )}
      </Box>

      <AlertDialog isOpen={isBulkDeleteOpen} leastDestructiveRef={cancelRef as React.RefObject<HTMLButtonElement>} onClose={onBulkDeleteClose}>
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete {selected.size} Upload{selected.size > 1 ? 's' : ''}
            </AlertDialogHeader>
            <AlertDialogBody>
              This will permanently delete {selected.size} upload{selected.size > 1 ? 's' : ''} including all files, results, and similarity pairs. This action cannot be undone.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkDeleteClose} isDisabled={isAnyBulkLoading}>Cancel</Button>
              <Button colorScheme="red" onClick={handleBulkDelete} ml={3} isLoading={bulkDeleteMutation.isPending}>Delete</Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
};

export default Uploads;
