import { useState } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  HStack,
  Text,
  Box,
  IconButton,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  Divider,
  Badge,
} from '@chakra-ui/react';
import { FiUserPlus, FiTrash2, FiUsers } from 'react-icons/fi';
import { useSubjectMembers, useGrantSubjectAccess, useRevokeSubjectAccess } from '../../hooks/useSubjects';
import type { Subject } from '../../types';

interface SubjectMembersDialogProps {
  isOpen: boolean;
  onClose: () => void;
  subject: Subject | null;
}

export function SubjectMembersDialog({ isOpen, onClose, subject }: SubjectMembersDialogProps) {
  const [email, setEmail] = useState('');
  const toast = useToast();

  const { data: members, isLoading: membersLoading, error: membersError } = useSubjectMembers(
    subject?.id || ''
  );

  const grantMutation = useGrantSubjectAccess();
  const revokeMutation = useRevokeSubjectAccess();

  const handleGrant = async () => {
    if (!email.trim() || !subject) return;

    try {
      await grantMutation.mutateAsync({ subjectId: subject.id, userEmail: email.trim() });
      setEmail('');
      toast({ title: 'Access granted', status: 'success', duration: 2000 });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to grant access';
      toast({ title: 'Error', description: message, status: 'error', duration: 3000 });
    }
  };

  const handleRevoke = async (userId: string) => {
    if (!subject) return;

    try {
      await revokeMutation.mutateAsync({ subjectId: subject.id, userId });
      toast({ title: 'Access revoked', status: 'success', duration: 2000 });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to revoke access';
      toast({ title: 'Error', description: message, status: 'error', duration: 3000 });
    }
  };

  if (!subject) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="md">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          <HStack>
            <FiUsers />
            <Text>Manage Subject Members</Text>
          </HStack>
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4} align="stretch">
            <Box>
              <Text fontWeight="semibold" mb={2}>
                Subject: {subject.name}
              </Text>
            </Box>

            <Divider />

            {/* Grant Access Form */}
            <FormControl>
              <FormLabel fontSize="sm">Grant Access to User</FormLabel>
              <HStack>
                <Input
                  placeholder="user@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleGrant()}
                />
                <IconButton
                  aria-label="Grant access"
                  icon={<FiUserPlus />}
                  onClick={handleGrant}
                  isLoading={grantMutation.isPending}
                  isDisabled={!email.trim()}
                />
              </HStack>
            </FormControl>

            <Divider />

            {/* Members List */}
            <Box>
              <Text fontWeight="semibold" mb={2}>
                Current Members ({members?.length || 0})
              </Text>

              {membersLoading && (
                <Spinner size="sm" />
              )}

              {membersError && (
                <Alert status="error" fontSize="sm">
                  <AlertIcon />
                  Failed to load members
                </Alert>
              )}

              {members && members.length === 0 && (
                <Text fontSize="sm" color="gray.500">
                  No other members. Grant access to add users.
                </Text>
              )}

              {members && members.length > 0 && (
                <VStack spacing={2} align="stretch">
                  {members.map((member) => (
                    <HStack
                      key={member.user_id}
                      justify="space-between"
                      p={2}
                      bg="gray.50"
                      borderRadius="md"
                    >
                      <Box>
                        <Text fontSize="sm" fontWeight="medium">
                          {member.email}
                        </Text>
                        <Text fontSize="xs" color="gray.500">
                          Added{' '}
                          {new Date(member.granted_at).toLocaleDateString()}
                        </Text>
                      </Box>
                      <IconButton
                        aria-label="Revoke access"
                        icon={<FiTrash2 />}
                        size="sm"
                        variant="ghost"
                        colorScheme="red"
                        onClick={() => handleRevoke(member.user_id)}
                        isLoading={revokeMutation.isPending}
                      />
                    </HStack>
                  ))}
                </VStack>
              )}
            </Box>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button onClick={onClose}>Close</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

export default SubjectMembersDialog;