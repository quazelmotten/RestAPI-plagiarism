import React, { useState } from 'react';
import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  Input,
  Textarea,
  Button,
  IconButton,
  useColorModeValue,
  useToast,
  Spinner,
  Icon,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
} from '@chakra-ui/react';
import { FiSave, FiTrash2, FiRefreshCw } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api, { API_ENDPOINTS } from '../../../services/api';

interface AssignmentSettingsTabProps {
  assignmentId: string;
  assignmentName: string;
  assignmentDescription: string | null;
  onRefetch: () => void;
}

const AssignmentSettingsTab: React.FC<AssignmentSettingsTabProps> = ({
  assignmentId,
  assignmentName,
  assignmentDescription,
  onRefetch,
}) => {
  const { t } = useTranslation(['assignments', 'common']);
  const toast = useToast();
  const queryClient = useQueryClient();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const [name, setName] = useState(assignmentName);
  const [description, setDescription] = useState(assignmentDescription || '');

  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const updateMutation = useMutation({
    mutationFn: async () => {
      const res = await api.patch(API_ENDPOINTS.ASSIGNMENT_DETAILS(assignmentId), {
        name,
        description: description || null,
      });
      return res.data;
    },
    onSuccess: () => {
      toast({ title: t('common:toasts.updated'), status: 'success', duration: 2000 });
      onRefetch();
    },
    onError: () => {
      toast({ title: t('common:errors.generic'), status: 'error', duration: 3000 });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const res = await api.delete(API_ENDPOINTS.ASSIGNMENT_DETAILS(assignmentId));
      return res.data;
    },
    onSuccess: () => {
      toast({ title: t('common:toasts.deleted'), status: 'success', duration: 2000 });
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      window.location.href = '/dashboard/assignments';
    },
    onError: () => {
      toast({ title: t('common:errors.generic'), status: 'error', duration: 3000 });
    },
  });

  const handleSave = () => {
    if (name.trim()) {
      updateMutation.mutate();
    }
  };

  const handleDelete = () => {
    deleteMutation.mutate();
    onClose();
  };

  return (
    <VStack align="stretch" spacing={4} maxW="600px">
      <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} p={4}>
        <VStack align="stretch" spacing={4}>
          <Text fontSize="lg" fontWeight="semibold">{t('assignments:settings.general')}</Text>

          <VStack align="stretch" spacing={2}>
            <Text fontSize="sm" fontWeight="medium">{t('assignments:assignmentName')}</Text>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('assignments:enterAssignmentName')}
            />
          </VStack>

          <VStack align="stretch" spacing={2}>
            <Text fontSize="sm" fontWeight="medium">{t('assignments:description')}</Text>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('assignments:enterDescription')}
              rows={3}
            />
          </VStack>

          <Button
            leftIcon={<FiSave />}
            colorScheme="brand"
            onClick={handleSave}
            isLoading={updateMutation.isPending}
            alignSelf="flex-start"
          >
            {t('common:buttons.save')}
          </Button>
        </VStack>
      </Box>

      <Box bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor="red.200" p={4}>
        <VStack align="stretch" spacing={4}>
          <Text fontSize="lg" fontWeight="semibold" color="red.500">{t('common:dangerZone')}</Text>

          <HStack justify="space-between">
            <Box>
              <Text fontSize="sm" fontWeight="medium">{t('assignments:deleteAssignment')}</Text>
              <Text fontSize="xs" color={mutedColor}>{t('assignments:deleteAssignmentDescription')}</Text>
            </Box>
            <Button
              leftIcon={<FiTrash2 />}
              colorScheme="red"
              variant="outline"
              size="sm"
              onClick={onOpen}
            >
              {t('common:buttons.delete')}
            </Button>
          </HStack>
        </VStack>
      </Box>

      <AlertDialog
        isOpen={isOpen}
        leastDestructiveRef={cancelRef}
        onClose={onClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              {t('assignments:deleteAssignment')}
            </AlertDialogHeader>
            <AlertDialogBody>
              {t('assignments:deleteAssignmentConfirm')}
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onClose}>
                {t('common:buttons.cancel')}
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDelete}
                isLoading={deleteMutation.isPending}
                ml={3}
              >
                {t('common:buttons.delete')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
};

export default AssignmentSettingsTab;
