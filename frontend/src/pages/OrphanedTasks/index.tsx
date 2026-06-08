import React, { useState } from 'react';
import {
  Box,
  Card,
  CardBody,
  Text,
  Button,
  VStack,
  HStack,
  Flex,
  Icon,
  Badge,
  Checkbox,
  useColorModeValue,
  Spinner,
  useToast,
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
  TableContainer,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  Select,
  FormControl,
  FormLabel,
} from '@chakra-ui/react';
import { FiTrash2, FiInbox, FiRefreshCw, FiGitBranch } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getOrphanedTasks, cleanupOrphanedTasks, hardDeleteTask, reassignTask } from '../../services/api';
import api, { API_ENDPOINTS } from '../../services/api';

const OrphanedTasks: React.FC = () => {
  const { t } = useTranslation(['storage', 'common', 'sessions']);
  const toast = useToast();
  const queryClient = useQueryClient();
  const { isOpen: isCleanupOpen, onOpen: onCleanupOpen, onClose: onCleanupClose } = useDisclosure();
  const { isOpen: isReassignOpen, onOpen: onReassignOpen, onClose: onReassignClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const [selectedTasks, setSelectedTasks] = useState<Set<string>>(new Set());
  const [taskToReassign, setTaskToReassign] = useState<string | null>(null);
  const [selectedAssignment, setSelectedAssignment] = useState('');

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  const { data: assignmentsData } = useQuery({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data;
    },
  });

  const assignments = assignmentsData?.items || [];

  const { data: orphanedData, isLoading } = useQuery({
    queryKey: ['tasks', 'orphaned'],
    queryFn: async () => {
      const res = await getOrphanedTasks(100, 0);
      return res.data;
    },
  });

  const cleanupMutation = useMutation({
    mutationFn: async () => {
      const res = await cleanupOrphanedTasks();
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['tasks', 'orphaned'] });
      queryClient.invalidateQueries({ queryKey: ['tasks', 'sessions'] });
      queryClient.invalidateQueries({ queryKey: ['storage', 'usage'] });
      toast({
        title: t('common:success'),
        description: t('storage:cleanupSuccess', { tasks: data.tasks_deleted, files: data.files_deleted }),
        status: 'success',
        duration: 5000,
      });
    },
    onError: () => {
      toast({
        title: t('common:error'),
        description: t('storage:cleanupFailed'),
        status: 'error',
        duration: 4000,
      });
    },
  });

  const deleteSelectedMutation = useMutation({
    mutationFn: async (taskIds: string[]) => {
      const results = [];
      for (const taskId of taskIds) {
        const res = await hardDeleteTask(taskId);
        results.push(res.data);
      }
      return results;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', 'orphaned'] });
      queryClient.invalidateQueries({ queryKey: ['tasks', 'sessions'] });
      setSelectedTasks(new Set());
      toast({
        title: t('common:success'),
        description: t('sessions:taskDeleted'),
        status: 'success',
        duration: 3000,
      });
    },
  });

  const reassignMutation = useMutation({
    mutationFn: async ({ taskId, assignmentId }: { taskId: string; assignmentId: string }) => {
      const res = await reassignTask(taskId, assignmentId);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', 'orphaned'] });
      queryClient.invalidateQueries({ queryKey: ['tasks', 'sessions'] });
      queryClient.invalidateQueries({ queryKey: ['storage', 'usage'] });
      toast({
        title: t('common:success'),
        description: t('storage:reassignSuccess'),
        status: 'success',
        duration: 3000,
      });
      onReassignClose();
      setSelectedAssignment('');
      setTaskToReassign(null);
    },
    onError: () => {
      toast({
        title: t('common:error'),
        description: t('storage:reassignFailed'),
        status: 'error',
        duration: 4000,
      });
    },
  });

  const handleReassign = (taskId: string) => {
    setTaskToReassign(taskId);
    onReassignOpen();
  };

  const confirmReassign = () => {
    if (taskToReassign && selectedAssignment) {
      reassignMutation.mutate({ taskId: taskToReassign, assignmentId: selectedAssignment });
    }
  };

  const orphanedTasks = orphanedData?.items || [];

  const toggleTask = (taskId: string) => {
    setSelectedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedTasks.size === orphanedTasks.length) {
      setSelectedTasks(new Set());
    } else {
      setSelectedTasks(new Set(orphanedTasks.map((t: any) => t.task_id)));
    }
  };

  const handleDeleteSelected = () => {
    if (selectedTasks.size > 0) {
      deleteSelectedMutation.mutate(Array.from(selectedTasks));
    }
  };

  const handleCleanupAll = () => {
    onCleanupOpen();
  };

  const confirmCleanup = () => {
    cleanupMutation.mutate();
    onCleanupClose();
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (isLoading) {
    return (
      <Flex justify="center" py={16}>
        <Spinner size="lg" />
      </Flex>
    );
  }

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
      <Flex justify="space-between" align="center" mb={6}>
        <VStack align="flex-start" spacing={1}>
          <Text fontSize="2xl" fontWeight="bold">
            {t('storage:orphanedTasks')}
          </Text>
          <Text fontSize="sm" color="gray.500">
            {orphanedTasks.length} {t('orphanedCount', { count: orphanedTasks.length })}
          </Text>
        </VStack>
        <HStack spacing={3}>
          {selectedTasks.size > 0 && (
            <Button
              leftIcon={<FiTrash2 />}
              colorScheme="red"
              variant="outline"
              onClick={handleDeleteSelected}
              isLoading={deleteSelectedMutation.isPending}
            >
              {t('common:delete')} Selected ({selectedTasks.size})
            </Button>
          )}
          <Button
            leftIcon={<FiTrash2 />}
            colorScheme="red"
            onClick={handleCleanupAll}
            isLoading={cleanupMutation.isPending}
            isDisabled={orphanedTasks.length === 0}
          >
            {t('storage:cleanupOrphaned')}
          </Button>
          <Button
            leftIcon={<FiRefreshCw />}
            variant="outline"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['tasks', 'orphaned'] })}
          >
            {t('common:refresh')}
          </Button>
        </HStack>
      </Flex>

      {orphanedTasks.length === 0 ? (
        <Card bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor}>
          <Flex direction="column" align="center" justify="center" py={16} color="gray.500">
            <Icon as={FiInbox} boxSize={16} mb={4} opacity={0.5} />
            <Text fontWeight="medium" fontSize="lg">{t('noOrphanedTasks')}</Text>
            <Text fontSize="sm">{t('orphanedTasksDesc')}</Text>
          </Flex>
        </Card>
      ) : (
        <Card bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor}>
          <CardBody p={0}>
            <TableContainer>
              <Table variant="simple" size="sm">
                <Thead>
                  <Tr>
                    <Th w="40px">
                      <Checkbox
                        isChecked={selectedTasks.size === orphanedTasks.length && orphanedTasks.length > 0}
                        isIndeterminate={selectedTasks.size > 0 && selectedTasks.size < orphanedTasks.length}
                        onChange={toggleAll}
                      />
                    </Th>
                    <Th>{t('common:session')}</Th>
                    <Th isNumeric>{t('common:files')}</Th>
                    <Th isNumeric>{t('common:pairs')}</Th>
                    <Th>{t('common:status')}</Th>
                    <Th>{t('common:created')}</Th>
                    <Th w="160px"></Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {orphanedTasks.map((task: any) => (
                    <Tr key={task.task_id} _hover={{ bg: 'gray.50' }}>
                      <Td>
                        <Checkbox
                          isChecked={selectedTasks.has(task.task_id)}
                          onChange={() => toggleTask(task.task_id)}
                        />
                      </Td>
                      <Td>
                        <Text fontSize="sm" fontFamily="monospace" noOfLines={1}>
                          {task.task_id.substring(0, 12)}...
                        </Text>
                      </Td>
                      <Td isNumeric>
                        <Badge variant="subtle" colorScheme="gray">{task.files_count || 0}</Badge>
                      </Td>
                      <Td isNumeric>
                        <Badge variant="subtle" colorScheme="gray">{task.total_pairs || 0}</Badge>
                      </Td>
                      <Td>
                        <Badge
                          colorScheme={task.status === 'completed' ? 'green' : task.status === 'failed' ? 'red' : 'orange'}
                          variant="subtle"
                          fontSize="xs"
                        >
                          {task.status}
                        </Badge>
                      </Td>
                      <Td fontSize="sm" color="gray.500">
                        {formatDate(task.created_at)}
                      </Td>
                      <Td>
                        <HStack spacing={1}>
                          <Button
                            size="xs"
                            colorScheme="blue"
                            variant="ghost"
                            leftIcon={<FiGitBranch />}
                            onClick={() => handleReassign(task.task_id)}
                          >
                            {t('storage:reassign')}
                          </Button>
                          <Button
                            size="xs"
                            colorScheme="red"
                            variant="ghost"
                            leftIcon={<FiTrash2 />}
                            onClick={() => {
                              deleteSelectedMutation.mutate([task.task_id]);
                            }}
                            isLoading={deleteSelectedMutation.isPending}
                          >
                            {t('common:delete')}
                          </Button>
                        </HStack>
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </TableContainer>
          </CardBody>
        </Card>
      )}

      <AlertDialog
        isOpen={isCleanupOpen}
        leastDestructiveRef={cancelRef}
        onClose={onCleanupClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('storage:cleanupOrphaned')}
            </AlertDialogHeader>
            <AlertDialogBody>
              {t('cleanupAllConfirm', { count: orphanedTasks.length })}
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onCleanupClose}>
                {t('common:cancel')}
              </Button>
              <Button
                colorScheme="red"
                onClick={confirmCleanup}
                ml={3}
                isLoading={cleanupMutation.isPending}
              >
                {t('common:delete')} {t('common:all')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <Modal isOpen={isReassignOpen} onClose={onReassignClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader fontSize="lg" fontWeight="bold">
            {t('storage:reassignTask')}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <Text fontSize="sm" color="gray.500" mb={4}>
              {t('storage:reassignDescription')}
            </Text>
            <FormControl>
              <FormLabel>{t('storage:selectAssignment')}</FormLabel>
              <Select
                value={selectedAssignment}
                onChange={(e) => setSelectedAssignment(e.target.value)}
                placeholder={t('storage:selectAssignmentPlaceholder')}
              >
                {assignments.map((assignment: any) => (
                  <option key={assignment.id} value={assignment.id}>
                    {assignment.name}
                  </option>
                ))}
              </Select>
            </FormControl>
          </ModalBody>
          <AlertDialogFooter>
            <Button onClick={onReassignClose}>
              {t('common:cancel')}
            </Button>
            <Button
              colorScheme="blue"
              onClick={confirmReassign}
              ml={3}
              isLoading={reassignMutation.isPending}
              isDisabled={!selectedAssignment}
              leftIcon={<FiGitBranch />}
            >
              {t('storage:reassign')}
            </Button>
          </AlertDialogFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default OrphanedTasks;
