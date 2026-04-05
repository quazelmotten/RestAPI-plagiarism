import React, { useState, useMemo } from 'react';
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
  SimpleGrid,
  Tooltip,
  Spinner,
  useColorModeValue,
  Icon,
} from '@chakra-ui/react';
import { FiSearch, FiCheck, FiAlertCircle, FiActivity, FiLayers, FiClock, FiCheckCircle, FiFolder, FiAlertTriangle } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import type { TaskListItem } from '../../types';
import { getStatusColorScheme } from '../../utils/statusColors';

interface TaskPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (task: TaskListItem) => void;
  tasks: TaskListItem[];
  selectedTaskId?: string;
  loading?: boolean;
}

const formatDate = (dateString?: string) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  const datePart = date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
  const timePart = date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  return `${datePart} ${timePart}`;
};

const TaskPickerModal: React.FC<TaskPickerModalProps> = ({
  isOpen,
  onClose,
  onSelect,
  tasks,
  selectedTaskId,
  loading,
}) => {
  const { t } = useTranslation(['results', 'common', 'status']);
  const [searchQuery, setSearchQuery] = useState('');
  const cardBg = useColorModeValue('white', 'gray.700');
  const selectedBg = useColorModeValue('blue.50', 'blue.900');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');

  const filteredTasks = useMemo(() => {
    if (!searchQuery.trim()) return tasks;
    const query = searchQuery.toLowerCase();
    return tasks.filter(task => task.task_id.toLowerCase().includes(query));
  }, [tasks, searchQuery]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <FiCheckCircle color="#48bb78" />;
      case 'failed':
        return <FiAlertCircle color="#f56565" />;
      case 'processing':
        return <FiActivity color="#ed8936" />;
      case 'indexing':
        return <FiLayers color="#4299e1" />;
      case 'finding_pairs':
        return <FiLayers color="#9f7aea" />;
      default:
        return <FiLayers color="#a0aec0" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'green.500';
      case 'failed':
        return 'red.500';
      case 'processing':
        return 'orange.500';
      case 'indexing':
        return 'blue.500';
      case 'finding_pairs':
        return 'purple.500';
      default:
        return 'gray.500';
    }
  };

  const handleSelect = (task: TaskListItem) => {
    onSelect(task);
    onClose();
    setSearchQuery('');
  };

  const isEmpty = filteredTasks.length === 0;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent maxH="80vh" display="flex" flexDir="column">
        <ModalHeader>{t('taskPicker.title')}</ModalHeader>
        <ModalCloseButton />

         <ModalBody flex={1} overflowY="auto" px={6} py={4}>
           <VStack spacing={4} align="stretch">
             <InputGroup size="sm">
               <InputLeftElement pointerEvents="none">
                 <FiSearch color="gray.400" />
               </InputLeftElement>
                <Input
                   placeholder={t('taskPicker.search')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                />
             </InputGroup>

             {loading && tasks.length === 0 ? (
               <Box textAlign="center" py={8}>
                 <Spinner />
               </Box>
             ) : isEmpty ? (
              <Box textAlign="center" py={8}>
                <Text color="gray.500">
                   {searchQuery ? t('taskPicker.noMatches') : t('taskPicker.noTasks')}
                </Text>
              </Box>
            ) : (
              <VStack spacing={2} align="stretch">
                {filteredTasks.map((task) => {
                  const isSelected = task.task_id === selectedTaskId;
                  return (
                    <Tooltip
                      key={task.task_id}
                      label={t('taskPicker.tooltip', { id: task.task_id, date: formatDate(task.created_at) })}
                      placement="left"
                      hasArrow
                    >
                       <Box
                         bg={isSelected ? selectedBg : cardBg}
                         borderLeft="4px solid"
                         borderLeftColor={
                           isSelected ? 'blue.500' : 
                           getStatusColor(task.status)
                         }
                         px={4}
                         py={3}
                         cursor="pointer"
                         onClick={() => handleSelect(task)}
                         _hover={{ bg: isSelected ? selectedBg : hoverBg }}
                         transition="background 0.15s"
                         borderRadius="md"
                       >
                        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={2} alignItems="center">
                          <HStack spacing={3}>
                            {getStatusIcon(task.status)}
                            <Box flex={1} minW={0}>
                              <Text fontWeight="semibold" fontSize="sm" isTruncated title={task.task_id}>
                                {task.task_id}
                              </Text>
                              <HStack mt={1} spacing={2}>
                                <Badge size="sm" colorScheme={getStatusColorScheme(task.status)}>
                                  {t(`status:${task.status}`)}
                                </Badge>
                                <HStack spacing={1}>
                                  <FiClock />
                                  <Text fontSize="xs" color="gray.500">
                                    {formatDate(task.created_at)}
                                  </Text>
                                </HStack>
                              </HStack>
                            </Box>
                          </HStack>

                          <HStack spacing={3} justify="flex-end" wrap="wrap">
                            <Badge size="sm" colorScheme="gray" variant="subtle">
                              <HStack spacing={1}>
                                <Icon as={FiFolder} boxSize={3} />
                                <Text>{t('taskPicker.fileCount', { count: task.files_count || 0 })}</Text>
                              </HStack>
                            </Badge>
                            <Badge size="sm" colorScheme="blue" variant="subtle">
                              {t('taskPicker.pairCount', { count: task.total_pairs })}
                            </Badge>
                            {(task.high_similarity_count || 0) > 0 && (
                              <Badge size="sm" colorScheme="red" variant="subtle">
                                <HStack spacing={1}>
                                  <Icon as={FiAlertTriangle} boxSize={3} />
                                  <Text>{t('taskPicker.highWarning', { count: task.high_similarity_count })}</Text>
                                </HStack>
                              </Badge>
                            )}
                            {['indexing', 'finding_intra_pairs', 'finding_cross_pairs', 'storing_results'].includes(task.status) && task.progress && (
                              <Badge size="sm" colorScheme="purple" variant="subtle">
                                {task.progress.display}
                              </Badge>
                            )}
                            {isSelected && (
                              <FiCheck color="blue.500" />
                            )}
                          </HStack>
                        </SimpleGrid>
                      </Box>
                    </Tooltip>
                  );
                })}
              </VStack>
            )}
          </VStack>
        </ModalBody>

        <ModalFooter pt={4} borderTopWidth="1px">
          <HStack justify="flex-end" w="100%">
            <Button variant="ghost" onClick={onClose}>
              {t('common:cancel')}
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

TaskPickerModal.displayName = 'TaskPickerModal';

export default TaskPickerModal;
