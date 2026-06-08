import React, { useState } from 'react';
import {
  Box,
  Text,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  useColorModeValue,
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
  Badge,
} from '@chakra-ui/react';
import { DeleteIcon, EditIcon } from '@chakra-ui/icons';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../contexts/AuthContext';
import { listAllApiKeys, deleteApiKey, updateApiKey } from '../../services/api';
import Overview from '../Overview';
import Storage from '../Storage';
import Users from '../Users';

interface AllApiKey {
  id: string;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  user_email?: string;
}

const Stat: React.FC<{ label: string; value: string | number; color?: string }> = ({ label, value, color }) => {
  const colorScheme = color || 'brand';
  return (
    <Box p={4} bg={useColorModeValue('white', 'gray.700')} borderRadius="lg" borderWidth="1px" borderColor={useColorModeValue('gray.200', 'gray.600')}>
      <Text fontSize="3xl" fontWeight="bold" color={`${colorScheme}.500`}>{value}</Text>
      <Text fontSize="sm" color="gray.500">{label}</Text>
    </Box>
  );
};

const Admin: React.FC<{ initialTab?: number }> = ({ initialTab = 0 }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const toast = useToast();
  const { isOpen: isEditOpen, onOpen: onEditOpen, onClose: onEditClose } = useDisclosure();
  const [activeTab, setActiveTab] = useState(initialTab);
  const [editingKey, setEditingKey] = useState<AllApiKey | null>(null);
  const [editName, setEditName] = useState('');
  const [editExpiresInDays, setEditExpiresInDays] = useState<number | null>(null);

  const { data: allKeys = [], isLoading, error } = useQuery<AllApiKey[]>({
    queryKey: ['allApiKeys'],
    queryFn: listAllApiKeys,
    enabled: !!user && user.is_global_admin === true,
  });

  const deleteMutation = useMutation({
    mutationFn: (keyId: string) => deleteApiKey(keyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['allApiKeys'] });
      toast({ status: 'success', title: t('common:apiKeyRevoked') });
    },
    onError: () => {
      toast({ status: 'error', title: t('common:errorRevokingApiKey') });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ keyId, name, expires_in_days }: { keyId: string; name?: string; expires_in_days?: number }) =>
      updateApiKey(keyId, { name, expires_in_days }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['allApiKeys'] });
      onEditClose();
      setEditingKey(null);
      setEditName('');
      setEditExpiresInDays(null);
      toast({ status: 'success', title: t('common:apiKeyUpdated') });
    },
    onError: () => {
      toast({ status: 'error', title: t('common:errorUpdatingApiKey') });
    },
  });

  const handleDeleteClick = (keyId: string) => {
    if (window.confirm(t('common:revokeKeyConfirm'))) {
      deleteMutation.mutate(keyId);
    }
  };

  const handleEditClick = (key: AllApiKey) => {
    setEditingKey(key);
    setEditName(key.name || '');
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
    <Box>
      <Tabs index={activeTab} onChange={setActiveTab}>
        <TabList>
          <Tab>{t('common:stats')}</Tab>
          <Tab>{t('common:storage')}</Tab>
          <Tab>{t('common:adminUsers')}</Tab>
          <Tab>{t('common:allApiKeys')}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel px={0} pt={4}>
            <Overview />
          </TabPanel>
          <TabPanel px={0} pt={4}>
            <Storage />
          </TabPanel>
          <TabPanel px={0} pt={4}>
            <Users />
          </TabPanel>
          <TabPanel px={0} pt={4}>
            <VStack align="stretch" spacing={4}>
              <Text fontWeight="bold">{t('common:allApiKeys')}</Text>
              {isLoading && <Text>{t('common:loading')}</Text>}
              {error && <Alert status="error"><AlertIcon />{t('common:failedToLoadKeys')}</Alert>}
              {!isLoading && !error && allKeys.length === 0 && (
                <Text color="gray.500">{t('common:noApiKeys')}</Text>
              )}
              {allKeys.length > 0 && (
                <Table size="sm">
                  <Thead>
                    <Tr>
                      <Th>{t('common:user')}</Th>
                      <Th>{t('common:name')}</Th>
                      <Th>{t('common:created')}</Th>
                      <Th>{t('common:lastUsed')}</Th>
                      <Th>{t('common:expires')}</Th>
                      <Th>{t('common:actions')}</Th>
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
                              <Badge colorScheme="red">{t('common:expired')}</Badge>
                            ) : (
                              <Text>{formatDate(key.expires_at)}</Text>
                            )
                          ) : (
                            <Text color="gray.400">{t('common:never')}</Text>
                          )}
                        </Td>
                        <Td>
                          <HStack spacing={2}>
                            <IconButton
                              aria-label={t('common:editKey')}
                              icon={<EditIcon />}
                              size="xs"
                              colorScheme="blue"
                              variant="ghost"
                              onClick={() => handleEditClick(key)}
                            />
                            <IconButton
                              aria-label={t('common:revokeKeyAria')}
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

            <Modal isOpen={isEditOpen} onClose={onEditClose}>
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>{t('common:editApiKey')}</ModalHeader>
                <ModalBody>
                  <VStack spacing={4} align="stretch">
                    <Text fontSize="sm" fontWeight="medium">{t('common:name')}</Text>
                    <Input
                      placeholder={t('common:keyName')}
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                    />
                    <Text fontSize="sm" fontWeight="medium">{t('common:expirationLabel')}</Text>
                    <Input
                      placeholder={t('common:expirationDays')}
                      type="number"
                      min="0"
                      value={editExpiresInDays ?? ''}
                      onChange={(e) => setEditExpiresInDays(e.target.value ? parseInt(e.target.value) : null)}
                    />
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="ghost" onClick={onEditClose}>
                    {t('common:cancel')}
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
                    {t('common:update') || 'Update'}
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
};

export default Admin;
