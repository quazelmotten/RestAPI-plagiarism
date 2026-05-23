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
} from '@chakra-ui/react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getUsers, deleteUser, updateUserGlobalRole, adminChangePassword } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';

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
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const { t } = useTranslation();

  if (!currentUser?.is_global_admin) {
    return (
      <Box p={8} textAlign="center">
        <Text fontSize="lg" color="red.500">Access Denied</Text>
        <Text color="gray.500" mt={2}>You must be an admin to view this page.</Text>
      </Box>
    );
  }

  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  });

  const deleteUserMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast({
        title: t('userDeleted'),
        status: 'success',
        duration: 3000,
      });
    },
    onError: () => {
      toast({
        title: t('failedToDeleteUser'),
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
        title: t('userRoleUpdated'),
        status: 'success',
        duration: 3000,
      });
    },
    onError: () => {
      toast({
        title: t('failedToUpdateUserRole'),
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
        title: t('passwordChangedSuccessfully'),
        status: 'success',
        duration: 3000,
      });
      setNewPassword('');
      onClose();
    },
    onError: () => {
      toast({
        title: t('failedToChangePassword'),
        status: 'error',
        duration: 3000,
      });
    },
  });

  const handleDeleteUser = (userId: string) => {
    if (window.confirm(t('areYouSureDeleteUser'))) {
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
    <Box>
      <Text fontSize="2xl" fontWeight="bold" mb={4}>
        {t('userManagement')}
      </Text>

      <Table variant="simple">
        <Thead>
          <Tr>
            <Th>{t('email')}</Th>
            <Th>{t('admin')}</Th>
            <Th>{t('created')}</Th>
            <Th>{t('lastLogin')}</Th>
            <Th>{t('actions')}</Th>
          </Tr>
        </Thead>
        <Tbody>
          {users.map((user: User) => (
            <Tr key={user.id}>
              <Td>
                <HStack>
                  <Text>{user.email}</Text>
                  {user.id === currentUser?.id && (
                    <Badge colorScheme="blue">{t('you')}</Badge>
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
                  : t('never')}
              </Td>
              <Td>
                <HStack spacing={2}>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => openPasswordModal(user)}
                  >
                    {t('changePassword')}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    colorScheme="red"
                    onClick={() => handleDeleteUser(user.id)}
                    isDisabled={user.id === currentUser?.id}
                  >
                    {t('delete')}
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
          <ModalHeader>{t('changePassword')}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>{t('newPasswordFor', { email: selectedUser?.email })}</FormLabel>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder={t('placeholders.newPassword')}
              />
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              {t('cancel')}
            </Button>
            <Button
              colorScheme="brand"
              onClick={handleChangePassword}
              isLoading={changePasswordMutation.isPending}
            >
              {t('changePassword')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default Users;
