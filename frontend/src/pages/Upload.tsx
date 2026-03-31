import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router';
import {
  Box,
  Text,
  Button,
  VStack,
  HStack,
  Select,
  Progress,
  Icon,
  Badge,
  useToast,
  useColorModeValue,
  Input,
  InputGroup,
  InputLeftElement,
  IconButton,
  Flex,
  Divider,
  Stat,
  StatLabel,
  StatNumber,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  Spinner,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import {
  FiUploadCloud,
  FiFile,
  FiX,
  FiSearch,
  FiTrash2,
  FiChevronLeft,
  FiChevronRight,
  FiCheckCircle,
  FiAlertTriangle,
  FiFolder,
} from 'react-icons/fi';
import {
  SiPython,
  SiJavascript,
  SiTypescript,
  SiCplusplus,
  SiC,
  SiGo,
  SiRust,
} from 'react-icons/si';
import { FaJava } from 'react-icons/fa';
import { useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../services/api';

const MAX_FILE_SIZE = 1 * 1024 * 1024; // 1MB
const MAX_FILES = 1000;
const LANG_STORAGE_KEY = 'upload_last_language';

const getFileExtension = (filename: string): string => {
  const parts = filename.split('.');
  return parts.length > 1 ? parts.pop()!.toLowerCase() : '';
};

const getFileKey = (file: File): string =>
  `${file.name}-${file.size}-${file.lastModified}`;

const getFileIcon = (filename: string) => {
  const ext = getFileExtension(filename);
  switch (ext) {
    case 'py':
      return { icon: SiPython, color: '#3776AB' };
    case 'js':
      return { icon: SiJavascript, color: '#F7DF1E' };
    case 'ts':
      return { icon: SiTypescript, color: '#3178C6' };
    case 'cpp':
    case 'cc':
    case 'cxx':
      return { icon: SiCplusplus, color: '#00599C' };
    case 'c':
      return { icon: SiC, color: '#555555' };
    case 'java':
      return { icon: FaJava, color: '#ED8B00' };
    case 'go':
      return { icon: SiGo, color: '#00ADD8' };
    case 'rs':
      return { icon: SiRust, color: '#DEA584' };
    default:
      return { icon: FiFile, color: '#718096' };
  }
};

const formatFileSize = (bytes: number): string => {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
};

const getLastLanguage = (): string => {
  try {
    return localStorage.getItem(LANG_STORAGE_KEY) || 'python';
  } catch {
    return 'python';
  }
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

const Upload: React.FC = () => {
  const { t } = useTranslation(['upload', 'common', 'languages']);
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [language, setLanguage] = useState(getLastLanguage);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [pageSize, setPageSize] = useState(50);
  const [currentPage, setCurrentPage] = useState(0);
  const toast = useToast();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const { isOpen: isClearOpen, onOpen: onClearOpen, onClose: onClearClose } = useDisclosure();

  const { data: assignmentsData } = useQuery({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data as { items: { id: string; name: string }[] };
    },
  });

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const subtleBg = useColorModeValue('gray.50', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');
  const dropzoneHoverBg = useColorModeValue('brand.50', 'gray.600');

  // Warn before leaving with unsaved files
  useEffect(() => {
    if (files.length === 0 || isUploading) return;
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [files.length, isUploading]);

  // Dropzone
  const onDrop = useCallback(
    (acceptedFiles: File[], rejected: { file: File }[]) => {
      if (rejected.length > 0) {
        toast({
          title: `${rejected.length} ${t('rejected')}`,
          description: `${t('toasts.failed')}: ${formatFileSize(MAX_FILE_SIZE)}`,
          status: 'warning',
          duration: 4000,
        });
      }

      setFiles((prev) => {
        const existingKeys = new Set(prev.map(getFileKey));
        const newFiles: File[] = [];
        let duplicateCount = 0;
        let overLimit = false;

        for (const file of acceptedFiles) {
          const key = getFileKey(file);
          if (existingKeys.has(key)) {
            duplicateCount++;
            continue;
          }
          if (prev.length + newFiles.length >= MAX_FILES) {
            overLimit = true;
            break;
          }
          newFiles.push(file);
          existingKeys.add(key);
        }

        if (duplicateCount > 0) {
          toast({
            title: `${duplicateCount} ${t('duplicateSkipped')}`,
            status: 'info',
            duration: 3000,
          });
        }
        if (overLimit) {
          toast({
            title: t('fileLimitReached'),
            description: `Max ${MAX_FILES} max`,
            status: 'warning',
            duration: 4000,
          });
        }

        if (newFiles.length > 0) {
          setCurrentPage(0);
          setSearchQuery('');
        }

        return [...prev, ...newFiles];
      });
    },
    [toast, t]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.txt', '.py', '.js', '.ts', '.cpp', '.c', '.java', '.go', '.rs'],
    },
    multiple: true,
    maxSize: MAX_FILE_SIZE,
  });

  const removeFile = (key: string) => {
    setFiles((prev) => {
      const file = prev.find((f) => getFileKey(f) === key);
      const next = prev.filter((f) => getFileKey(f) !== key);

      if (file) {
        toast({
          title: t('common:clearAllFiles'),
          status: 'info',
          duration: 3000,
          render: ({ onClose }) => (
            <Box
              bg="gray.700"
              color="white"
              p={3}
              borderRadius="md"
              boxShadow="lg"
              display="flex"
              alignItems="center"
              gap={3}
            >
              <Text fontSize="sm">{t('common:clearAllFiles')}: {file.name}</Text>
              <Button
                size="xs"
                colorScheme="blue"
                onClick={() => {
                  setFiles((current) => [...current, file]);
                  onClose();
                }}
              >
                Undo
              </Button>
              <IconButton
                aria-label="Close"
                icon={<FiX />}
                size="xs"
                variant="ghost"
                colorScheme="whiteAlpha"
                onClick={onClose}
              />
            </Box>
          ),
        });
      }

      if (next.length === 0) setCurrentPage(0);
      return next;
    });
  };

  const clearAll = () => {
    setFiles([]);
    setSearchQuery('');
    setCurrentPage(0);
    onClearClose();
  };

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const lang = e.target.value;
    setLanguage(lang);
    try {
      localStorage.setItem(LANG_STORAGE_KEY, lang);
    } catch {
      // ignore storage errors
    }
  };

  // Upload
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
      if (selectedAssignmentId) {
        formData.append('assignment_id', selectedAssignmentId);
      }

      await api.post(API_ENDPOINTS.CHECK, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded / (progressEvent.total || 1)) * 100
          );
          setUploadProgress(percentCompleted);
        },
      });

      toast({
        title: t('toasts.success'),
        description: t('uploadSuccess', { count: files.length }),
        status: 'success',
        duration: 3000,
      });

      setFiles([]);
      navigate('/dashboard/results');
    } catch (err: unknown) {
      let errorMessage = t('common:error');
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string; message?: string } } };
        errorMessage =
          axiosErr.response?.data?.detail ||
          axiosErr.response?.data?.message ||
          errorMessage;
      }
      toast({
        title: t('toasts.failed'),
        description: errorMessage,
        status: 'error',
        duration: 6000,
      });
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  // Derived state
  const totalSize = useMemo(
    () => files.reduce((sum, f) => sum + f.size, 0),
    [files]
  );

  const filteredFiles = useMemo(() => {
    if (!searchQuery.trim()) return files;
    const q = searchQuery.toLowerCase();
    return files.filter((f) => f.name.toLowerCase().includes(q));
  }, [files, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(filteredFiles.length / pageSize));
  const paginatedFiles = filteredFiles.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize
  );

  const showingStart = filteredFiles.length > 0 ? currentPage * pageSize + 1 : 0;
  const showingEnd = Math.min((currentPage + 1) * pageSize, filteredFiles.length);

  // Reset to page 0 when search or page size changes
  useEffect(() => {
    setCurrentPage(0);
  }, [searchQuery, pageSize]);

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
      <Flex
        direction={{ base: 'column', lg: 'row' }}
        gap={6}
        flex={1}
        minH={0}
        overflow="hidden"
      >
        {/* Left column: Config + Dropzone */}
        <Flex
          direction="column"
          flex={{ base: 'none', lg: 1 }}
          minH={0}
          overflow={{ base: 'auto', lg: 'hidden' }}
        >
          {/* Configuration */}
          <Box
            bg={cardBg}
            borderRadius="lg"
            borderWidth="1px"
            borderColor={borderColor}
            p={4}
            flexShrink={0}
          >
            <HStack spacing={6} wrap="wrap">
              <Box>
                <Text fontSize="sm" color={mutedColor} mb={1}>
                  {t('language')}
                </Text>
                <Select
                  value={language}
                  onChange={handleLanguageChange}
                  maxW="200px"
                  size="sm"
                >
                  {languageOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {t(`languages.${opt.key}`)}
                    </option>
                  ))}
                </Select>
              </Box>
              <Box>
                <Text fontSize="sm" color={mutedColor} mb={1}>
                  {t('analysisScope')}
                </Text>
                <Select
                  value={selectedAssignmentId}
                  onChange={(e) => setSelectedAssignmentId(e.target.value)}
                  maxW="250px"
                  size="sm"
                >
                  <option value="">{t('fullDbScan')}</option>
                  {(assignmentsData?.items || []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </Select>
              </Box>
              <Box>
                <Text fontSize="sm" color={mutedColor} mb={1}>
                  {t('maxFileSize')}
                </Text>
                <Text fontWeight="medium" pt={1}>
                  {formatFileSize(MAX_FILE_SIZE)}
                </Text>
              </Box>
            </HStack>
          </Box>

          {/* Dropzone - fills remaining vertical space */}
          <Box
            bg={cardBg}
            borderRadius="lg"
            borderWidth="1px"
            borderColor={borderColor}
            mt={6}
            flex={1}
            minH={0}
            display="flex"
          >
            <Box
              {...getRootProps()}
              border="2px dashed"
              borderColor={isDragActive ? 'brand.500' : borderColor}
              borderRadius="lg"
              m={2}
              flex={1}
              display="flex"
              flexDirection="column"
              alignItems="center"
              justifyContent="center"
              textAlign="center"
              cursor="pointer"
              bg={isDragActive ? dropzoneHoverBg : subtleBg}
              transition="all 0.2s"
              _hover={{
                borderColor: 'brand.400',
                bg: dropzoneHoverBg,
              }}
            >
              <input {...getInputProps()} />
              <VStack spacing={3}>
                <Icon
                  as={FiUploadCloud}
                  boxSize={12}
                  color={isDragActive ? 'brand.500' : 'brand.400'}
                  transition="transform 0.2s"
                  transform={isDragActive ? 'translateY(-4px)' : 'none'}
                />
                <Text fontSize="lg" fontWeight="medium">
                  {isDragActive ? t('dragAndDrop') : t('dragAndDrop')}
                </Text>
                <Text color={mutedColor}>{t('orClickToSelect')}</Text>
                <HStack spacing={1} flexWrap="wrap" justify="center">
                  {['.py', '.js', '.ts', '.cpp', '.c', '.java', '.go', '.rs', '.txt'].map(
                    (ext) => (
                      <Badge key={ext} variant="subtle" colorScheme="gray" fontSize="xs">
                        {ext}
                      </Badge>
                    )
                  )}
                </HStack>
                <Text fontSize="xs" color={mutedColor}>
                  {t('maxPerFile', { size: formatFileSize(MAX_FILE_SIZE) })} &middot; {t('maxFiles', { max: MAX_FILES })}
                </Text>
              </VStack>
            </Box>
          </Box>
        </Flex>

        {/* Right column: File list */}
        <Box
          bg={cardBg}
          borderRadius="lg"
          borderWidth="1px"
          borderColor={borderColor}
          display="flex"
          flexDirection="column"
          flex={{ base: 'none', lg: 1 }}
          minH={0}
          overflow="hidden"
        >
          <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
            {files.length === 0 ? (
              <Flex
                flex={1}
                align="center"
                justify="center"
                direction="column"
                p={8}
                color={mutedColor}
              >
                <Icon as={FiFolder} boxSize={10} mb={3} />
                <Text fontWeight="medium">{t('noFilesSelected')}</Text>
                <Text fontSize="sm">{t('dropFilesToStart')}</Text>
              </Flex>
            ) : (
              <>
                {/* Summary header */}
                <Box p={4} pb={2} flexShrink={0}>
                  <Flex justify="space-between" align="center" wrap="wrap" gap={2}>
                    <Text fontWeight="semibold">
                      {t('selectedFiles')}
                    </Text>
                    <Button
                      size="xs"
                      variant="ghost"
                      colorScheme="red"
                      leftIcon={<FiTrash2 />}
                      onClick={onClearOpen}
                      isDisabled={isUploading}
                    >
                      {t('common:clearAll')}
                    </Button>
                  </Flex>
                  <HStack spacing={4} mt={2}>
                    <Stat size="sm">
                      <StatLabel fontSize="xs">{t('filesCount', { count: files.length })}</StatLabel>
                      <StatNumber fontSize="md">{files.length}</StatNumber>
                    </Stat>
                    <Stat size="sm">
                      <StatLabel fontSize="xs">{t('totalSize')}</StatLabel>
                      <StatNumber fontSize="md">{formatFileSize(totalSize)}</StatNumber>
                    </Stat>
                  </HStack>
                </Box>

                <Divider flexShrink={0} />

                {/* Search */}
                <Box px={4} pt={3} pb={2} flexShrink={0}>
                  <InputGroup size="sm">
                    <InputLeftElement pointerEvents="none">
                      <Icon as={FiSearch} color={mutedColor} />
                    </InputLeftElement>
                    <Input
                      placeholder={t('filterFiles')}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      isDisabled={isUploading}
                    />
                  </InputGroup>
                </Box>

                {/* Pagination top */}
                <Flex
                  justify="space-between"
                  align="center"
                  px={4}
                  py={2}
                  borderBottomWidth={1}
                  borderColor={borderColor}
                  wrap="wrap"
                  gap={2}
                  flexShrink={0}
                >
                  <HStack spacing={2}>
                    <Button
                      size="xs"
                      onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                      isDisabled={currentPage === 0 || isUploading}
                      leftIcon={<FiChevronLeft />}
                    >
                      {t('common:prev')}
                    </Button>
                    <Text fontSize="xs" color={mutedColor}>
                      {currentPage + 1} / {totalPages}
                    </Text>
                    <Button
                      size="xs"
                      onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
                      isDisabled={currentPage >= totalPages - 1 || isUploading}
                      rightIcon={<FiChevronRight />}
                    >
                      {t('common:next')}
                    </Button>
                  </HStack>
                  <HStack spacing={2}>
                    <Text fontSize="xs" color={mutedColor}>
                      {t('common:show')}
                    </Text>
                    <Select
                      size="xs"
                      value={pageSize}
                      onChange={(e) => setPageSize(parseInt(e.target.value, 10))}
                      w="70px"
                      isDisabled={isUploading}
                    >
                      <option value="25">25</option>
                      <option value="50">50</option>
                      <option value="100">100</option>
                    </Select>
                    <Text fontSize="xs" color={mutedColor}>
                      {showingStart}-{showingEnd} {t('common:of', { total: filteredFiles.length })}
                      {searchQuery && ` (filtered)`}
                    </Text>
                  </HStack>
                </Flex>

                {/* File list - scrolls */}
                <Box flex={1} minH={0} overflowY="auto" px={2} py={2}>
                  <VStack spacing={1} align="stretch">
                    {paginatedFiles.map((file) => {
                      const key = getFileKey(file);
                      const { icon: FileIcon, color: iconColor } = getFileIcon(file.name);
                      const isOverSize = file.size > MAX_FILE_SIZE;

                      return (
                        <HStack
                          key={key}
                          justify="space-between"
                          p={2}
                          borderRadius="md"
                          _hover={{ bg: hoverBg }}
                          transition="background 0.15s"
                        >
                          <HStack spacing={3} minW={0} flex={1}>
                            <Icon as={FileIcon} color={iconColor} boxSize={4} flexShrink={0} />
                            <Text fontSize="sm" noOfLines={1} title={file.name}>
                              {file.name}
                            </Text>
                            <Badge
                              size="sm"
                              colorScheme={isOverSize ? 'red' : 'gray'}
                              variant="subtle"
                              flexShrink={0}
                            >
                              {formatFileSize(file.size)}
                            </Badge>
                            {isOverSize && (
                              <Icon
                                as={FiAlertTriangle}
                                color="red.400"
                                boxSize={3}
                                flexShrink={0}
                              />
                            )}
                          </HStack>
                          <IconButton
                            aria-label={t('common:actions')}
                            icon={<FiX />}
                            size="xs"
                            variant="ghost"
                            colorScheme="red"
                            onClick={() => removeFile(key)}
                            isDisabled={isUploading}
                            flexShrink={0}
                          />
                        </HStack>
                      );
                    })}
                  </VStack>
                </Box>

                <Divider flexShrink={0} />

                {/* Upload section */}
                <Box p={4} flexShrink={0} bg={cardBg}>
                  {isUploading && (
                    <Box mb={3}>
                      <Progress
                        value={uploadProgress}
                        size="sm"
                        colorScheme="brand"
                        borderRadius="full"
                        hasStripe
                        isAnimated
                      />
                      <Text fontSize="xs" textAlign="center" mt={1} color={mutedColor}>
                        {t('uploading')} {uploadProgress}%
                      </Text>
                    </Box>
                  )}
                  <Button
                    colorScheme="brand"
                    size="lg"
                    w="full"
                    onClick={handleUpload}
                    isLoading={isUploading}
                    loadingText={t('uploading')}
                    leftIcon={isUploading ? <Spinner size="sm" /> : <FiCheckCircle />}
                  >
                    {t('upload', { count: files.length, size: formatFileSize(totalSize) })}
                  </Button>
                </Box>
              </>
            )}
          </Box>
        </Box>
      </Flex>

      {/* Clear All confirmation */}
      <AlertDialog
        isOpen={isClearOpen}
        leastDestructiveRef={cancelRef as React.RefObject<HTMLButtonElement>}
        onClose={onClearClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('common:clearAllFiles')}
            </AlertDialogHeader>
            <AlertDialogBody>
              {t('common:areYouSure')} {files.length} {t('common:clearAllFiles')}.
            </AlertDialogBody>
             <AlertDialogFooter>
               <Button ref={cancelRef} onClick={onClearClose}>
                 {t('common:cancel')}
               </Button>
               <Button colorScheme="red" onClick={clearAll} ml={3}>
                 {t('common:clearAll')}
               </Button>
             </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default Upload;
