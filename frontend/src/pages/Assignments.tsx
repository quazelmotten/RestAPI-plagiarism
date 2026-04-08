import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Text,
  Button,
  VStack,
  HStack,
  useToast,
  useColorModeValue,
  Input,
  InputGroup,
  InputLeftElement,
  IconButton,
  Flex,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Badge,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  Icon,
  Spinner,
  Collapse,
  Select,
  Tooltip,
} from '@chakra-ui/react';
import {
  FiPlus,
  FiSearch,
  FiEdit2,
  FiTrash2,
  FiFolder,
  FiChevronDown,
  FiChevronRight,
  FiInbox,
} from 'react-icons/fi';
import { MdDragIndicator } from 'react-icons/md';
import {
  DndContext,
  closestCenter,
  pointerWithin,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  useDraggable,
  useDroppable,
} from '@dnd-kit/core';
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../services/api';
import { useSubjects, useUncategorizedAssignments, useCreateSubject, useUpdateSubject, useDeleteSubject, useRestoreSubject, useRestoreAssignment } from '../hooks/useSubjects';

interface Assignment {
  id: string;
  name: string;
  description: string | null;
  subject_id: string | null;
  created_at: string | null;
  tasks_count: number;
  files_count: number;
}

interface AssignmentsResponse {
  items: Assignment[];
  total: number;
  limit: number;
  offset: number;
}

interface Subject {
  id: string;
  name: string;
  description: string | null;
  created_at: string | null;
  assignments_count: number;
}

const LOCAL_STORAGE_KEY = 'assignments-subjects-collapsed';

interface DraggableAssignmentRowProps {
  assignment: Assignment;
  hoverBg: string;
  mutedColor: string;
  t: (key: string) => string;
  isDragging?: boolean;
  onEdit: (a: Assignment) => void;
  onDelete: (a: Assignment) => void;
}

  const DraggableAssignmentRow: React.FC<DraggableAssignmentRowProps> = ({
    assignment, hoverBg, mutedColor, t, isDragging, onEdit, onDelete,
  }) => {
    const { attributes, listeners, setNodeRef, transform } = useDraggable({
      id: assignment.id,
      data: { assignmentId: assignment.id, currentSubjectId: assignment.subject_id },
    });
    const style = {
      transform: CSS.Translate.toString(transform),
      opacity: isDragging ? 0.4 : 1,
    };

    return (
      <Tr ref={setNodeRef} style={style} _hover={{ bg: hoverBg }}>
        <Td {...attributes} {...listeners} cursor="grab">
          <Icon
            as={MdDragIndicator}
            boxSize={4}
            color="gray.400"
            _hover={{ color: 'brand.500' }}
          />
        </Td>
        <Td fontWeight="medium">{assignment.name}</Td>
        <Td maxW="300px" isTruncated>{assignment.description || '—'}</Td>
        <Td isNumeric>
          <Badge colorScheme="blue">{assignment.tasks_count}</Badge>
        </Td>
        <Td isNumeric>
          <Badge colorScheme="green">{assignment.files_count}</Badge>
        </Td>
        <Td fontSize="sm" color={mutedColor}>
          {assignment.created_at ? new Date(assignment.created_at).toLocaleDateString() : '—'}
        </Td>
        <Td>
          <HStack spacing={1}>
            <IconButton
              aria-label="Edit assignment"
              icon={<FiEdit2 />}
              size="xs"
              variant="ghost"
              onClick={() => onEdit(assignment)}
            />
            <IconButton
              aria-label="Delete assignment"
              icon={<FiTrash2 />}
              size="xs"
              variant="ghost"
              colorScheme="red"
              onClick={() => onDelete(assignment)}
            />
          </HStack>
        </Td>
      </Tr>
    );
  };

const SubjectHeader: React.FC<{
  isOver: boolean;
  isUncategorized?: boolean;
  children: React.ReactNode;
}> = ({ isOver, isUncategorized, children }) => {
  return (
    <Flex
      bg={isOver ? (isUncategorized ? 'gray.100' : 'purple.50') : undefined}
      borderColor={isOver ? (isUncategorized ? 'gray.400' : 'purple.400') : 'transparent'}
      borderWidth="2px"
      borderStyle="dashed"
      transition="all 0.15s"
      px={4}
      py={3}
      borderRadius="md"
      align="center"
      justify="space-between"
      cursor="pointer"
      _hover={{ bg: isOver ? undefined : useColorModeValue('gray.200', 'gray.600') }}
    >
      {children}
    </Flex>
  );
};

