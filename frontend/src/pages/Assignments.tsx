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
      toast({ title: 'Assignment created', status: 'success', duration: 3000 });
      closeModal();
    },
    onError: (err: unknown) => {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Failed to create assignment';
      toast({ title: 'Error', description: msg, status: 'error', duration: 5000 });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: { name?: string; description?: string | null } }) => {
      const res = await api.patch(`${API_ENDPOINTS.ASSIGNMENTS}/${id}`, payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      toast({ title: 'Assignment updated', status: 'success', duration: 3000 });
      closeModal();
    },
    onError: () => {
      toast({ title: 'Error', description: 'Failed to update assignment', status: 'error', duration: 5000 });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`${API_ENDPOINTS.ASSIGNMENTS}/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      toast({ title: 'Assignment deleted', status: 'success', duration: 3000 });
      setDeletingAssignment(null);
      onDeleteClose();
    },
    onError: () => {
      toast({ title: 'Error', description: 'Failed to delete assignment', status: 'error', duration: 5000 });
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
      toast({ title: 'Name is required', status: 'warning', duration: 3000 });
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
          Assignments
        </Text>
        <Button leftIcon={<FiPlus />} colorScheme="brand" size="sm" onClick={openCreate}>
          New Assignment
        </Button>
      </Flex>

      {/* Search */}
      <Box mb={4} flexShrink={0}>
        <InputGroup size="sm" maxW="300px">
          <InputLeftElement pointerEvents="none">
            <Icon as={FiSearch} color={mutedColor} />
          </InputLeftElement>
          <Input
            placeholder="Search assignments..."
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
            <Text fontWeight="medium">No assignments yet</Text>
            <Text fontSize="sm">Create an assignment to scope your plagiarism checks</Text>
          </Flex>
        ) : (
          <TableContainer>
            <Table variant="simple" size="sm">
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>Description</Th>
                  <Th isNumeric>Tasks</Th>
                  <Th isNumeric>Files</Th>
                  <Th>Created</Th>
                  <Th>Actions</Th>
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
                          aria-label="Edit assignment"
                          icon={<FiEdit2 />}
                          size="xs"
                          variant="ghost"
                          onClick={() => openEdit(a)}
                        />
                        <IconButton
                          aria-label="Delete assignment"
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
          <ModalHeader>{editingAssignment ? 'Edit Assignment' : 'New Assignment'}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Name</FormLabel>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g., CS101 Homework 3"
                  autoFocus
                />
              </FormControl>
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Optional description"
                  rows={3}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={closeModal}>
              Cancel
            </Button>
            <Button
              colorScheme="brand"
              onClick={handleSave}
              isLoading={createMutation.isPending || updateMutation.isPending}
            >
              {editingAssignment ? 'Save' : 'Create'}
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
              Delete Assignment
            </AlertDialogHeader>
            <AlertDialogBody>
              Are you sure you want to delete &quot;{deletingAssignment?.name}&quot;? Tasks associated
              with this assignment will not be deleted.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDelete}
                ml={3}
                isLoading={deleteMutation.isPending}
              >
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default Assignments;
