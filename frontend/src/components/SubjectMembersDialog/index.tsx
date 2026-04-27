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
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();

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
      toast({ title: t('accessGranted'), status: 'success', duration: 2000 });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t('failedToGrantAccess');
      toast({ title: t('error'), description: message, status: 'error', duration: 3000 });
    }
  };

  const handleRevoke = async (userId: string) => {
    if (!subject) return;

    try {
      await revokeMutation.mutateAsync({ subjectId: subject.id, userId });
      toast({ title: t('accessRevoked'), status: 'success', duration: 2000 });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t('failedToRevokeAccess');
      toast({ title: t('error'), description: message, status: 'error', duration: 3000 });
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
             <Text>{t('manageSubjectMembers')}</Text>
           </HStack>
         </ModalHeader>
         <ModalCloseButton />
         <ModalBody>
           <VStack spacing={4} align="stretch">
             <Box>
               <Text fontWeight="semibold" mb={2}>
                 {t('subject')}: {subject.name}
               </Text>
             </Box>

             <Divider />

             {/* Grant Access Form */}
             <FormControl>
               <FormLabel fontSize="sm">{t('grantAccessToUser')}</FormLabel>
               <HStack>
<Input
                    placeholder={t('placeholders.userEmail')}
                    value={email}
                   onChange={(e) => setEmail(e.target.value)}
                   onKeyDown={(e) => e.key === 'Enter' && handleGrant()}
                 />
<IconButton
                    aria-label={t('aria.grantAccess')}
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
                 {t('currentMembers', { count: members?.length || 0 })}
               </Text>

               {membersLoading && (
                 <Spinner size="sm" />
               )}

               {membersError && (
                 <Alert status="error" fontSize="sm">
                   <AlertIcon />
                   {t('failedToLoadMembers')}
                 </Alert>
               )}

               {members && members.length === 0 && (
                 <Text fontSize="sm" color="gray.500">
                   {t('noOtherMembers')}
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
                           {t('added')}{' '}
                           {new Date(member.granted_at).toLocaleDateString()}
                         </Text>
                       </Box>
<IconButton
                          aria-label={t('aria.revokeAccess')}
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
           <Button onClick={onClose}>{t('close')}</Button>
         </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

export default SubjectMembersDialog;