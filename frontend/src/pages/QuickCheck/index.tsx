import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router';
import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  Card,
  CardBody,
  Button,
  Select,
  Input,
  Radio,
  RadioGroup,
  Stack,
  Progress,
  Badge,
  Icon,
  Spinner,
  useColorModeValue,
  useToast,
  Collapse,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiUploadCloud, FiFile, FiX, FiCheckCircle, FiArrowRight } from 'react-icons/fi';
import { useMutation, useQuery } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../../services/api';
import { useUploadDetails } from '../../hooks/useUploadQueries';

const MAX_FILE_SIZE = 1 * 1024 * 1024;

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

const formatFileSize = (bytes: number): string => {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
};

const getSimilarityColor = (score: number) => {
  if (score >= 0.8) return 'red';
  if (score >= 0.5) return 'yellow';
  return 'green';
};

const QuickCheck: React.FC = () => {
  const { t } = useTranslation(['quickCheck', 'common', 'navigation']);
  const toast = useToast();
  const navigate = useNavigate();
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const dropBg = useColorModeValue('gray.50', 'gray.600');
  const dropBorder = useColorModeValue('gray.300', 'gray.500');

  const [mode, setMode] = useState<'two-files' | 'vs-assignment'>('two-files');
  const [filesA, setFilesA] = useState<File[]>([]);
  const [filesB, setFilesB] = useState<File[]>([]);
  const [language, setLanguage] = useState('auto');
  const [selectedAssignment, setSelectedAssignment] = useState('');
  const [createdTaskId, setCreatedTaskId] = useState<string | null>(null);
  const [showResults, setShowResults] = useState(false);

  const { data: assignmentsData } = useQuery({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data;
    },
  });

  const { data: uploadDetails } = useUploadDetails(createdTaskId || undefined);

  const checkMutation = useMutation({
    mutationFn: async ({
      files,
      lang,
      assignmentId,
    }: {
      files: File[];
      lang: string;
      assignmentId?: string;
    }) => {
      const formData = new FormData();
      for (const file of files) {
        formData.append('files', file);
      }
      const timestamp = new Date().toISOString().slice(0, 16).replace('T', ' ');
      formData.append('name', `Quick Check — ${timestamp}`);
      if (lang !== 'auto') formData.append('language', lang);
      if (assignmentId) formData.append('assignment_id', assignmentId);

      const res = await api.post(API_ENDPOINTS.QUICK_CHECK, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    },
    onSuccess: (data) => {
      setCreatedTaskId(data.task_id);
      setShowResults(true);
      toast({
        title: t('analysisStarted'),
        status: 'success',
        duration: 3000,
      });
    },
    onError: (err: any) => {
      toast({
        title: t('analysisFailed'),
        description: err.response?.data?.detail || t('common:error'),
        status: 'error',
        duration: 4000,
      });
    },
  });

  const onDropA = useCallback((accepted: File[]) => {
    const newFiles = accepted.slice(0, 1);
    if (newFiles.length > 0 && newFiles[0].size > MAX_FILE_SIZE) {
      toast({ title: t('fileTooLarge'), status: 'warning', duration: 3000 });
      return;
    }
    if (newFiles.length > 0) {
      setFilesA(newFiles);
    }
  }, [toast, t]);

  const onDropB = useCallback((accepted: File[]) => {
    const newFiles = accepted.slice(0, 1);
    if (newFiles.length > 0 && newFiles[0].size > MAX_FILE_SIZE) {
      toast({ title: t('fileTooLarge'), status: 'warning', duration: 3000 });
      return;
    }
    if (newFiles.length > 0) {
      setFilesB(newFiles);
    }
  }, [toast, t]);

  const { getRootProps: getRootPropsA, getInputProps: getInputPropsA, isDragActive: isDragActiveA } = useDropzone({
    onDrop: onDropA,
    accept: {
      'text/x-python': ['.py'],
      'text/x-java-source': ['.java'],
      'text/javascript': ['.js'],
      'text/x-c': ['.c', '.cpp', '.h'],
      'text/x-go': ['.go'],
      'text/x-rust': ['.rs'],
    },
  });

  const { getRootProps: getRootPropsB, getInputProps: getInputPropsB, isDragActive: isDragActiveB } = useDropzone({
    onDrop: onDropB,
    accept: {
      'text/x-python': ['.py'],
      'text/x-java-source': ['.java'],
      'text/javascript': ['.js'],
      'text/x-c': ['.c', '.cpp', '.h'],
      'text/x-go': ['.go'],
      'text/x-rust': ['.rs'],
    },
  });

  const handleRunAnalysis = () => {
    if (mode === 'two-files') {
      if (filesA.length === 0 || filesB.length === 0) {
        toast({ title: t('selectBothFiles'), status: 'warning', duration: 3000 });
        return;
      }
      checkMutation.mutate({ files: [...filesA, ...filesB], lang: language });
    } else {
      if (filesA.length === 0) {
        toast({ title: t('selectFile'), status: 'warning', duration: 3000 });
        return;
      }
      if (!selectedAssignment) {
        toast({ title: t('selectAssignment'), status: 'warning', duration: 3000 });
        return;
      }
      checkMutation.mutate({ files: [...filesA], lang: language, assignmentId: selectedAssignment });
    }
  };

  const isProcessing = uploadDetails && !['completed', 'failed', 'error'].includes(uploadDetails.status);
  const isCompleted = uploadDetails?.status === 'completed';

  const assignments = assignmentsData?.items || [];

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="auto">
      <Flex justify="space-between" align="center" mb={6}>
        <Text fontSize="2xl" fontWeight="bold">
          {t('title')}
        </Text>
      </Flex>

      <Card bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} mb={6}>
        <CardBody>
          <VStack spacing={6} align="stretch">
            <RadioGroup value={mode} onChange={(v) => setMode(v as typeof mode)}>
              <Stack direction="row" spacing={6}>
                <Radio value="two-files">{t('modeTwoFiles')}</Radio>
                <Radio value="vs-assignment">{t('modeVsAssignment')}</Radio>
              </Stack>
            </RadioGroup>

            <Flex direction={{ base: 'column', md: 'row' }} align="start" gap={6} w="full">
              <VStack flex={1} align="stretch" spacing={3}>
                <Text fontWeight="semibold" fontSize="sm">{t('fileA')}</Text>
                <Box
                  {...getRootPropsA()}
                  p={4}
                  borderRadius="md"
                  bg={isDragActiveA ? 'brand.50' : dropBg}
                  border="2px dashed"
                  borderColor={isDragActiveA ? 'brand.400' : dropBorder}
                  cursor="pointer"
                  transition="all 0.2s"
                  minH="100px"
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                >
                  <input {...getInputPropsA()} />
                  {filesA.length > 0 ? (
                    <HStack spacing={2}>
                      <Icon as={FiFile} boxSize={4} color="brand.500" />
                      <Text fontSize="sm" fontWeight="medium" noOfLines={1}>{filesA[0].name}</Text>
                      <Text fontSize="xs" color="gray.500">({formatFileSize(filesA[0].size)})</Text>
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={(e) => { e.stopPropagation(); setFilesA([]); }}
                      >
                        <Icon as={FiX} />
                      </Button>
                    </HStack>
                  ) : (
                    <VStack spacing={2}>
                      <Icon as={FiUploadCloud} boxSize={6} color="gray.400" />
                      <Text fontSize="sm" color="gray.500">{t('dropFile')}</Text>
                    </VStack>
                  )}
                </Box>
              </VStack>

              {mode === 'two-files' && (
                <VStack flex={1} align="stretch" spacing={3}>
                  <Text fontWeight="semibold" fontSize="sm">{t('fileB')}</Text>
                  <Box
                    {...getRootPropsB()}
                    p={4}
                    borderRadius="md"
                    bg={isDragActiveB ? 'brand.50' : dropBg}
                    border="2px dashed"
                    borderColor={isDragActiveB ? 'brand.400' : dropBorder}
                    cursor="pointer"
                    transition="all 0.2s"
                    minH="100px"
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                  >
                    <input {...getInputPropsB()} />
                    {filesB.length > 0 ? (
                      <HStack spacing={2}>
                        <Icon as={FiFile} boxSize={4} color="brand.500" />
                        <Text fontSize="sm" fontWeight="medium" noOfLines={1}>{filesB[0].name}</Text>
                        <Text fontSize="xs" color="gray.500">({formatFileSize(filesB[0].size)})</Text>
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={(e) => { e.stopPropagation(); setFilesB([]); }}
                        >
                          <Icon as={FiX} />
                        </Button>
                      </HStack>
                    ) : (
                      <VStack spacing={2}>
                        <Icon as={FiUploadCloud} boxSize={6} color="gray.400" />
                        <Text fontSize="sm" color="gray.500">{t('dropFile')}</Text>
                      </VStack>
                    )}
                  </Box>
                </VStack>
              )}

              {mode === 'vs-assignment' && (
                <VStack flex={1} align="stretch" spacing={3}>
                  <Text fontWeight="semibold" fontSize="sm">{t('compareAgainst')}</Text>
                  <Select
                    value={selectedAssignment}
                    onChange={(e) => setSelectedAssignment(e.target.value)}
                    placeholder={t('selectAssignmentPlaceholder')}
                    size="md"
                  >
                    {assignments.map((a: any) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </Select>
                </VStack>
              )}
            </Flex>

            <HStack wrap="wrap">
              <Select value={language} onChange={(e) => setLanguage(e.target.value)} size="sm" w={{ base: 'full', md: '200px' }}>
                {languageOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
              <Button
                colorScheme="brand"
                leftIcon={<FiArrowRight />}
                onClick={handleRunAnalysis}
                isLoading={checkMutation.isPending}
                isDisabled={
                  checkMutation.isPending ||
                  (mode === 'two-files' && (filesA.length === 0 || filesB.length === 0)) ||
                  (mode === 'vs-assignment' && (filesA.length === 0 || !selectedAssignment))
                }
              >
                {t('runAnalysis')}
              </Button>
            </HStack>
          </VStack>
        </CardBody>
      </Card>

      <Collapse in={showResults && !!uploadDetails} animateOpacity>
        <Card bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} mb={6}>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Text fontWeight="semibold">{t('results')}</Text>
                {isCompleted && (
                  <Badge colorScheme="green">
                    <Icon as={FiCheckCircle} mr={1} />
                    {t('completed')}
                  </Badge>
                )}
              </HStack>

              {isProcessing && (
                <VStack spacing={2}>
                  <Progress value={uploadDetails.progress?.percentage ?? 0} w="full" size="sm" borderRadius="full" />
                  <Text fontSize="sm" color="gray.500">
                    {uploadDetails.status} — {uploadDetails.progress?.display || ''}
                  </Text>
                </VStack>
              )}

              {isCompleted && uploadDetails && (
                <VStack spacing={3} align="stretch">
                  <HStack justify="space-between">
                    <Text fontSize="sm">
                      {uploadDetails.files_count} {t('common:files')} · {uploadDetails.total_pairs || 0} {t('common:pairs')}
                    </Text>
                    {uploadDetails.similarity != null && (
                      <Badge colorScheme={getSimilarityColor(uploadDetails.similarity)}>
                        {t('maxSimilarity')}: {(uploadDetails.similarity * 100).toFixed(1)}%
                      </Badge>
                    )}
                  </HStack>
                  <HStack spacing={2}>
                    <Button
                      size="sm"
                      colorScheme="brand"
                      onClick={() => navigate(`/dashboard/review?upload=${createdTaskId}`)}
                    >
                      {t('reviewPairs')}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigate(`/dashboard/uploads/${createdTaskId}`)}
                    >
                      {t('viewUpload')}
                    </Button>
                  </HStack>
                  <Text fontSize="xs" color="gray.500">
                    {t('notSavedHint')}
                  </Text>
                </VStack>
              )}
            </VStack>
          </CardBody>
        </Card>
      </Collapse>
    </Box>
  );
};

export default QuickCheck;
