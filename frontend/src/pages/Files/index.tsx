import React, { useState, useCallback, useMemo, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
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
  Card,
  CardBody,
  useColorModeValue,
  useToast,
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
  NumberInput,
  NumberInputField,
} from '@chakra-ui/react';
import {
  FiUploadCloud,
  FiFile,
  FiX,
  FiSearch,
  FiTrash2,
  FiMove,
  FiChevronLeft,
  FiChevronRight,
  FiChevronsLeft,
  FiChevronsRight,
} from 'react-icons/fi';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../../services/api';
import { useAllFiles, useDeleteFile, useFileIds, useBulkMoveByAssignment } from '../../hooks/useFileQueries';
import { useDebounce } from '../../hooks/useDebounce';
import { useSubjectsWithAssignments } from '../../hooks/useSubjects';
import type { FileListItem } from '../../types';
import { AssignmentFilter } from '../../components/Review/AssignmentFilter';

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const MAX_FILES = 1000;
const PAGE_SIZE = 200;

const formatFileSize = (bytes: number): string => {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
};

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
};

const getFileKey = (file: File): string => `${file.name}-${file.size}-${file.lastModified}`;

const languageOptions = (t: (key: string) => string) => [
  { value: '', label: t('files:filterLabels.allLanguages') },
  { value: 'python', label: t('languages:python') },
  { value: 'javascript', label: t('languages:javascript') },
  { value: 'typescript', label: t('languages:typescript') },
  { value: 'cpp', label: t('languages:cpp') },
  { value: 'c', label: t('languages:c') },
  { value: 'java', label: t('languages:java') },
  { value: 'go', label: t('languages:go') },
  { value: 'rust', label: t('languages:rust') },
];

const statusOptions = (t: (key: string) => string) => [
  { value: '', label: t('files:filterLabels.allStatuses') },
  { value: 'completed', label: t('status:completed') },
  { value: 'processing', label: t('status:processing') },
  { value: 'queued', label: t('status:queued') },
  { value: 'error', label: t('status:error') },
];

const confirmedOptions = (t: (key: string) => string) => [
  { value: '', label: t('files:filterLabels.allFiles') },
  { value: 'confirmed', label: t('files:confirmedBadge') },
  { value: 'unreviewed', label: t('files:unreviewedBadge') },
];

const getSimilarityBadge = (similarity: number | null) => {
  if (similarity == null) return <Text fontSize="xs" color="gray.400">—</Text>;
  if (similarity >= 0.8) return <Badge colorScheme="red" fontSize="xs">{(similarity * 100).toFixed(1)}%</Badge>;
  if (similarity >= 0.5) return <Badge colorScheme="yellow" fontSize="xs">{(similarity * 100).toFixed(1)}%</Badge>;
  return <Badge colorScheme="green" fontSize="xs">{(similarity * 100).toFixed(1)}%</Badge>;
};

const getLanguageBadge = (language: string | null | undefined) => {
  if (!language) return null;
  return <Badge variant="subtle" colorScheme="gray" fontSize="xs">{language}</Badge>;
};

const languageFormOptions = (t: (key: string) => string) => [
  { value: 'auto', label: t('languages:auto') },
  { value: 'python', label: t('languages:python') },
  { value: 'javascript', label: t('languages:javascript') },
  { value: 'typescript', label: t('languages:typescript') },
  { value: 'cpp', label: t('languages:cpp') },
  { value: 'c', label: t('languages:c') },
  { value: 'java', label: t('languages:java') },
  { value: 'go', label: t('languages:go') },
  { value: 'rust', label: t('languages:rust') },
];

// --- File Row ---

interface FileRowProps {
  file: FileListItem;
  isSelected: boolean;
  onSelect: (id: string, selected: boolean) => void;
  onDelete: (id: string) => void;
}

