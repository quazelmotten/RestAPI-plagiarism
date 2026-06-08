import React, { useState } from 'react';
import {
  Box,
  Flex,
  HStack,
  VStack,
  Text,
  Badge,
  Button,
  IconButton,
  useColorModeValue,
  useToast,
  Icon,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  useDisclosure,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
} from '@chakra-ui/react';
import { FiCheckCircle, FiAlertCircle, FiActivity, FiClock, FiLayers, FiDownload, FiTrash2, FiLink } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../../../services/api';
import { useUnassignUpload } from '../../../hooks/useUploadQueries';
import { getSimilarityColor, getStatusColorScheme } from '../../../utils/statusColors';
import type { TaskListItem } from '../../../types';

interface AssignmentUploadsTabProps {
  tasks: TaskListItem[];
  selectedTaskId: string;
  onTaskSelect: (taskId: string) => void;
  onExportPdf: (assignmentId: string, taskId?: string) => void;
  isExporting: boolean;
  assignmentId: string;
}

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

const AssignmentUploadsTab: React.FC<AssignmentUploadsTabProps> = ({
  tasks,
  selectedTaskId,
  onTaskSelect,
  onExportPdf,
  isExporting,
  assignmentId,
}) => {
  const { t } = useTranslation(['assignments', 'common', 'status', 'results']);
  const toast = useToast();
  const queryClient = useQueryClient();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const [taskToDelete, setTaskToDelete] = useState<string | null>(null);

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const selectedRowBg = useColorModeValue('brand.50', 'whiteAlpha.100');
  const selectedRowHoverBg = useColorModeValue('brand.100', 'whiteAlpha.200');

  const deleteTaskMutation = useMutation({
    mutationFn: async (taskId: string) => {
      const res = await api.delete(API_ENDPOINTS.HARD_DELETE_TASK(taskId));
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignmentFull', assignmentId] });
      toast({ title: t('common:success'), description: t('sessions:taskDeleted'), status: 'success', duration: 3000 });
    },
    onError: () => {
      toast({ title: t('common:error'), description: t('sessions:deleteFailed'), status: 'error', duration: 4000 });
    },
  });

  const unassignUpload = useUnassignUpload();

  const handleUnassignTask = async (taskId: string) => {
    try {
      await unassignUpload.mutateAsync(taskId);
      queryClient.invalidateQueries({ queryKey: ['assignmentFull', assignmentId] });
      toast({ title: t('common:success'), description: t('assignments:uploadUnassigned'), status: 'success', duration: 3000 });
    } catch {
      toast({ title: t('common:error'), description: t('assignments:unassignFailed'), status: 'error', duration: 4000 });
    }
  };

  const handleDeleteTask = (taskId: string) => {
    setTaskToDelete(taskId);
    onOpen();
  };

  const confirmDeleteTask = () => {
    if (taskToDelete) {
      deleteTaskMutation.mutate(taskToDelete);
    }
    onClose();
  };

  if (tasks.length === 0) {
    return (
      <Flex flex={1} align="center" justify="center" direction="column" color="gray.500" py={12}>
        <Icon as={FiLayers} boxSize={10} mb={3} />
        <Text fontWeight="medium">{t('assignments:noUploads')}</Text>
        <Text fontSize="sm" mt={1}>{t('assignments:uploadFilesToStart')}</Text>
      </Flex>
    );
  }

  return (
    <Box flex={1} display="flex" flexDirection="column" minH={0} overflow="auto">
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
          {tasks.map((task) => (
            <Tr
              key={task.task_id}
              bg={selectedTaskId === task.task_id ? selectedRowBg : undefined}
              cursor="pointer"
              onClick={() => onTaskSelect(task.task_id)}
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
                  isLoading={isExporting}
                  isDisabled={(task.total_pairs ?? 0) === 0}
                  onClick={(e) => {
                    e.stopPropagation();
                    onExportPdf(assignmentId, task.task_id);
                  }}
                />
              </Td>
              <Td>
                <HStack spacing={1}>
                  <IconButton
                    aria-label={t('assignments:unassignFromAssignment')}
                    icon={<FiLink />}
                    size="xs"
                    variant="ghost"
                    colorScheme="orange"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleUnassignTask(task.task_id);
                    }}
                  />
                  <IconButton
                    aria-label={t('assignments:deleteTask')}
                    icon={<FiTrash2 />}
                    size="xs"
                    variant="ghost"
                    colorScheme="red"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteTask(task.task_id);
                    }}
                  />
                </HStack>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>

      <AlertDialog
        isOpen={isOpen}
        leastDestructiveRef={cancelRef}
        onClose={onClose}
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
              <Button ref={cancelRef} onClick={onClose}>
                {t('common:cancel')}
              </Button>
              <Button
                colorScheme="red"
                onClick={confirmDeleteTask}
                isLoading={deleteTaskMutation.isPending}
                ml={3}
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

export default AssignmentUploadsTab;
