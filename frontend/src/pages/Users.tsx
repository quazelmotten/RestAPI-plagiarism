import React, { useState } from 'react';
import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Button,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Input,
  FormControl,
  FormLabel,
  Switch,
  useDisclosure,
  useToast,
  Badge,
  Text,
  Spinner,
  HStack,
  Icon,
} from '@chakra-ui/react';
import { FiArrowLeft } from 'react-icons/fi';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { getUsers, deleteUser, updateUserGlobalRole, adminChangePassword } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface User {
  id: string;
  email: string;
  is_global_admin: boolean;
  created_at: string;
  last_login: string | null;
}

const Users: React.FC = () => {
  const { user: currentUser } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [newPassword, setNewPassword] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  });

  const deleteUserMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast({
        title: 'User deleted',
        status: 'success',
        duration: 3000,
      });
    },
    onError: () => {
      toast({
        title: 'Failed to delete user',
        status: 'error',
        duration: 3000,
      });
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, isGlobalAdmin }: { userId: string; isGlobalAdmin: boolean }) =>
      updateUserGlobalRole(userId, isGlobalAdmin),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast({
        title: 'User role updated',
        status: 'success',
        duration: 3000,
      });
    },
    onError: () => {
      toast({
        title: 'Failed to update user role',
        status: 'error',
        duration: 3000,
      });
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: ({ userId, password }: { userId: string; password: string }) =>
      adminChangePassword(userId, password),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast({
        title: 'Password changed successfully',
        status: 'success',
        duration: 3000,
      });
      setNewPassword('');
      onClose();
    },
    onError: () => {
      toast({
        title: 'Failed to change password',
        status: 'error',
        duration: 3000,
      });
    },
  });

  const handleDeleteUser = (userId: string) => {
    if (window.confirm('Are you sure you want to delete this user?')) {
      deleteUserMutation.mutate(userId);
    }
  };

  const handleRoleChange = (user: User, isGlobalAdmin: boolean) => {
    updateRoleMutation.mutate({ userId: user.id, isGlobalAdmin });
  };

  const handleChangePassword = () => {
    if (selectedUser && newPassword) {
      changePasswordMutation.mutate({ userId: selectedUser.id, password: newPassword });
    }
  };

  const openPasswordModal = (user: User) => {
    setSelectedUser(user);
    setNewPassword('');
    onOpen();
  };

  if (isLoading) {
    return (
      <Box p={8} textAlign="center">
        <Spinner size="xl" />
      </Box>
    );
  }

  const users = data?.users || [];

  return (
    <Box p={8}>
      <HStack mb={6} gap={4}>
        <Button
          variant="ghost"
          leftIcon={<Icon as={FiArrowLeft} />}
          onClick={() => navigate('/dashboard')}
        >
          Back
        </Button>
        <Text fontSize="2xl" fontWeight="bold">
          User Management
        </Text>
      </HStack>

      <Table variant="simple">
        <Thead>
          <Tr>
            <Th>Email</Th>
            <Th>Admin</Th>
            <Th>Created</Th>
            <Th>Last Login</Th>
            <Th>Actions</Th>
          </Tr>
        </Thead>
        <Tbody>
          {users.map((user: User) => (
            <Tr key={user.id}>
              <Td>
                <HStack>
                  <Text>{user.email}</Text>
                  {user.id === currentUser?.id && (
                    <Badge colorScheme="blue">You</Badge>
                  )}
                </HStack>
              </Td>
              <Td>
                <Switch
                  isChecked={user.is_global_admin}
                  onChange={(e) => handleRoleChange(user, e.target.checked)}
                  isDisabled={user.id === currentUser?.id}
                />
              </Td>
              <Td>{new Date(user.created_at).toLocaleDateString()}</Td>
              <Td>
                {user.last_login
                  ? new Date(user.last_login).toLocaleString()
                  : 'Never'}
              </Td>
              <Td>
                <HStack spacing={2}>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => openPasswordModal(user)}
                  >
                    Change Password
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    colorScheme="red"
                    onClick={() => handleDeleteUser(user.id)}
                    isDisabled={user.id === currentUser?.id}
                  >
                    Delete
                  </Button>
                </HStack>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>

      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Change Password</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>New password for {selectedUser?.email}</FormLabel>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
              />
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="brand"
              onClick={handleChangePassword}
              isLoading={changePasswordMutation.isPending}
            >
              Change Password
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default Users;