const FileRow: React.FC<FileRowProps> = React.memo(({ file, isSelected, onSelect, onDelete }) => {
  const { t } = useTranslation(['files', 'common', 'status']);
  const navigate = useNavigate();
  const rowBg = useColorModeValue('white', 'gray.800');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');

  return (
    <Tr
      bg={isSelected ? 'brand.50' : rowBg}
      _hover={{ bg: hoverBg }}
      transition="background 0.1s"
    >
      <Td w="40px" px={2}>
        <Checkbox
          isChecked={isSelected}
          onChange={(e) => onSelect(file.id, e.target.checked)}
          size="sm"
        />
      </Td>
      <Td>
        <HStack spacing={2}>
          <Icon as={FiFile} boxSize={3.5} color="gray.400" flexShrink={0} />
          <Text fontSize="sm" isTruncated maxW="320px" title={file.filename}>
            {file.filename}
          </Text>
        </HStack>
      </Td>
      <Td>
        <Text
          fontSize="sm"
          isTruncated
          maxW="200px"
          color="brand.600"
          cursor="pointer"
          title={file.upload_name || file.task_id}
          onClick={() => navigate(`/dashboard/uploads/${file.task_id}`)}
          _hover={{ textDecoration: 'underline' }}
        >
          {file.upload_name || file.task_id.substring(0, 8) + '…'}
        </Text>
      </Td>
      <Td>{getLanguageBadge(file.language)}</Td>
      <Td>{getSimilarityBadge(file.similarity)}</Td>
      <Td>
        {file.is_confirmed ? (
          <Badge colorScheme="green" variant="subtle" fontSize="xs">{t('files:confirmedBadge')}</Badge>
        ) : (
          <Badge colorScheme="gray" variant="subtle" fontSize="xs">{t('files:unreviewedBadge')}</Badge>
        )}
      </Td>
      <Td whiteSpace="nowrap" fontSize="sm" color="gray.500">
        {formatDate(file.created_at)}
      </Td>
      <Td>
        <IconButton
          as={FiTrash2}
          size="xs"
          variant="ghost"
          color="red.400"
          aria-label={t('files:deleteFileLabel')}
          onClick={() => onDelete(file.id)}
        />
      </Td>
    </Tr>
  );
});

FileRow.displayName = 'FileRow';

// --- New Upload Form ---

interface NewUploadFormProps {
  onSuccess: () => void;
  assignments?: { id: string; name: string }[];
}

