import React, { useState, useCallback } from 'react';
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
  Divider,
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
} from '@chakra-ui/react';
import {
  FiPlus,
  FiSearch,
  FiEdit2,
  FiTrash2,
  FiFolder,
} from 'react-icons/fi';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import api, { API_ENDPOINTS } from '../services/api';

interface Assignment {
  id: string;
  name: string;
  description: string | null;
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

const Assignments: React.FC = () => {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { t } = useTranslation(['assignments', 'common']);

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const [searchQuery, setSearchQuery] = useState('');
  const [editingAssignment, setEditingAssignment] = useState<Assignment | null>(null);
  const [deletingAssignment, setDeletingAssignment] = useState<Assignment | null>(null);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');

  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const { isOpen: isModalOpen, onOpen: onModalOpen, onClose: onModalClose } = useDisclosure();
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();

  const { data, isLoading } = useQuery<AssignmentsResponse>({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: { name: string; description: string | null }) => {
      const res = await api.post(API_ENDPOINTS.ASSIGNMENTS, payload);
      return res.data;
    },
     onSuccess: () => {
       queryClient.invalidateQueries({ queryKey: ['assignments'] });
       toast({ title: t('toasts.created'), status: 'success', duration: 3000 });
       closeModal();
     },
     onError: (err: unknown) => {
       const msg = err && typeof err === 'object' && 'response' in err
         ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
         : t('common:error');
       toast({ title: t('common:error'), description: msg, status: 'error', duration: 5000 });
     },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: { name?: string; description?: string | null } }) => {
      const res = await api.patch(`${API_ENDPOINTS.ASSIGNMENTS}/${id}`, payload);
      return res.data;
    },
     onSuccess: () => {
       queryClient.invalidateQueries({ queryKey: ['assignments'] });
       toast({ title: t('toasts.updated'), status: 'success', duration: 3000 });
       closeModal();
     },
     onError: () => {
       toast({ title: t('common:error'), description: t('toasts.updateFailed'), status: 'error', duration: 5000 });
     },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`${API_ENDPOINTS.ASSIGNMENTS}/${id}`);
    },
     onSuccess: () => {
       queryClient.invalidateQueries({ queryKey: ['assignments'] });
       toast({ title: t('toasts.deleted'), status: 'success', duration: 3000 });
       setDeletingAssignment(null);
       onDeleteClose();
     },
     onError: () => {
       toast({ title: t('common:error'), description: t('toasts.deleteFailed'), status: 'error', duration: 5000 });
     },
  });

  const openCreate = () => {
    setEditingAssignment(null);
    setNewName('');
    setNewDescription('');
    onModalOpen();
  };

  const openEdit = (a: Assignment) => {
    setEditingAssignment(a);
    setNewName(a.name);
    setNewDescription(a.description || '');
    onModalOpen();
  };

  const closeModal = () => {
    setEditingAssignment(null);
    setNewName('');
    setNewDescription('');
    onModalClose();
  };

  const handleSave = useCallback(() => {
    if (!newName.trim()) {
      toast({ title: t('validation.nameRequired'), status: 'warning', duration: 3000 });
      return;
    }
    const payload = {
      name: newName.trim(),
      description: newDescription.trim() || null,
    };
    if (editingAssignment) {
      updateMutation.mutate({ id: editingAssignment.id, payload });
    } else {
      createMutation.mutate(payload);
    }
  }, [newName, newDescription, editingAssignment, createMutation, updateMutation, toast]);

  const handleDelete = useCallback(() => {
    if (deletingAssignment) {
      deleteMutation.mutate(deletingAssignment.id);
    }
  }, [deletingAssignment, deleteMutation]);

  const filteredAssignments = (data?.items || []).filter((a) =>
    a.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
      {/* Header */}
      <Flex justify="space-between" align="center" mb={4} flexShrink={0}>
        <Text fontSize="2xl" fontWeight="bold">
          {t('title')}
        </Text>
        <Button leftIcon={<FiPlus />} colorScheme="brand" size="sm" onClick={openCreate}>
          {t('newAssignment')}
        </Button>
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

      {/* Table */}
      <Box
        bg={cardBg}
        borderRadius="lg"
        borderWidth="1px"
        borderColor={borderColor}
        flex={1}
        minH={0}
        overflow="auto"
      >
        {isLoading ? (
          <Flex justify="center" align="center" p={8}>
            <Spinner />
          </Flex>
        ) : filteredAssignments.length === 0 ? (
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
        ) : (
          <TableContainer>
            <Table variant="simple" size="sm">
               <Thead>
                 <Tr>
                   <Th>{t('table.name')}</Th>
                   <Th>{t('table.description')}</Th>
                   <Th isNumeric>{t('table.tasks')}</Th>
                   <Th isNumeric>{t('table.files')}</Th>
                   <Th>{t('table.created')}</Th>
                   <Th>{t('table.actions')}</Th>
                 </Tr>
               </Thead>
              <Tbody>
                {filteredAssignments.map((a) => (
                  <Tr key={a.id} _hover={{ bg: hoverBg }}>
                    <Td fontWeight="medium">{a.name}</Td>
                    <Td maxW="300px" isTruncated>{a.description || '—'}</Td>
                    <Td isNumeric>
                      <Badge colorScheme="blue">{a.tasks_count}</Badge>
                    </Td>
                    <Td isNumeric>
                      <Badge colorScheme="green">{a.files_count}</Badge>
                    </Td>
                    <Td fontSize="sm" color={mutedColor}>
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                    </Td>
                    <Td>
                      <HStack spacing={1}>
                        <IconButton
                          aria-label={`${t('common:edit')} assignment`}
                          icon={<FiEdit2 />}
                          size="xs"
                          variant="ghost"
                          onClick={() => openEdit(a)}
                        />
                        <IconButton
                          aria-label={`${t('common:delete')} assignment`}
                          icon={<FiTrash2 />}
                          size="xs"
                          variant="ghost"
                          colorScheme="red"
                          onClick={() => {
                            setDeletingAssignment(a);
                            onDeleteOpen();
                          }}
                        />
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </TableContainer>
        )}
      </Box>

      {/* Create/Edit Modal */}
      <Modal isOpen={isModalOpen} onClose={closeModal} isCentered>
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
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={closeModal}>
              {t('common:cancel')}
            </Button>
            <Button
              colorScheme="brand"
              onClick={handleSave}
              isLoading={createMutation.isPending || updateMutation.isPending}
            >
              {editingAssignment ? t('common:save') : t('common:create')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Delete Confirmation */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef as React.RefObject<HTMLButtonElement>}
        onClose={() => {
          setDeletingAssignment(null);
          onDeleteClose();
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
               <Button ref={cancelRef} onClick={onDeleteClose}>
                 {t('common:cancel')}
               </Button>
               <Button
                 colorScheme="red"
                 onClick={handleDelete}
                 ml={3}
                 isLoading={deleteMutation.isPending}
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

export default Assignments;