interface DroppableSubjectContainerProps {
  subjectId: string;
  children: (ctx: { isOver: boolean }) => React.ReactNode;
}

const DroppableSubjectContainer: React.FC<DroppableSubjectContainerProps> = ({ subjectId, children }) => {
  const { isOver, setNodeRef } = useDroppable({
    id: `subject-drop:${subjectId}`,
  });

  return <Box ref={setNodeRef}>{children({ isOver })}</Box>;
};

const Assignments: React.FC = () => {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { t } = useTranslation(['assignments', 'common']);

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');
  const subjectBg = useColorModeValue('gray.50', 'gray.750');
  const headerBg = useColorModeValue('gray.100', 'gray.700');

  const [searchQuery, setSearchQuery] = useState('');
  const [editingAssignment, setEditingAssignment] = useState<Assignment | null>(null);
  const [deletingAssignment, setDeletingAssignment] = useState<Assignment | null>(null);
  const [editingSubject, setEditingSubject] = useState<Subject | null>(null);
  const [deletingSubject, setDeletingSubject] = useState<Subject | null>(null);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newSubjectId, setNewSubjectId] = useState<string | null>(null);
  const [collapsedSubjects, setCollapsedSubjects] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [activeDragId, setActiveDragId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const { isOpen: isAssignmentModalOpen, onOpen: onAssignmentModalOpen, onClose: onAssignmentModalClose } = useDisclosure();
  const { isOpen: isDeleteAssignmentOpen, onOpen: onDeleteAssignmentOpen, onClose: onDeleteAssignmentClose } = useDisclosure();
  const { isOpen: isSubjectModalOpen, onOpen: onSubjectModalOpen, onClose: onSubjectModalClose } = useDisclosure();
  const { isOpen: isDeleteSubjectOpen, onOpen: onDeleteSubjectOpen, onClose: onDeleteSubjectClose } = useDisclosure();

    const { data, isLoading: assignmentsLoading } = useQuery<AssignmentsResponse>({
      queryKey: ['assignments'],
      queryFn: async () => {
        const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
        return res.data;
      },
    });

    const { data: subjects, isLoading: subjectsLoading } = useSubjects();
    const { data: uncategorizedAssignments, isLoading: uncategorizedLoading } = useUncategorizedAssignments();

    const createSubjectMutation = useCreateSubject();
    const updateSubjectMutation = useUpdateSubject();
    const deleteSubjectMutation = useDeleteSubject();
    const restoreSubjectMutation = useRestoreSubject();

    const createMutation = useMutation({
      mutationFn: async (payload: { name: string; description: string | null; subject_id: string | null }) => {
        const res = await api.post(API_ENDPOINTS.ASSIGNMENTS, payload);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['assignments'] });
        queryClient.invalidateQueries({ queryKey: ['subjects'] });
        toast({ title: t('toasts.created'), status: 'success', duration: 3000 });
        closeAssignmentModal();
      },
       onError: (err: unknown) => {
         const msg = err && typeof err === 'object' && 'response' in err
           ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
           : t('common:error');
         toast({ title: t('common:error'), description: msg, status: 'error', duration: 5000 });
       },
    });

    const updateMutation = useMutation({
      mutationFn: async ({ id, payload }: { id: string; payload: { name?: string; description?: string | null; subject_id?: string | null } }) => {
        const res = await api.patch(`${API_ENDPOINTS.ASSIGNMENTS}/${id}`, payload);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['assignments'] });
        queryClient.invalidateQueries({ queryKey: ['subjects'] });
        toast({ title: t('toasts.updated'), status: 'success', duration: 3000 });
        closeAssignmentModal();
      },
      onError: () => {
        toast({ title: t('common:error'), description: t('toasts.updateFailed'), status: 'error', duration: 5000 });
      },
    });

    const restoreAssignmentMutation = useRestoreAssignment();

    const deleteMutation = useMutation({
      mutationFn: async (assignment: Assignment) => {
        await api.delete(`${API_ENDPOINTS.ASSIGNMENTS}/${assignment.id}`);
      },
      onSuccess: (_, assignment) => {
        toast({
          title: t('toasts.deleted'),
          description: (
            <Button
              size="sm"
              colorScheme="blue"
              mt={2}
              onClick={() => {
                restoreAssignmentMutation.mutate(assignment.id);
              }}
              width="100%"
            >
              {t('common:undo')}
            </Button>
          ),
          status: 'warning',
          duration: 8000,
          isClosable: true,
        });
        queryClient.invalidateQueries({ queryKey: ['assignments'] });
        queryClient.invalidateQueries({ queryKey: ['subjects'] });
        setDeletingAssignment(null);
        onDeleteAssignmentClose();
      },
      onError: () => {
        toast({ title: t('common:error'), description: t('toasts.deleteFailed'), status: 'error', duration: 5000 });
      },
    });

  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(Array.from(collapsedSubjects)));
    } catch {
    }
  }, [collapsedSubjects]);

  const moveAssignmentMutation = useMutation({
    mutationFn: async ({ id, subject_id }: { id: string; subject_id: string | null }) => {
      const res = await api.patch(`${API_ENDPOINTS.ASSIGNMENTS}/${id}`, { subject_id });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['assignments', 'uncategorized'] });
      queryClient.invalidateQueries({ queryKey: ['subjects'] });
      queryClient.invalidateQueries({ queryKey: ['assignmentFull'] });
    },
    onError: () => {
      toast({ title: t('common:error'), description: t('toasts.updateFailed'), status: 'error', duration: 3000 });
    },
  });

  const handleDragStart = (event: DragStartEvent) => {
    setActiveDragId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveDragId(null);

    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    if (!overId.startsWith('subject-drop:')) return;

    const targetSubjectId = overId.replace('subject-drop:', '');
    const newSubjectId = targetSubjectId === '__uncategorized__' ? null : targetSubjectId;

    const assignment = (data?.items || []).find(a => a.id === activeId);
    if (!assignment) {
      toast({ title: 'Assignment not found', status: 'error', duration: 2000 });
      return;
    }

    if (assignment.subject_id === newSubjectId) {
      // Already in that subject
      return;
    }

    moveAssignmentMutation.mutate({ id: activeId, subject_id: newSubjectId });
    const targetName = targetSubjectId === '__uncategorized__'
      ? t('uncategorized')
      : subjects?.find(s => s.id === targetSubjectId)?.name;
    toast({
      title: t('assignmentMoved'),
      description: `${assignment.name} → ${targetName}`,
      status: 'success',
      duration: 2500,
    });
  };

  const toggleSubject = (subjectId: string) => {
    setCollapsedSubjects(prev => {
      const next = new Set(prev);
      if (next.has(subjectId)) {
        next.delete(subjectId);
      } else {
        next.add(subjectId);
      }
      return next;
    });
  };

  const openCreateAssignment = () => {
    setEditingAssignment(null);
    setNewName('');
    setNewDescription('');
    setNewSubjectId(null);
    onAssignmentModalOpen();
  };

  const openEditAssignment = (a: Assignment) => {
    setEditingAssignment(a);
    setNewName(a.name);
    setNewDescription(a.description || '');
    setNewSubjectId(a.subject_id);
    onAssignmentModalOpen();
  };

  const closeAssignmentModal = () => {
    setEditingAssignment(null);
    setNewName('');
    setNewDescription('');
    setNewSubjectId(null);
    onAssignmentModalClose();
  };

  const openCreateSubject = () => {
    setEditingSubject(null);
    setNewName('');
    setNewDescription('');
    onSubjectModalOpen();
  };

  const openEditSubject = (s: Subject) => {
    setEditingSubject(s);
    setNewName(s.name);
    setNewDescription(s.description || '');
    onSubjectModalOpen();
  };

  const closeSubjectModal = () => {
    setEditingSubject(null);
    setNewName('');
    setNewDescription('');
    onSubjectModalClose();
  };

  const handleSaveAssignment = useCallback(() => {
    if (!newName.trim()) {
      toast({ title: t('validation.nameRequired'), status: 'warning', duration: 3000 });
      return;
    }
    const payload = {
      name: newName.trim(),
      description: newDescription.trim() || null,
      subject_id: newSubjectId,
    };
    if (editingAssignment) {
      updateMutation.mutate({ id: editingAssignment.id, payload });
    } else {
      createMutation.mutate(payload);
    }
  }, [newName, newDescription, newSubjectId, editingAssignment, createMutation, updateMutation, toast]);

  const handleSaveSubject = useCallback(() => {
    if (!newName.trim()) {
      toast({ title: t('validation.nameRequired'), status: 'warning', duration: 3000 });
      return;
    }
    const payload = {
      name: newName.trim(),
      description: newDescription.trim() || null,
    };
    if (editingSubject) {
      updateSubjectMutation.mutate({ id: editingSubject.id, payload });
    } else {
      createSubjectMutation.mutate(payload);
    }
    closeSubjectModal();
  }, [newName, newDescription, editingSubject, createSubjectMutation, updateSubjectMutation, toast]);

   const handleDeleteAssignment = useCallback(() => {
     if (deletingAssignment) {
       deleteMutation.mutate(deletingAssignment);
     }
   }, [deletingAssignment, deleteMutation]);

   const handleDeleteSubject = useCallback(() => {
     if (!deletingSubject) return;

     const subjectToUndo = deletingSubject;

      deleteSubjectMutation.mutate(subjectToUndo.id, {
        onSuccess: () => {
          toast({
            title: t('toasts.deleted'),
            description: (
              <Button
                size="sm"
                colorScheme="blue"
                mt={2}
                onClick={() => {
                  restoreSubjectMutation.mutate(subjectToUndo.id);
                }}
                width="100%"
              >
                {t('common:undo')}
              </Button>
            ),
            status: 'warning',
            duration: 8000,
            isClosable: true,
          });
        },
      });

     setDeletingSubject(null);
     onDeleteSubjectClose();
   }, [deletingSubject, deleteSubjectMutation, restoreSubjectMutation, t]);

  const filterAssignments = (assignments: Assignment[]) => {
    if (!searchQuery.trim()) return assignments;
    return assignments.filter(a =>
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (a.description && a.description.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  };

  const isLoading = assignmentsLoading || subjectsLoading || uncategorizedLoading;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={pointerWithin}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
      {/* Header */}
      <Flex justify="space-between" align="center" mb={4} flexShrink={0}>
        <Text fontSize="2xl" fontWeight="bold">
          {t('title')}
        </Text>
        <HStack spacing={2}>
          <Button leftIcon={<FiFolder />} colorScheme="purple" size="sm" onClick={openCreateSubject}>
            {t('newSubject')}
          </Button>
          <Button leftIcon={<FiPlus />} colorScheme="brand" size="sm" onClick={openCreateAssignment}>
            {t('newAssignment')}
          </Button>
        </HStack>
      </Flex>

      {/* Search */}
      <Box mb={4} flexShrink={0}>
        <InputGroup size="sm" maxW="300px">
          <InputLeftElement pointerEvents="none">
            <Icon as={FiSearch} color={mutedColor} />
          </InputLeftElement>
          <Input
            placeholder={t('search')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </InputGroup>
      </Box>

      {/* Content */}
      <Box flex={1} minH={0} overflow="auto">
        {isLoading ? (
          <Flex justify="center" align="center" p={8}>
            <Spinner />
          </Flex>
        ) : (
          <VStack spacing={4} align="stretch">
            {/* Subjects */}
            {subjects && subjects.length > 0 && subjects.map((subject) => {
              const subjectAssignments = filterAssignments(
                (data?.items || []).filter(a => a.subject_id === subject.id)
              );
              const isCollapsed = collapsedSubjects.has(subject.id);
              const dropTargetId = `subject-drop:${subject.id}`;

              return (
                <DroppableSubjectContainer key={subject.id} subjectId={subject.id}>
                  {({ isOver }) => (
                    <>
                      <SubjectHeader isOver={isOver} isUncategorized={false}>
                        <HStack spacing={3} flex={1} onClick={() => toggleSubject(subject.id)} cursor="pointer">
                          <Icon
                            as={isCollapsed ? FiChevronRight : FiChevronDown}
                            boxSize={4}
                            color={mutedColor}
                          />
                          <Icon as={FiFolder} boxSize={5} color="purple.500" />
                          <Text fontWeight="semibold" fontSize="md">{subject.name}</Text>
                          <Badge colorScheme="purple">{subjectAssignments.length}</Badge>
                        </HStack>
                        <HStack spacing={1} onClick={(e) => e.stopPropagation()}>
                          <IconButton
                            aria-label="Edit subject"
                            icon={<FiEdit2 />}
                            size="xs"
                            variant="ghost"
                            onClick={() => openEditSubject(subject)}
                          />
                          <IconButton
                            aria-label="Delete subject"
                            icon={<FiTrash2 />}
                            size="xs"
                            variant="ghost"
                            colorScheme="red"
                            onClick={() => {
                              setDeletingSubject(subject);
                              onDeleteSubjectOpen();
                            }}
                          />
                        </HStack>
                      </SubjectHeader>

                      <Collapse in={!isCollapsed} animateOpacity>
                        <Box
                          bg={cardBg}
                          borderRadius="md"
                          borderWidth="1px"
                          borderColor={borderColor}
                          mt={2}
                          overflow="hidden"
                        >
                          {subjectAssignments.length === 0 ? (
                            <Flex direction="column" align="center" justify="center" py={12} color={mutedColor}>
                              <Icon as={FiInbox} boxSize={10} mb={3} opacity={0.5} />
                              <Text fontWeight="medium">{t('noAssignmentsInSubject')}</Text>
                            </Flex>
                          ) : (
                            <TableContainer>
                              <Table variant="simple" size="sm">
                                <Thead>
                                  <Tr>
                                    <Th w="30px"></Th>
                                    <Th>{t('table.name')}</Th>
                                    <Th>{t('table.description')}</Th>
                                    <Th isNumeric>{t('table.tasks')}</Th>
                                    <Th isNumeric>{t('table.files')}</Th>
                                    <Th>{t('table.created')}</Th>
                                    <Th>{t('table.actions')}</Th>
                                  </Tr>
                                </Thead>
                                <Tbody>
                                  {subjectAssignments.map((a) => (
                                    <DraggableAssignmentRow
                                      key={a.id}
                                      assignment={a}
                                      hoverBg={hoverBg}
                                      mutedColor={mutedColor}
                                      t={t}
                                      isDragging={activeDragId === `assignment-move:${a.id}`}
                                      onEdit={openEditAssignment}
                                      onDelete={(a) => { setDeletingAssignment(a); onDeleteAssignmentOpen(); }}
                                    />
                                  ))}
                                </Tbody>
                              </Table>
                            </TableContainer>
                          )}
                        </Box>
                      </Collapse>
                    </>
                  )}
                </DroppableSubjectContainer>
              );
            })}

            {/* Uncategorized */}
            {(() => {
              const uncategorized = filterAssignments(uncategorizedAssignments || []);
              const isCollapsed = collapsedSubjects.has('__uncategorized__');

              if (uncategorized.length === 0 && (!subjects || subjects.length === 0)) {
                return (
                  <Flex
                    flex={1}
                    align="center"
                    justify="center"
                    direction="column"
                    p={8}
                    color={mutedColor}
                  >
                    <Icon as={FiFolder} boxSize={10} mb={3} />
                    <Text fontWeight="medium">{t('noAssignments')}</Text>
                    <Text fontSize="sm">{t('createAssignmentPrompt')}</Text>
                  </Flex>
                );
              }

              if (uncategorized.length === 0) return null;

               return (
                <DroppableSubjectContainer key="__uncategorized__" subjectId="__uncategorized__">
                    {({ isOver }) => (
                      <>
                        <SubjectHeader isOver={isOver} isUncategorized={true}>
                         <HStack spacing={3} flex={1} onClick={() => toggleSubject('__uncategorized__')} cursor="pointer">
                           <Icon
                             as={isCollapsed ? FiChevronRight : FiChevronDown}
                             boxSize={4}
                             color={mutedColor}
                           />
                           <Icon as={FiFolder} boxSize={5} color="gray.500" />
                           <Text fontWeight="semibold" fontSize="md">{t('uncategorized')}</Text>
                           <Badge colorScheme="gray">{uncategorized.length}</Badge>
                         </HStack>
                       </SubjectHeader>

                       <Collapse in={!isCollapsed} animateOpacity>
                         <Box
                           bg={cardBg}
                           borderRadius="md"
                           borderWidth="1px"
                           borderColor={borderColor}
                           mt={2}
                           overflow="hidden"
                         >
                           <TableContainer>
                             <Table variant="simple" size="sm">
                               <Thead>
                                 <Tr>
                                   <Th w="30px"></Th>
                                   <Th>{t('table.name')}</Th>
                                   <Th>{t('table.description')}</Th>
                                   <Th isNumeric>{t('table.tasks')}</Th>
                                   <Th isNumeric>{t('table.files')}</Th>
                                   <Th>{t('table.created')}</Th>
                                   <Th>{t('table.actions')}</Th>
                                 </Tr>
                               </Thead>
                               <Tbody>
                                 {uncategorized.map((a) => (
                                   <DraggableAssignmentRow
                                     key={a.id}
                                     assignment={a}
                                     hoverBg={hoverBg}
                                     mutedColor={mutedColor}
                                     t={t}
                                     isDragging={activeDragId === a.id}
                                     onEdit={openEditAssignment}
                                     onDelete={(a) => { setDeletingAssignment(a); onDeleteAssignmentOpen(); }}
                                   />
                                 ))}
                               </Tbody>
                             </Table>
                           </TableContainer>
                         </Box>
                       </Collapse>
                     </>
                   )}
                 </DroppableSubjectContainer>
               );
            })()}
          </VStack>
        )}
      </Box>

      {/* Assignment Create/Edit Modal */}
      <Modal isOpen={isAssignmentModalOpen} onClose={closeAssignmentModal} isCentered>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{editingAssignment ? t('modal.edit') : t('modal.new')}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>{t('form.name')}</FormLabel>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t('form.namePlaceholder')}
                  autoFocus
                />
              </FormControl>
              <FormControl>
                <FormLabel>{t('form.description')}</FormLabel>
                <Textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder={t('form.descriptionPlaceholder')}
                  rows={3}
                />
              </FormControl>
              <FormControl>
                <FormLabel>{t('form.subject')}</FormLabel>
                <Select
                  value={newSubjectId || ''}
                  onChange={(e) => setNewSubjectId(e.target.value || null)}
                  placeholder={t('form.selectSubject')}
                >
                  {subjects?.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </Select>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={closeAssignmentModal}>
              {t('common:cancel')}
            </Button>
            <Button
              colorScheme="brand"
              onClick={handleSaveAssignment}
              isLoading={createMutation.isPending || updateMutation.isPending}
            >
              {editingAssignment ? t('common:save') : t('common:create')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Assignment Delete Confirmation */}
      <AlertDialog
        isOpen={isDeleteAssignmentOpen}
        leastDestructiveRef={cancelRef as React.RefObject<HTMLButtonElement>}
        onClose={() => {
          setDeletingAssignment(null);
          onDeleteAssignmentClose();
        }}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('deleteConfirm.title')}
            </AlertDialogHeader>
            <AlertDialogBody>
              {t('deleteConfirm.message', { name: deletingAssignment?.name })}
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteAssignmentClose}>
                {t('common:cancel')}
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDeleteAssignment}
                ml={3}
                isLoading={deleteMutation.isPending}
              >
                {t('common:delete')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Subject Create/Edit Modal */}
      <Modal isOpen={isSubjectModalOpen} onClose={closeSubjectModal} isCentered>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{editingSubject ? t('modal.editSubject') : t('modal.newSubject')}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>{t('form.subjectName')}</FormLabel>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t('form.subjectNamePlaceholder')}
                  autoFocus
                />
              </FormControl>
              <FormControl>
                <FormLabel>{t('form.description')}</FormLabel>
                <Textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder={t('form.subjectDescriptionPlaceholder')}
                  rows={3}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={closeSubjectModal}>
              {t('common:cancel')}
            </Button>
            <Button
              colorScheme="purple"
              onClick={handleSaveSubject}
              isLoading={createSubjectMutation.isPending || updateSubjectMutation.isPending}
            >
              {editingSubject ? t('common:save') : t('common:create')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Subject Delete Confirmation */}
      <AlertDialog
        isOpen={isDeleteSubjectOpen}
        leastDestructiveRef={cancelRef as React.RefObject<HTMLButtonElement>}
        onClose={() => {
          setDeletingSubject(null);
          onDeleteSubjectClose();
        }}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('deleteSubjectConfirm.title')}
            </AlertDialogHeader>
            <AlertDialogBody>
              {t('deleteSubjectConfirm.message', { name: deletingSubject?.name })}
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteSubjectClose}>
                {t('common:cancel')}
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDeleteSubject}
                ml={3}
                isLoading={deleteSubjectMutation.isPending}
              >
                {t('common:delete')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <DragOverlay>
        {activeDragId ? (
          (() => {
            const id = activeDragId.replace('assignment-move:', '');
            const assignment = (data?.items || []).find(a => a.id === id);
            if (!assignment) return null;
            return (
              <Box
                bg={cardBg}
                borderRadius="md"
                shadow="lg"
                px={3}
                py={2}
                opacity={0.9}
                border="1px"
                borderColor={borderColor}
                pointerEvents="none"
              >
                <Flex align="center" gap={2}>
                  <Icon as={FiFolder} boxSize={4} color="purple.500" />
                  <Text fontSize="sm" fontWeight="medium">{assignment.name}</Text>
                </Flex>
              </Box>
            );
          })()
        ) : null}
        </DragOverlay>
      </Box>
    </DndContext>
  );
};

export default Assignments;
