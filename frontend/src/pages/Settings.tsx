import React, { useState } from 'react';
import {
  Box,
  Heading,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Text,
  VStack,
  HStack,
  Button,
  Input,
  IconButton,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure,

  Alert,
  AlertIcon,
  useClipboard,
  Badge,
} from '@chakra-ui/react';
import { AddIcon, CopyIcon, DeleteIcon, EditIcon } from '@chakra-ui/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { listApiKeys, createApiKey, deleteApiKey, updateApiKey, listAllApiKeys } from '../services/api';
import { useTranslation } from 'react-i18next';

interface ApiKey {
  id: string;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

interface AllApiKey extends ApiKey {
  user_email?: string;
}

const Settings: React.FC = () => {
  const { t } = useTranslation('common');
  const { user, updateProfile, changePassword } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [newKeyName, setNewKeyName] = useState('');
  const [expiresInDays, setExpiresInDays] = useState<number | null>(null);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [updateUsernameLoading, setUpdateUsernameLoading] = useState(false);
  const [changePasswordLoading, setChangePasswordLoading] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const { onCopy, hasCopied } = useClipboard(generatedKey || '');
  const [activeTab, setActiveTab] = useState(0);
  const [editingKey, setEditingKey] = useState<AllApiKey | ApiKey | null>(null);
  const [editName, setEditName] = useState('');
  const [editExpiresInDays, setEditExpiresInDays] = useState<number | null>(null);
  const { isOpen: isEditOpen, onOpen: onEditOpen, onClose: onEditClose } = useDisclosure();
  const { isOpen: isCreateOpen, onOpen: onCreateOpen, onClose: onCreateClose } = useDisclosure();

  // Fetch user's API keys
  const { data: keys = [], isLoading, error } = useQuery<ApiKey[]>({
    queryKey: ['apiKeys'],
    queryFn: listApiKeys,
    enabled: !!user,
  });

  // Fetch all API keys (admin only)
  const { data: allKeys = [], isLoading: allKeysLoading, error: allKeysError } = useQuery<AllApiKey[]>({
    queryKey: ['allApiKeys'],
    queryFn: listAllApiKeys,
    enabled: !!user && user.is_global_admin === true && activeTab === 2,
  });

  // Create key mutation
  const createMutation = useMutation({
    mutationFn: ({ name, expires_in_days }: { name?: string; expires_in_days?: number }) => createApiKey({ name, expires_in_days }),
     onSuccess: (data) => {
       setGeneratedKey(data.raw_key);
       queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
       onCreateClose();
       onOpen();
     },
    onError: () => {
      toast({ status: 'error', title: 'Error creating API key' });
    },
  });

  // Delete key mutation
  const deleteMutation = useMutation({
    mutationFn: (keyId: string) => deleteApiKey(keyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
      queryClient.invalidateQueries({ queryKey: ['allApiKeys'] });
      toast({ status: 'success', title: 'API key revoked' });
    },
    onError: () => {
      toast({ status: 'error', title: 'Error revoking API key' });
    },
  });

  const handleDeleteClick = (keyId: string) => {
    if (window.confirm(t('revokeKeyConfirm') || 'Are you sure you want to revoke this API key?')) {
      deleteMutation.mutate(keyId);
    }
  };

  // Update key mutation
  const updateMutation = useMutation({
    mutationFn: ({ keyId, name, expires_in_days }: { keyId: string; name?: string; expires_in_days?: number }) =>
      updateApiKey(keyId, { name, expires_in_days }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
      queryClient.invalidateQueries({ queryKey: ['allApiKeys'] });
      onEditClose();
      setEditingKey(null);
      setEditName('');
      setEditExpiresInDays(null);
      toast({ status: 'success', title: 'API key updated' });
    },
    onError: () => {
      toast({ status: 'error', title: 'Error updating API key' });
    },
  });

  const handleCreateKey = () => {
    createMutation.mutate({
      name: newKeyName || undefined,
      expires_in_days: expiresInDays ?? undefined,
    });
    setNewKeyName('');
    setExpiresInDays(null);
  };

  const handleEditClick = (key: AllApiKey | ApiKey) => {
    setEditingKey(key);
    setEditName(key.name || '');
    // Calculate days until expiration if exists
    if (key.expires_at) {
      const diff = new Date(key.expires_at).getTime() - new Date().getTime();
      const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
      setEditExpiresInDays(days > 0 ? days : 0);
    } else {
      setEditExpiresInDays(null);
    }
    onEditOpen();
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString();
  };

  const isExpired = (expiresAt: string | null) => {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  };

  return (
    <Box p={8}>
      <Heading mb={6}>{t('settings') || 'Settings'}</Heading>
      <Tabs index={activeTab} onChange={(index) => setActiveTab(index)}>
        <TabList>
          <Tab>{t('apiKeys') || 'API Keys'}</Tab>
          <Tab>{t('account') || 'Account'}</Tab>
          {user?.is_global_admin && (
            <Tab>{t('allApiKeys') || 'All API Keys (Admin)'}</Tab>
          )}
        </TabList>
        <TabPanels>
          <TabPanel>
            <VStack align="stretch" spacing={4}>
             <HStack justify="space-between" spacing={4}>
                  <Text fontWeight="bold">{t('apiKeys') || 'API Keys'}</Text>
                  <Button leftIcon={<AddIcon />} size="sm" onClick={onCreateOpen}>
                    {t('createApiKey') || 'Create new key'}
                  </Button>
                </HStack>
              {isLoading && <Text>Loading...</Text>}
              {error && <Alert status="error"><AlertIcon />Failed to load keys</Alert>}
              {!isLoading && !error && keys.length === 0 && (
                <Text color="gray.500">{t('noKeysYet') || 'No API keys yet.'}</Text>
              )}
              {keys.length > 0 && (
                <Table size="sm">
                  <Thead>
                    <Tr>
                      <Th>Name</Th>
                      <Th>Created</Th>
                      <Th>Last Used</Th>
                      <Th>Expires</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {keys.map((key) => (
                      <Tr key={key.id}>
                        <Td>{key.name || '—'}</Td>
                        <Td>{formatDate(key.created_at)}</Td>
                        <Td>{formatDate(key.last_used_at)}</Td>
                        <Td>
                          {key.expires_at ? (
                            isExpired(key.expires_at) ? (
                              <Badge colorScheme="red">Expired</Badge>
                            ) : (
                              <Text>{formatDate(key.expires_at)}</Text>
                            )
                          ) : (
                            <Text color="gray.400">Never</Text>
                          )}
                        </Td>
                         <Td>
<HStack spacing={2}>
  <IconButton
    aria-label="Edit key"
    icon={<EditIcon />}
    size="xs"
    colorScheme="blue"
    variant="ghost"
    onClick={() => handleEditClick(key)}
  />
  <IconButton
    aria-label="Revoke key"
    icon={<DeleteIcon />}
    size="xs"
    colorScheme="red"
    variant="ghost"
    onClick={() => handleDeleteClick(key.id)}
    isLoading={deleteMutation.isPending}
  />
</HStack>
                         </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              )}
            </VStack>
          </TabPanel>
           <TabPanel>
             <VStack align="stretch" spacing={4}>
               <Text fontWeight="bold">{t('account') || 'Account'}</Text>
               {updateError && (
                 <Alert status="error"><AlertIcon />{updateError}</Alert>
               )}
               {updateMessage && (
                 <Alert status="success"><AlertIcon />{updateMessage}</Alert>
               )}
               <Box>
                 <Text fontSize="sm" fontWeight="medium" mb={2}>{t('currentUsername') || 'Current username'}</Text>
                 <Text>{user?.username || '—'}</Text>
               </Box>
               <Box>
                 <Text fontSize="sm" fontWeight="medium" mb={2}>{t('currentEmail') || 'Current email'}</Text>
                 <Text>{user?.email || '—'}</Text>
               </Box>
               <Box>
                 <Text fontSize="sm" fontWeight="medium" mb={2}>{t('newUsername') || 'New username'}</Text>
                 <HStack spacing={2}>
                   <Input
                     placeholder={t('newUsername') || 'New username'}
                     value={newUsername}
                     onChange={(e) => setNewUsername(e.target.value)}
                     size="sm"
                   />
                   <Button
                     size="sm"
                     colorScheme="blue"
                     isLoading={updateUsernameLoading}
                     onClick={async () => {
                       if (!newUsername.trim()) return;
                       setUpdateUsernameLoading(true);
                       setUpdateError(null);
                       setUpdateMessage(null);
                        try {
                          await updateProfile({ username: newUsername });
                          setUpdateMessage(t('usernameUpdated') || 'Username updated successfully');
                          setNewUsername('');
                        } catch (err: unknown) {
                          const message = err instanceof Error ? err.message : t('failedToUpdateUsername') || 'Failed to update username';
                          setUpdateError(message);
                        } finally {
                          setUpdateUsernameLoading(false);
                        }
                     }}
                   >
                     {t('update') || 'Update'}
                   </Button>
                 </HStack>
               </Box>
               <Box>
                 <Text fontSize="sm" fontWeight="medium" mb={2}>{t('changePassword') || 'Change password'}</Text>
                 <HStack spacing={2}>
                   <Input
                     placeholder={t('currentPassword') || 'Current password'}
                     type="password"
                     value={currentPassword}
                     onChange={(e) => setCurrentPassword(e.target.value)}
                     size="sm"
                   />
                   <Input
                     placeholder={t('newPassword') || 'New password'}
                     type="password"
                     value={newPassword}
                     onChange={(e) => setNewPassword(e.target.value)}
                     size="sm"
                   />
                   <Button
                     size="sm"
                     colorScheme="blue"
                     isLoading={changePasswordLoading}
                     onClick={async () => {
                       if (!currentPassword || !newPassword) return;
                       setChangePasswordLoading(true);
                       setUpdateError(null);
                       setUpdateMessage(null);
                        try {
                          await changePassword(currentPassword, newPassword);
                          setUpdateMessage(t('passwordChangedSuccessfully') || 'Password changed successfully');
                          setCurrentPassword('');
                          setNewPassword('');
                        } catch (err: unknown) {
                          const message = err instanceof Error ? err.message : t('failedToChangePassword') || 'Failed to change password';
                          setUpdateError(message);
                        } finally {
                          setChangePasswordLoading(false);
                        }
                     }}
                   >
                     {t('changePassword') || 'Change password'}
                   </Button>
                 </HStack>
               </Box>
             </VStack>
           </TabPanel>
          {user?.is_global_admin && (
            <TabPanel>
              <VStack align="stretch" spacing={4}>
                <Text fontWeight="bold">{t('allApiKeys') || 'All API Keys'}</Text>
                {allKeysLoading && <Text>Loading...</Text>}
                {allKeysError && <Alert status="error"><AlertIcon />Failed to load keys</Alert>}
                {!allKeysLoading && !allKeysError && allKeys.length === 0 && (
                  <Text color="gray.500">No API keys found.</Text>
                )}
                 {allKeys.length > 0 && (
                   <Table size="sm">
                     <Thead>
                       <Tr>
                         <Th>User</Th>
                         <Th>Name</Th>
                         <Th>Created</Th>
                         <Th>Last Used</Th>
                         <Th>Expires</Th>
                         <Th>Actions</Th>
                       </Tr>
                     </Thead>
                     <Tbody>
                       {allKeys.map((key) => (
                         <Tr key={key.id}>
                           <Td>{key.user_email || '—'}</Td>
                           <Td>{key.name || '—'}</Td>
                           <Td>{formatDate(key.created_at)}</Td>
                           <Td>{formatDate(key.last_used_at)}</Td>
                           <Td>
                             {key.expires_at ? (
                               isExpired(key.expires_at) ? (
                                 <Badge colorScheme="red">Expired</Badge>
                               ) : (
                                 <Text>{formatDate(key.expires_at)}</Text>
                               )
                             ) : (
                               <Text color="gray.400">Never</Text>
                             )}
                           </Td>
                            <Td>
<HStack spacing={2}>
  <IconButton
    aria-label="Edit key"
    icon={<EditIcon />}
    size="xs"
    colorScheme="blue"
    variant="ghost"
    onClick={() => handleEditClick(key)}
  />
  <IconButton
    aria-label="Revoke key"
    icon={<DeleteIcon />}
    size="xs"
    colorScheme="red"
    variant="ghost"
    onClick={() => handleDeleteClick(key.id)}
    isLoading={deleteMutation.isPending}
  />
</HStack>
                            </Td>
                         </Tr>
                       ))}
                     </Tbody>
                   </Table>
                 )}
              </VStack>
            </TabPanel>
          )}
        </TabPanels>
      </Tabs>

      {/* Modal for displaying newly created key */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('apiKeyCreated') || 'API Key Created'}</ModalHeader>
          <ModalBody>
            <Text mb={2}>{t('copyKeyNow') || 'Copy this key now. You won\'t be able to see it again!'}</Text>
            <HStack>
              <Input value={generatedKey || ''} isReadOnly />
              <IconButton aria-label="Copy" icon={<CopyIcon />} onClick={onCopy} colorScheme={hasCopied ? 'green' : 'gray'} />
            </HStack>
          </ModalBody>
          <ModalFooter>
            <Button onClick={onClose}>Close</Button>
          </ModalFooter>
        </ModalContent>
       </Modal>

      {/* Modal for creating API key */}
      <Modal isOpen={isCreateOpen} onClose={onCreateClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('createApiKey') || 'Create new API key'}</ModalHeader>
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Text fontSize="sm" fontWeight="medium">Name</Text>
              <Input
                placeholder={t('keyName') || 'Key name (optional)'}
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
              />
              <Text fontSize="sm" fontWeight="medium">Expiration (days from now, leave empty for no expiration)</Text>
              <Input
                placeholder={t('expirationDays') || 'Days until expiration (optional)'}
                type="number"
                min="0"
                value={expiresInDays ?? ''}
                onChange={(e) => setExpiresInDays(e.target.value ? parseInt(e.target.value) : null)}
              />
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={onCreateClose}>
              {t('cancel') || 'Cancel'}
            </Button>
            <Button
              colorScheme="blue"
              isLoading={createMutation.isPending}
              onClick={handleCreateKey}
            >
              {t('create') || 'Create'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Modal for editing API key */}
      <Modal isOpen={isEditOpen} onClose={onEditClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{t('editApiKey') || 'Edit API Key'}</ModalHeader>
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Text fontSize="sm" fontWeight="medium">Name</Text>
              <Input
                placeholder="Key name (optional)"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
              <Text fontSize="sm" fontWeight="medium">Expiration (days from now, leave empty for no expiration)</Text>
              <Input
                placeholder="Days until expiration (optional)"
                type="number"
                min="0"
                value={editExpiresInDays ?? ''}
                onChange={(e) => setEditExpiresInDays(e.target.value ? parseInt(e.target.value) : null)}
              />
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={onEditClose}>
              {t('cancel') || 'Cancel'}
            </Button>
            <Button
              colorScheme="blue"
              isLoading={updateMutation.isPending}
              onClick={() => {
                if (editingKey) {
                  updateMutation.mutate({
                    keyId: editingKey.id,
                    name: editName || undefined,
                    expires_in_days: editExpiresInDays ?? undefined,
                  });
                }
              }}
            >
              {t('update') || 'Update'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default Settings;