const NewUploadForm: React.FC<NewUploadFormProps> = ({ onSuccess, assignments }) => {
  const { t } = useTranslation(['files', 'common', 'languages', 'upload']);
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
        toast({ title: t('files:toasts.fileTooLarge', { name: file.name }), status: 'warning', duration: 3000 });
        continue;
      }
      const key = getFileKey(file);
      if (!newFiles.some(f => getFileKey(f) === key)) {
        newFiles.push(file);
      }
    }
    for (const rej of rejected) {
      toast({ title: t('files:toasts.fileRejected', { name: rej.file.name }), status: 'error', duration: 3000 });
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

      toast({ title: t('files:toasts.uploadStarted'), status: 'success', duration: 2000 });
      setFiles([]);
      setUploadName('');
      onSuccess();
    } catch {
      toast({ title: t('files:toasts.uploadFailed'), status: 'error', duration: 3000 });
    } finally {
      setUploading(false);
    }
  };

  const cardBg = useColorModeValue('white', 'gray.700');
  const dropBg = useColorModeValue('gray.50', 'gray.600');
  const dropBorder = useColorModeValue('gray.300', 'gray.500');

  return (
    <Card bg={cardBg} variant="outline">
      <CardBody>
        <VStack spacing={4} align="stretch">
          <HStack spacing={3} wrap="wrap">
            <Input
              placeholder={t('files:uploadNamePlaceholder')}
              value={uploadName}
              onChange={(e) => setUploadName(e.target.value)}
              size="sm"
              flex={{ base: 1, md: 'auto' }}
              minW={{ base: 'full', md: '200px' }}
            />
            <Select value={language} onChange={(e) => setLanguage(e.target.value)} size="sm" w={{ base: 'full', md: '180px' }}>
              {languageFormOptions(t).map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </Select>
            {assignments && assignments.length > 0 && (
              <Select
                value={selectedAssignment}
                onChange={(e) => setSelectedAssignment(e.target.value)}
                size="sm"
                w={{ base: 'full', md: '220px' }}
                placeholder={t('files:linkToAssignment')}
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
              {isDragActive ? t('files:dropzone.active') : t('files:dropzone.inactive')}
            </Text>
            <Text fontSize="xs" color="gray.500">
              {t('files:dropzone.maxInfo', { max: MAX_FILES, size: formatFileSize(MAX_FILE_SIZE) })}
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
                    aria-label={t('files:removeFileLabel')}
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
              {t('files:startAnalysis', { count: files.length })}
            </Button>
          </Flex>
        </VStack>
      </CardBody>
    </Card>
  );
};

// --- Main Files Page ---

const Files: React.FC = () => {
  const { t } = useTranslation(['files', 'common', 'languages', 'status']);
  const toast = useToast();
  const queryClient = useQueryClient();
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [languageFilter, setLanguageFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [confirmedFilter, setConfirmedFilter] = useState('');
  const [assignmentFilter, setAssignmentFilter] = useState('');
  const [minSimilarity, setMinSimilarity] = useState<number | undefined>(undefined);
  const [maxSimilarity, setMaxSimilarity] = useState<number | undefined>(undefined);

  // Pagination
  const [page, setPage] = useState(0);

  // Selection
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectAllAcrossPages, setSelectAllAcrossPages] = useState(false);

  // Move to assignment state
  const [showMoveToAssignment, setShowMoveToAssignment] = useState(false);
  const [targetAssignmentId, setTargetAssignmentId] = useState('');

  // Upload form
  const [showUpload, setShowUpload] = useState(false);

  // Delete confirmation
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const { isOpen: isBulkDeleteOpen, onOpen: onBulkDeleteOpen, onClose: onBulkDeleteClose } = useDisclosure();

  const debouncedSearch = useDebounce(search, 300);

  // Data fetching
  const { data: filesData, isLoading } = useAllFiles({
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    filename: debouncedSearch || undefined,
    language: languageFilter || undefined,
    status: statusFilter || undefined,
    assignment_id: assignmentFilter || undefined,
    similarity_min: minSimilarity,
    similarity_max: maxSimilarity,
  });

  const { data: subjectsData } = useSubjectsWithAssignments();

  const deleteFile = useDeleteFile();
  const bulkMoveMutation = useBulkMoveByAssignment();

  const total = filesData?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const assignments: { id: string; name: string }[] = (subjectsData || []).flatMap(
    (s: { assignments?: { id: string; name: string }[] }) => s.assignments || [],
  );

  const fileIdsQuery = useFileIds({
    filename: debouncedSearch || undefined,
    language: languageFilter || undefined,
    status: statusFilter || undefined,
    assignment_id: assignmentFilter || undefined,
    similarity_min: minSimilarity,
    similarity_max: maxSimilarity,
  });

  // Client-side confirmed filter (since server doesn't have this filter)
  const filteredFiles = useMemo(() => {
    const files = filesData?.items || [];
    if (!confirmedFilter) return files;
    if (confirmedFilter === 'confirmed') return files.filter(f => f.is_confirmed);
    return files.filter(f => !f.is_confirmed);
  }, [filesData, confirmedFilter]);

  // Selection handlers
  const handleSelect = useCallback((id: string, selectedState: boolean) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (selectedState) next.add(id);
      else next.delete(id);
      return next;
    });
    if (!selectedState) setSelectAllAcrossPages(false);
  }, []);

  const handleSelectAll = useCallback(() => {
    if (!selectAllAcrossPages && selected.size === filteredFiles.length) {
      setSelected(new Set());
    } else {
      setSelectAllAcrossPages(false);
      setSelected(new Set(filteredFiles.map(f => f.id)));
    }
  }, [filteredFiles, selected.size, selectAllAcrossPages]);

  const handleSelectAllAcrossPages = useCallback(async () => {
    setSelectAllAcrossPages(true);
    setSelected(new Set());
    fileIdsQuery.refetch();
  }, [fileIdsQuery]);

  const handleClearSelection = useCallback(() => {
    setSelected(new Set());
    setSelectAllAcrossPages(false);
  }, []);

  // Delete handlers
  const handleSingleDelete = useCallback((fileId: string) => {
    setPendingDeleteId(fileId);
    onDeleteOpen();
  }, [onDeleteOpen]);

  const confirmSingleDelete = async () => {
    if (!pendingDeleteId) return;
    try {
      await deleteFile.mutateAsync(pendingDeleteId);
      toast({ title: t('files:toasts.fileDeleted'), status: 'success', duration: 2000 });
    } catch {
      toast({ title: t('files:toasts.failedToDelete'), status: 'error', duration: 3000 });
    }
    setPendingDeleteId(null);
    onDeleteClose();
  };

  const handleBulkDelete = useCallback(() => {
    onBulkDeleteOpen();
  }, [onBulkDeleteOpen]);

  const confirmBulkDelete = async () => {
    for (const fileId of selected) {
      try {
        await deleteFile.mutateAsync(fileId);
      } catch {
        // continue
      }
    }
    toast({ title: t('files:toasts.filesDeleted', { count: selected.size }), status: 'success', duration: 3000 });
    setSelected(new Set());
    onBulkDeleteClose();
  };

  const isAnyBulkLoading = deleteFile.isPending;

  // Pagination handlers
  const goToPage = useCallback((p: number) => {
    setPage(Math.max(0, Math.min(p, totalPages - 1)));
  }, [totalPages]);

  const handleUploadSuccess = useCallback(() => {
    setShowUpload(false);
    queryClient.invalidateQueries({ queryKey: ['files'] });
  }, [queryClient]);

  // Empty state
  const isEmpty = !isLoading && filteredFiles.length === 0;

  return (
    <VStack align="stretch" spacing={4} flex={1} overflow="hidden">
      {/* Header */}
      <Flex justify="space-between" align="center">
        <HStack spacing={3}>
          <Text fontSize="2xl" fontWeight="bold">{t('files:pageTitle')}</Text>
          {!isLoading && (
            <Badge colorScheme="gray" variant="subtle" fontSize="sm" px={2}>
              {t('files:count', { count: total })}
            </Badge>
          )}
        </HStack>
        <Button
          colorScheme="brand"
          leftIcon={<FiUploadCloud />}
          onClick={() => setShowUpload(!showUpload)}
          size="sm"
        >
          {showUpload ? t('files:hide') : t('files:newUpload')}
        </Button>
      </Flex>

      {/* Upload form */}
      <Collapse in={showUpload} animateOpacity>
        <NewUploadForm onSuccess={handleUploadSuccess} assignments={assignments} />
      </Collapse>

      {/* Filters toolbar */}
      <Card variant="outline">
        <CardBody py={3}>
          <VStack spacing={3}>
            <HStack spacing={3} wrap="wrap" w="full">
              <InputGroup maxW={{ base: 'full', md: '280px' }}>
                <InputLeftElement pointerEvents="none">
                  <Icon as={FiSearch} color="gray.400" />
                </InputLeftElement>
                <Input
                  placeholder={t('files:searchPlaceholder')}
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(0); }}
                  size="sm"
                />
              </InputGroup>
              <Select
                size="sm"
                w={{ base: 'full', md: '150px' }}
                value={languageFilter}
                onChange={(e) => { setLanguageFilter(e.target.value); setPage(0); }}
              >
                {languageOptions(t).map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
              <Select
                size="sm"
                w={{ base: 'full', md: '150px' }}
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
              >
                {statusOptions(t).map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
              <Select
                size="sm"
                w={{ base: 'full', md: '150px' }}
                value={confirmedFilter}
                onChange={(e) => { setConfirmedFilter(e.target.value); setPage(0); }}
              >
                {confirmedOptions(t).map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
              <AssignmentFilter
                selectedAssignmentId={assignmentFilter || null}
                onSelect={(id) => { setAssignmentFilter(id || ''); setPage(0); }}
              />
            </HStack>
            <HStack spacing={3} wrap="wrap" w="full">
              <HStack spacing={1}>
                <Text fontSize="xs" color="gray.500" whiteSpace="nowrap">{t('files:simGreater')}</Text>
                <NumberInput
                  size="xs"
                  w="70px"
                  min={0}
                  max={1}
                  step={0.1}
                  value={minSimilarity ?? ''}
                  onChange={(_, val) => { setMinSimilarity(isNaN(val) ? undefined : val); setPage(0); }}
                >
                  <NumberInputField placeholder={t('files:min')} />
                </NumberInput>
              </HStack>
              <HStack spacing={1}>
                <Text fontSize="xs" color="gray.500" whiteSpace="nowrap">{t('files:simLess')}</Text>
                <NumberInput
                  size="xs"
                  w="70px"
                  min={0}
                  max={1}
                  step={0.1}
                  value={maxSimilarity ?? ''}
                  onChange={(_, val) => { setMaxSimilarity(isNaN(val) ? undefined : val); setPage(0); }}
                >
                  <NumberInputField placeholder={t('files:max')} />
                </NumberInput>
              </HStack>
              {(search || languageFilter || statusFilter || confirmedFilter || assignmentFilter || minSimilarity !== undefined || maxSimilarity !== undefined) && (
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => {
                    setSearch('');
                    setLanguageFilter('');
                    setStatusFilter('');
                    setConfirmedFilter('');
                    setAssignmentFilter('');
                    setMinSimilarity(undefined);
                    setMaxSimilarity(undefined);
                    setPage(0);
                  }}
                >
                  {t('files:clearFilters')}
                </Button>
              )}
            </HStack>
          </VStack>
        </CardBody>
      </Card>

      {/* Bulk action bar */}
      {(selected.size > 0 || selectAllAcrossPages) && (
        <Card bg="brand.50" borderColor="brand.200" borderWidth={1} variant="outline">
          <CardBody py={2}>
            <VStack spacing={2} align="stretch">
              <HStack spacing={3}>
                <Text fontSize="sm" fontWeight="medium" color="brand.700">
                  {selectAllAcrossPages
                    ? t('files:selectedAll', { total: total.toLocaleString() })
                    : selected.size === 1
                      ? t('files:selectedCount', { count: selected.size })
                      : t('files:selectedCountPlural', { count: selected.size })}
                </Text>
                <Button
                  size="xs"
                  colorScheme="red"
                  leftIcon={<FiTrash2 />}
                  onClick={handleBulkDelete}
                  isLoading={isAnyBulkLoading}
                >
                  {t('files:delete')}
                </Button>
                <Button
                  size="xs"
                  colorScheme="blue"
                  leftIcon={<FiMove />}
                  onClick={() => setShowMoveToAssignment(true)}
                >
                  {t('files:moveToAssignment')}
                </Button>
                <Button size="xs" variant="ghost" onClick={handleClearSelection}>
                  {t('files:clear')}
                </Button>
              </HStack>
              {showMoveToAssignment && (
                <HStack spacing={2}>
                  <Select
                    size="sm"
                    w="250px"
                    value={targetAssignmentId}
                    onChange={(e) => setTargetAssignmentId(e.target.value)}
                    placeholder={t('files:selectAssignmentPlaceholder')}
                  >
                    {assignments.map((a: { id: string; name: string }) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </Select>
                  <Button
                    size="xs"
                    colorScheme="green"
                    isDisabled={!targetAssignmentId}
                    isLoading={bulkMoveMutation.isPending}
                    onClick={async () => {
                      const fileIds = selectAllAcrossPages
                        ? (fileIdsQuery.data ?? [])
                        : Array.from(selected);
                      try {
                        await bulkMoveMutation.mutateAsync({
                          fileIds,
                          targetAssignmentId,
                        });
                        toast({ title: t('files:toasts.filesMoved', { count: fileIds.length }), status: 'success', duration: 3000 });
                        setShowMoveToAssignment(false);
                        setTargetAssignmentId('');
                        handleClearSelection();
                        queryClient.invalidateQueries({ queryKey: ['files'] });
                      } catch {
                        toast({ title: t('files:toasts.failedToMove'), status: 'error', duration: 3000 });
                      }
                    }}
                  >
                    {t('files:move')}
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => { setShowMoveToAssignment(false); setTargetAssignmentId(''); }}
                  >
                    {t('files:cancel')}
                  </Button>
                </HStack>
              )}
            </VStack>
          </CardBody>
        </Card>
      )}

      {/* Table */}
      <Box
        flex={1}
        overflow="auto"
        borderWidth="1px"
        borderColor="gray.200"
        borderRadius="md"
        css={{
          '&::-webkit-scrollbar': { width: '6px' },
          '&::-webkit-scrollbar-thumb': { bg: 'gray.300', borderRadius: '3px' },
        }}
      >
        <Table size="sm" variant="simple">
          <Thead position="sticky" top={0} bg={useColorModeValue('gray.50', 'gray.700')} zIndex={1}>
            <Tr>
              <Th w="40px" px={2}>
                <Checkbox
                  isChecked={selectAllAcrossPages || (filteredFiles.length > 0 && selected.size === filteredFiles.length)}
                  onChange={handleSelectAll}
                  size="sm"
                />
              </Th>
              <Th>{t('files:columns.filename')}</Th>
              <Th>{t('files:columns.upload')}</Th>
              <Th>{t('files:columns.language')}</Th>
              <Th>{t('files:columns.similarity')}</Th>
              <Th>{t('files:columns.confirmed')}</Th>
              <Th>{t('files:columns.created')}</Th>
              <Th w="40px"></Th>
            </Tr>
          </Thead>
          <Tbody>
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <Tr key={i}>
                  {Array.from({ length: 8 }).map((_, j) => (
                    <Td key={j}><Box h="32px" bg="gray.100" borderRadius="sm" /></Td>
                  ))}
                </Tr>
              ))
            ) : isEmpty ? (
              <Tr>
                <Td colSpan={8}>
                  <Flex justify="center" py={8} flexDirection="column" align="center">
                    <Icon as={FiFile} boxSize={10} color="gray.300" mb={3} />
                    <Text color="gray.500" fontSize="md">{t('files:noFilesFound')}</Text>
                    <Text color="gray.400" fontSize="sm">
                      {search || languageFilter || statusFilter || confirmedFilter || assignmentFilter || minSimilarity !== undefined || maxSimilarity !== undefined
                        ? t('files:adjustFilters')
                        : t('files:uploadToGetStarted')}
                    </Text>
                  </Flex>
                </Td>
              </Tr>
            ) : (
              filteredFiles.map(file => (
                <FileRow
                  key={file.id}
                  file={file}
                  isSelected={selected.has(file.id)}
                  onSelect={handleSelect}
                  onDelete={handleSingleDelete}
                />
              ))
            )}
          </Tbody>
        </Table>
      </Box>

      {/* Pagination */}
      {totalPages > 1 && (
        <HStack justify="center" spacing={2} pt={2}>
          <IconButton
            size="sm"
            icon={<FiChevronsLeft />}
            onClick={() => goToPage(0)}
            isDisabled={page === 0}
            aria-label={t('common:aria.firstPage')}
          />
          <IconButton
            size="sm"
            icon={<FiChevronLeft />}
            onClick={() => goToPage(page - 1)}
            isDisabled={page === 0}
            aria-label={t('common:aria.previousPage')}
          />
          <Text fontSize="sm" minW="200px" textAlign="center" color="gray.600">
            {t('files:showing', {
              start: page * PAGE_SIZE + 1,
              end: Math.min((page + 1) * PAGE_SIZE, total),
              total: total.toLocaleString(),
            })}
          </Text>
          <IconButton
            size="sm"
            icon={<FiChevronRight />}
            onClick={() => goToPage(page + 1)}
            isDisabled={page >= totalPages - 1}
            aria-label={t('common:aria.nextPage')}
          />
          <IconButton
            size="sm"
            icon={<FiChevronsRight />}
            onClick={() => goToPage(totalPages - 1)}
            isDisabled={page >= totalPages - 1}
            aria-label={t('common:aria.lastPage')}
          />
          <HStack spacing={1} ml={2}>
            <Text fontSize="xs" color="gray.500">{t('files:goTo')}</Text>
            <Select
              size="xs"
              w="70px"
              value={page}
              onChange={(e) => goToPage(Number(e.target.value))}
            >
              {Array.from({ length: totalPages }, (_, i) => (
                <option key={i} value={i}>{i + 1}</option>
              ))}
            </Select>
            <Text fontSize="xs" color="gray.500">{t('files:ofPages', { total: totalPages })}</Text>
          </HStack>
        </HStack>
      )}

      {/* Single delete confirmation */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef as React.RefObject<HTMLButtonElement>}
        onClose={onDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">{t('files:singleDeleteTitle')}</AlertDialogHeader>
            <AlertDialogBody>
              {t('files:singleDeleteDesc')}
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose} isDisabled={deleteFile.isPending}>{t('common:cancel')}</Button>
              <Button colorScheme="red" onClick={confirmSingleDelete} ml={3} isLoading={deleteFile.isPending}>{t('common:delete')}</Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Bulk delete confirmation */}
      <AlertDialog
        isOpen={isBulkDeleteOpen}
        leastDestructiveRef={cancelRef as React.RefObject<HTMLButtonElement>}
        onClose={onBulkDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('files:bulkDeleteTitle', { count: selected.size })}
            </AlertDialogHeader>
            <AlertDialogBody>
              {t('files:bulkDeleteDesc', { count: selected.size })}
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkDeleteClose} isDisabled={deleteFile.isPending}>{t('common:cancel')}</Button>
              <Button colorScheme="red" onClick={confirmBulkDelete} ml={3} isLoading={deleteFile.isPending}>{t('common:delete')}</Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
};

export default Files;
