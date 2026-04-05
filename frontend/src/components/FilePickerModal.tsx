import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Button,
  Input,
  InputGroup,
  InputLeftElement,
  VStack,
  HStack,
  Text,
  Badge,
  Box,
  Flex,
  Spinner,
  Alert,
  AlertIcon,
  useColorModeValue,
} from '@chakra-ui/react';
import { FiSearch, FiRefreshCw } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useVirtualizer } from '@tanstack/react-virtual';
import api, { API_ENDPOINTS } from '../services/api';
import type { FileInfo, ApiError } from '../types';
import { useDebounce } from '../pages/Submissions/hooks/useDebounce';

interface FileResponse extends FileInfo {
  created_at?: string;
}

interface FilePickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (fileA: FileInfo, fileB: FileInfo) => void;
  initialFileAId?: string;
  initialFileBId?: string;
}

const LIST_HEIGHT = 400;
const SEARCH_DEBOUNCE_MS = 300;

interface FileItemProps {
  file: FileInfo;
  isSelectedA: boolean;
  isSelectedB: boolean;
  onSelectA: (file: FileInfo) => void;
  onSelectB: (file: FileInfo) => void;
  column: 'A' | 'B';
}

const FileItem: React.FC<FileItemProps> = ({ file, isSelectedA, isSelectedB, onSelectA, onSelectB, column }) => {
  const bgColor = useColorModeValue('white', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');
  const selectedBgA = useColorModeValue('blue.50', 'blue.900');
  const selectedBgB = useColorModeValue('green.50', 'green.900');

  const getBackground = () => {
    if (isSelectedA) return selectedBgA;
    if (isSelectedB) return selectedBgB;
    return bgColor;
  };

  const getBorderLeft = () => {
    if (isSelectedA) return '4px solid #3182CE';
    if (isSelectedB) return '4px solid #38A169';
    return '4px solid transparent';
  };

  const handleClick = () => {
    if (column === 'A') onSelectA(file);
    else onSelectB(file);
  };

  return (
    <Box
      bg={getBackground()}
      borderLeft={getBorderLeft()}
      px={3}
      py={2}
      cursor="pointer"
      onClick={handleClick}
      _hover={{ bg: isSelectedA ? selectedBgA : isSelectedB ? selectedBgB : hoverBg }}
      transition="background 0.15s"
      borderBottom="1px solid"
      borderColor={useColorModeValue('gray.200', 'gray.600')}
    >
      <Flex justify="space-between" align="start">
        <Box flex={1} minW={0}>
          <Text fontWeight="medium" fontSize="sm" isTruncated title={file.filename}>
            {file.filename}
          </Text>
          <HStack mt={1} spacing={2}>
            <Badge size="sm" colorScheme="gray" variant="subtle">
              {file.language || 'unknown'}
            </Badge>
            <Text fontSize="xs" color="gray.500" isTruncated>
              task: {file.task_id.substring(0, 8)}...
            </Text>
          </HStack>
        </Box>
        {file.similarity !== null && file.similarity !== undefined && (
          <Badge
            colorScheme={file.similarity >= 0.8 ? 'red' : file.similarity >= 0.5 ? 'orange' : file.similarity >= 0.3 ? 'yellow' : 'green'}
            variant="subtle"
            ml={2}
          >
            {(file.similarity * 100).toFixed(0)}%
          </Badge>
        )}
      </Flex>
    </Box>
  );
};

FileItem.displayName = 'FileItem';

const FilePickerModal: React.FC<FilePickerModalProps> = ({
  isOpen,
  onClose,
  onSelect,
  initialFileAId,
  initialFileBId,
}) => {
  const { t } = useTranslation(['pairComparison', 'common']);
  const [fileASearch, setFileASearch] = useState('');
  const [fileBSearch, setFileBSearch] = useState('');
  const [fileAResults, setFileAResults] = useState<FileResponse[]>([]);
  const [fileBResults, setFileBResults] = useState<FileResponse[]>([]);
  const [selectedFileA, setSelectedFileA] = useState<FileResponse | null>(null);
  const [selectedFileB, setSelectedFileB] = useState<FileResponse | null>(null);
  const [loadingA, setLoadingA] = useState(false);
  const [loadingB, setLoadingB] = useState(false);
  const [errors, setErrors] = useState<{ a?: string; b?: string }>({});
  const [similaritiesMap, setSimilaritiesMap] = useState<Record<string, number>>({});

  // Debounced search
  const debouncedSearchA = useDebounce(fileASearch, SEARCH_DEBOUNCE_MS);
  const debouncedSearchB = useDebounce(fileBSearch, SEARCH_DEBOUNCE_MS);

  const fetchFiles = useCallback(async (query: string, column: 'A' | 'B') => {
    if (!query.trim()) {
      if (column === 'A') setFileAResults([]);
      else setFileBResults([]);
      return;
    }

    const setLoading = column === 'A' ? setLoadingA : setLoadingB;
    const setResults = column === 'A' ? setFileAResults : setFileBResults;
    const setError = column === 'A' ? (msg: string) => setErrors(e => ({ ...e, a: msg })) : (msg: string) => setErrors(e => ({ ...e, b: msg }));

    setLoading(true);
    setError('');

    try {
      const response = await api.get<{ items: FileInfo[] }>(API_ENDPOINTS.FILES, {
        params: {
          filename: query,
          limit: 100,
        },
      });
      const files = response.data.items || [];
      setResults(files);
    } catch (err: unknown) {
      const apiError = err as ApiError;
      console.error(`Error fetching files for column ${column}:`, err);
       setError(apiError.response?.data?.detail || 'Failed to load files');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFiles(debouncedSearchA, 'A');
  }, [debouncedSearchA, fetchFiles]);

  useEffect(() => {
    fetchFiles(debouncedSearchB, 'B');
  }, [debouncedSearchB, fetchFiles]);

  // Reset when modal closes
  useEffect(() => {
    if (!isOpen) {
      setFileASearch('');
      setFileBSearch('');
      setFileAResults([]);
      setFileBResults([]);
      setSelectedFileA(initialFileAId ? { id: initialFileAId, filename: '', language: '', task_id: '', status: '' } : null);
      setSelectedFileB(initialFileBId ? { id: initialFileBId, filename: '', language: '', task_id: '', status: '' } : null);
      setErrors({});
    }
  }, [isOpen, initialFileAId, initialFileBId]);

   // Load initial selections if provided
   useEffect(() => {
     if (isOpen && initialFileAId && !selectedFileA) {
       // Could pre-fetch file details for display
        api.get<{ items: FileInfo[] }>(API_ENDPOINTS.FILES_LIST).then(res => {
          const fileA = res.data.items.find((f) => f.id === initialFileAId);
          if (fileA) setSelectedFileA(fileA);
        });
      }
      if (isOpen && initialFileBId && !selectedFileB) {
        api.get<{ items: FileInfo[] }>(API_ENDPOINTS.FILES_LIST).then(res => {
          const fileB = res.data.items.find((f) => f.id === initialFileBId);
          if (fileB) setSelectedFileB(fileB);
        });
      }
    }, [isOpen, initialFileAId, initialFileBId, selectedFileA, selectedFileB]);

    // Fetch similarities for selected File A to compare against
    useEffect(() => {
      if (selectedFileA) {
        api.get<{ items: Array<{ id: string; similarity: number }> }>(API_ENDPOINTS.FILE_SIMILARITIES(selectedFileA.id))
          .then(res => {
            const map: Record<string, number> = {};
            res.data.items.forEach((item) => {
              map[item.id] = item.similarity;
            });
           setSimilaritiesMap(map);
         })
         .catch(err => {
           console.error('Failed to fetch similarities for selected File A', err);
           setSimilaritiesMap({});
         });
     } else {
       setSimilaritiesMap({});
     }
   }, [selectedFileA]);

  const handleSelectA = (file: FileResponse) => {
    setSelectedFileA(file);
    setErrors(e => ({ ...e, a: '' }));
  };

  const handleSelectB = (file: FileResponse) => {
    setSelectedFileB(file);
    setErrors(e => ({ ...e, b: '' }));
  };

  const handleCompare = () => {
    if (selectedFileA && selectedFileB && selectedFileA.id !== selectedFileB.id) {
      onSelect(selectedFileA, selectedFileB);
      onClose();
    }
  };

  const isCompareDisabled = !selectedFileA || !selectedFileB || selectedFileA.id === selectedFileB.id;

  const columnBg = useColorModeValue('gray.50', 'gray.700');
  const listBg = useColorModeValue('white', 'gray.700');
  const listBorderColor = useColorModeValue('gray.200', 'gray.600');

  const columnA = useMemo<ColumnConfig>(() => ({
    title: t('filePicker.fileA'),
    colorScheme: 'blue',
    search: fileASearch,
    onSearchChange: setFileASearch,
    results: [...fileAResults]
      .filter(f => f.id !== selectedFileB?.id)
      .sort((a, b) => (b.similarity ?? 0) - (a.similarity ?? 0)),
    loading: loadingA,
    selected: selectedFileA,
    onSelect: handleSelectA,
    error: errors.a,
    columnKey: 'A',
  }), [fileASearch, fileAResults, loadingA, selectedFileA, selectedFileB, errors.a]);

  const columnB = useMemo<ColumnConfig>(() => {
    // Filter out selected File A
    let results = fileBResults.filter(f => f.id !== selectedFileA?.id);

    if (selectedFileA && similaritiesMap && Object.keys(similaritiesMap).length > 0) {
      // Annotate with similarity against selected File A
      results = results.map(file => ({
        ...file,
        similarity: similaritiesMap[file.id] ?? null,
      }));
      // Sort: files with known similarity first (descending), then others
      results.sort((a, b) => {
        const simA = a.similarity ?? -1;
        const simB = b.similarity ?? -1;
        return simB - simA;
      });
    } else {
      // Default: sort by max similarity descending
      results.sort((a, b) => (b.similarity ?? 0) - (a.similarity ?? 0));
    }

    return {
      title: t('filePicker.fileB'),
      colorScheme: 'green',
      search: fileBSearch,
      onSearchChange: setFileBSearch,
      results,
      loading: loadingB,
      selected: selectedFileB,
      onSelect: handleSelectB,
      error: errors.b,
      columnKey: 'B',
    };
  }, [fileBSearch, fileBResults, loadingB, selectedFileB, errors.b, selectedFileA, similaritiesMap]);

interface VirtualFileListProps {
  results: FileInfo[];
  selectedA: FileInfo | null;
  selectedB: FileInfo | null;
  onSelectA: (file: FileInfo) => void;
  onSelectB: (file: FileInfo) => void;
  columnKey: 'A' | 'B';
  listBg: string;
  listBorderColor: string;
}

const VirtualFileList: React.FC<VirtualFileListProps> = ({
  results,
  selectedA,
  selectedB,
  onSelectA,
  onSelectB,
  columnKey,
  listBg,
  listBorderColor,
}) => {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: results.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 5,
  });

  return (
    <Box
      ref={parentRef}
      h={`${LIST_HEIGHT}px`}
      overflowY="auto"
      bg={listBg}
      border="1px solid"
      borderColor={listBorderColor}
      borderRadius="md"
    >
      <Box
        position="relative"
        width="100%"
        height={`${virtualizer.getTotalSize()}px`}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const file = results[virtualRow.index] as FileResponse;
          return (
            <Box
              key={file.id}
              position="absolute"
              top={0}
              left={0}
              width="100%"
              transform={`translateY(${virtualRow.start}px)`}
            >
              <FileItem
                file={file}
                isSelectedA={selectedA?.id === file.id}
                isSelectedB={selectedB?.id === file.id}
                onSelectA={onSelectA}
                onSelectB={onSelectB}
                column={columnKey}
              />
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

VirtualFileList.displayName = 'VirtualFileList';

interface ColumnConfig {
  title: string;
  colorScheme: 'blue' | 'green';
  search: string;
  onSearchChange: (value: string) => void;
  results: FileInfo[];
  loading: boolean;
  selected: FileInfo | null;
  onSelect: (file: FileInfo) => void;
  error: string | undefined;
  columnKey: 'A' | 'B';
}

const renderColumn = (col: ColumnConfig, listBg: string, listBorderColor: string, columnBg: string, t: (key: string) => string, otherSelected: FileInfo | null, handleSelectA: (file: FileResponse) => void, handleSelectB: (file: FileResponse) => void) => (
    <VStack flex={1} spacing={3} align="stretch">
      <Box>
        <Text fontWeight="bold" color={`${col.colorScheme}.500`} mb={2}>
          {col.title}
        </Text>
        <InputGroup size="sm">
          <InputLeftElement pointerEvents="none">
            <FiSearch color="gray.400" />
          </InputLeftElement>
           <Input
             placeholder={t('filePicker.search')}
             value={col.search}
             onChange={(e) => col.onSearchChange(e.target.value)}
           />
        </InputGroup>
      </Box>

      {col.error && (
        <Alert status="error" size="sm">
          <AlertIcon />
          {col.error}
        </Alert>
      )}

      {col.loading ? (
        <Box h={LIST_HEIGHT} display="flex" alignItems="center" justifyContent="center">
          <Spinner size="md" color={`${col.colorScheme}.500`} />
        </Box>
      ) : col.results.length === 0 ? (
        <Box h={LIST_HEIGHT} display="flex" alignItems="center" justifyContent="center">
           <Text color="gray.500" fontSize="sm">
             {col.search ? t('filePicker.noFiles') : t('filePicker.typeToSearch')}
           </Text>
        </Box>
       ) : (
         <VirtualFileList
           results={col.results}
           selectedA={col.columnKey === 'A' ? col.selected : otherSelected}
           selectedB={col.columnKey === 'B' ? col.selected : otherSelected}
           onSelectA={handleSelectA}
           onSelectB={handleSelectB}
           columnKey={col.columnKey}
           listBg={listBg}
           listBorderColor={listBorderColor}
         />
       )}

      {col.selected && (
        <Box p={2} bg={columnBg} borderRadius="md" borderWidth="1px" borderColor={listBorderColor}>
          <Text fontSize="xs" fontWeight="semibold" color={useColorModeValue('gray.600', 'gray.400')}>
            {t('filePicker.selected')}
          </Text>
          <Text fontSize="sm" isTruncated>
            {col.selected.filename}
          </Text>
        </Box>
      )}
    </VStack>
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="6xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent maxH="90vh" display="flex" flexDir="column">
        <ModalHeader>{t('filePicker.title')}</ModalHeader>
        <ModalCloseButton />

        <ModalBody flex={1} overflowY="auto" px={6} py={4}>
          <HStack spacing={4} align="stretch">
            {renderColumn(columnA, listBg, listBorderColor, columnBg, t, columnB.selected, handleSelectA, handleSelectB)}
            <Box w={8} display="flex" alignItems="center" justifyContent="center">
               <Text fontSize="2xl" fontWeight="bold" color="gray.400" whiteSpace="nowrap">
                 {t('filePicker.vs')}
               </Text>
            </Box>
            {renderColumn(columnB, listBg, listBorderColor, columnBg, t, columnA.selected, handleSelectA, handleSelectB)}
          </HStack>
        </ModalBody>

        <ModalFooter pt={4} borderTopWidth="1px">
          <VStack spacing={2} align="stretch" w="100%">
            {isCompareDisabled && selectedFileA && selectedFileB && selectedFileA.id === selectedFileB.id && (
               <Alert status="warning" size="sm">
                 <AlertIcon />
                 {t('filePicker.selfComparison')}
               </Alert>
            )}
            <HStack justify="flex-end">
              <Button variant="ghost" onClick={onClose}>
                {t('common:cancel')}
              </Button>
              <Button
                colorScheme="blue"
                leftIcon={<FiRefreshCw />}
                isDisabled={isCompareDisabled}
                onClick={handleCompare}
              >
                {t('filePicker.compare')}
              </Button>
            </HStack>
          </VStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default FilePickerModal;
