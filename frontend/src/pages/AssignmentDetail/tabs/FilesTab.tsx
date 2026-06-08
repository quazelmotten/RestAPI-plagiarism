import React, { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Box,
  Flex,
  HStack,
  VStack,
  Text,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
  Button,
  IconButton,
  useColorModeValue,
  Spinner,
  Icon,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Badge,
  Checkbox,
  Card,
  CardBody,
} from '@chakra-ui/react';
import { FiSearch, FiChevronUp, FiChevronDown, FiEye, FiTrash2, FiDownload } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import type { AssignmentFullFile } from '../../../types';
import { getSimilarityColor } from '../../../utils/statusColors';

interface AssignmentFilesTabProps {
  files: AssignmentFullFile[];
  totalFiles: number;
  tasks: Array<{ task_id: string }>;
  isLoading: boolean;
  isFetching: boolean;
  page: number;
  onPageChange: (page: number) => void;
  filesPerPage: number;
  onViewFile: (fileId: string, filename: string) => void;
  onDeleteFiles?: (fileIds: string[]) => void;
  onDownloadFiles?: (fileIds: string[]) => void;
}

const AssignmentFilesTab: React.FC<AssignmentFilesTabProps> = ({
  files,
  totalFiles,
  tasks,
  isLoading,
  isFetching,
  page,
  onPageChange,
  filesPerPage,
  onViewFile,
  onDeleteFiles,
  onDownloadFiles,
}) => {
  const { t } = useTranslation(['assignments', 'common', 'review']);
  const [fileFilterName, setFileFilterName] = useState('');
  const [fileFilterTask, setFileFilterTask] = useState('');
  const [fileSortCol, setFileSortCol] = useState<'filename' | 'task_id' | 'max_similarity'>('filename');
  const [fileSortDir, setFileSortDir] = useState<'asc' | 'desc'>('asc');
  const [colWidths, setColWidths] = useState({ filename: 300, task: 120, maxSim: 120 });
  const [resizingCol, setResizingCol] = useState<string | null>(null);
  const [resizeStartX, setResizeStartX] = useState(0);
  const [resizeStartW, setResizeStartW] = useState(0);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const displayedFiles = useMemo((): AssignmentFullFile[] => {
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
  }, [files, fileFilterName, fileFilterTask, fileSortCol, fileSortDir]);

  const totalFilePages = Math.max(1, Math.ceil(totalFiles / filesPerPage));

  const handleFileSort = (col: 'filename' | 'task_id' | 'max_similarity') => {
    if (fileSortCol === col) setFileSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setFileSortCol(col); setFileSortDir('asc'); }
  };

  const handleSelectFile = useCallback((fileId: string, selected: boolean) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (selected) next.add(fileId);
      else next.delete(fileId);
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    if (selectedFiles.size === displayedFiles.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(displayedFiles.map(f => f.id)));
    }
  }, [displayedFiles, selectedFiles.size]);

  const handleBulkDelete = () => {
    if (onDeleteFiles && selectedFiles.size > 0) {
      onDeleteFiles(Array.from(selectedFiles));
      setSelectedFiles(new Set());
    }
  };

  const handleBulkDownload = () => {
    if (onDownloadFiles && selectedFiles.size > 0) {
      onDownloadFiles(Array.from(selectedFiles));
    }
  };

  const handleResizeStart = useCallback((col: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setResizingCol(col);
    setResizeStartX(e.clientX);
    setResizeStartW(colWidths[col as keyof typeof colWidths]);
  }, [colWidths]);

  useEffect(() => {
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

  const renderResizeHandle = (col: string) => (
    <Box
      position="absolute" right={0} top={0} bottom={0} w="4px" cursor="col-resize" zIndex={2}
      bg={resizingCol === col ? 'brand.400' : 'transparent'}
      _hover={{ bg: 'brand.300' }}
      onMouseDown={(e: React.MouseEvent) => handleResizeStart(col, e)}
    />
  );

  if (isLoading) {
    return <Flex justify="center" py={8}><Spinner size="lg" /></Flex>;
  }

  return (
    <Box flex={1} display="flex" flexDirection="column" minH={0} overflow="hidden">
      {selectedFiles.size > 0 && (onDeleteFiles || onDownloadFiles) && (
        <Card bg="brand.50" borderColor="brand.200" borderWidth={1} mb={3}>
          <CardBody py={2}>
            <HStack spacing={3}>
              <Text fontSize="sm" fontWeight="medium">{t('review:selected', { count: selectedFiles.size })}</Text>
              {onDownloadFiles && (
                <Button size="sm" leftIcon={<FiDownload />} onClick={handleBulkDownload}>
                  {t('common:buttons.download')}
                </Button>
              )}
              {onDeleteFiles && (
                <Button size="sm" colorScheme="red" leftIcon={<FiTrash2 />} onClick={handleBulkDelete}>
                  {t('common:delete')}
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => setSelectedFiles(new Set())}>
                {t('common:clear')}
              </Button>
            </HStack>
          </CardBody>
        </Card>
      )}

      <HStack spacing={3} mb={3} flexShrink={0} flexWrap="wrap">
        <InputGroup size="sm" maxW="250px">
          <InputLeftElement pointerEvents="none"><Icon as={FiSearch} color={mutedColor} /></InputLeftElement>
          <Input placeholder={t('common:placeholders.filterByFilename')} value={fileFilterName} onChange={(e) => setFileFilterName(e.target.value)} />
        </InputGroup>
        <Select size="sm" w="180px" value={fileFilterTask} onChange={(e) => { setFileFilterTask(e.target.value); }}>
          <option value="">{t('review:allTasks')}</option>
          {tasks.map((task) => (
            <option key={task.task_id} value={task.task_id}>{task.task_id.substring(0, 8)}...</option>
          ))}
        </Select>
        <Text fontSize="xs" color={mutedColor}>{totalFiles} {t('common:files')}</Text>
        {(onDeleteFiles || onDownloadFiles) && displayedFiles.length > 0 && (
          <Checkbox isChecked={selectedFiles.size === displayedFiles.length && displayedFiles.length > 0} onChange={handleSelectAll}>
            {t('assignments:selectAll')}
          </Checkbox>
        )}
      </HStack>

      <Box flex={1} overflowY="auto">
        <TableContainer>
          <Table variant="simple" size="sm">
            <colgroup>
              {(onDeleteFiles || onDownloadFiles) && <col style={{ width: '40px' }} />}
              <col style={{ width: `${colWidths.filename}px` }} />
              <col style={{ width: `${colWidths.task}px` }} />
              <col style={{ width: `${colWidths.maxSim}px` }} />
              <col style={{ width: '80px' }} />
            </colgroup>
            <Thead position="sticky" top={0} bg={cardBg} zIndex={1}>
              <Tr>
                {(onDeleteFiles || onDownloadFiles) && <Th></Th>}
                <Th position="relative" cursor="pointer" userSelect="none" _hover={{ bg: hoverBg }} onClick={() => handleFileSort('filename')} pr="20px">
                  <HStack spacing={1}>
                    <Text as="span">{t('assignments:filename')}</Text>
                    {fileSortCol === 'filename' && <Icon as={fileSortDir === 'asc' ? FiChevronUp : FiChevronDown} boxSize={3} />}
                  </HStack>
                  {renderResizeHandle('filename')}
                </Th>
                <Th position="relative" cursor="pointer" userSelect="none" _hover={{ bg: hoverBg }} onClick={() => handleFileSort('task_id')} pr="20px">
                  <HStack spacing={1}>
                    <Text as="span">{t('assignments:task')}</Text>
                    {fileSortCol === 'task_id' && <Icon as={fileSortDir === 'asc' ? FiChevronUp : FiChevronDown} boxSize={3} />}
                  </HStack>
                  {renderResizeHandle('task')}
                </Th>
                <Th position="relative" cursor="pointer" userSelect="none" _hover={{ bg: hoverBg }} onClick={() => handleFileSort('max_similarity')} pr="20px">
                  <HStack spacing={1}>
                    <Text as="span">{t('assignments:maxSim')}</Text>
                    {fileSortCol === 'max_similarity' && <Icon as={fileSortDir === 'asc' ? FiChevronUp : FiChevronDown} boxSize={3} />}
                  </HStack>
                  {renderResizeHandle('maxSim')}
                </Th>
                <Th></Th>
              </Tr>
            </Thead>
            <Tbody>
              {displayedFiles.map((file) => (
                <Tr key={file.id} _hover={{ bg: hoverBg }} bg={selectedFiles.has(file.id) ? 'brand.50' : undefined}>
                  {(onDeleteFiles || onDownloadFiles) && (
                    <Td>
                      <Checkbox
                        isChecked={selectedFiles.has(file.id)}
                        onChange={(e) => handleSelectFile(file.id, e.target.checked)}
                      />
                    </Td>
                  )}
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
                    <Button size="xs" leftIcon={<FiEye />} variant="ghost" onClick={() => onViewFile(file.id, file.filename)}>{t('common:view')}</Button>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
        {displayedFiles.length === 0 && !isFetching && (
          <Box textAlign="center" py={8} color={mutedColor}><Text>{t('review:noFilesInAssignment')}</Text></Box>
        )}
        {isFetching && (
          <Flex justify="center" py={4}><Spinner size="sm" /></Flex>
        )}
      </Box>

      {totalFilePages > 1 && (
        <HStack spacing={2} mt={3} flexShrink={0} justifyContent="center">
          <Button size="xs" onClick={() => onPageChange(Math.max(0, page - 1))} isDisabled={page === 0}>
            {t('common:prev')}
          </Button>
          <Text fontSize="xs" color={mutedColor}>
            {t('common:pageOf', { current: page + 1, total: totalFilePages })}
          </Text>
          <Button size="xs" onClick={() => onPageChange(Math.min(totalFilePages - 1, page + 1))} isDisabled={page >= totalFilePages - 1}>
            {t('common:next')}
          </Button>
        </HStack>
      )}
    </Box>
  );
};

export default AssignmentFilesTab;
