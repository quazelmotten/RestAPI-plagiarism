import React from 'react';
import {
  Box,
  Card,
  CardBody,
  Text,
  VStack,
  HStack,
  Flex,
  Progress,
  Button,
  Icon,
  useColorModeValue,
  Spinner,
  useToast,
  Badge,
} from '@chakra-ui/react';
import { FiHardDrive, FiTrash2, FiRefreshCw } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getStorageUsage, cleanupOrphanedTasks } from '../../services/api';

const Storage: React.FC = () => {
  const { t } = useTranslation(['storage', 'common']);
  const toast = useToast();
  const queryClient = useQueryClient();
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  const { data: storageData, isLoading } = useQuery({
    queryKey: ['storage', 'usage'],
    queryFn: async () => {
      const res = await getStorageUsage();
      return res.data;
    },
  });

  const cleanupMutation = useMutation({
    mutationFn: async () => {
      const res = await cleanupOrphanedTasks();
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['storage', 'usage'] });
      queryClient.invalidateQueries({ queryKey: ['tasks', 'orphaned'] });
      toast({
        title: t('common:success'),
        description: t('cleanupSuccess', { tasks: data.tasks_deleted, files: data.files_deleted }),
        status: 'success',
        duration: 5000,
      });
    },
    onError: () => {
      toast({
        title: t('common:error'),
        description: t('cleanupFailed'),
        status: 'error',
        duration: 4000,
      });
    },
  });

  if (isLoading) {
    return (
      <Flex justify="center" py={16}>
        <Spinner size="lg" />
      </Flex>
    );
  }

  if (!storageData) {
    return null;
  }

  const {
    total_bytes: totalBytes,
    total_human: totalHuman,
    by_assignment: byAssignment,
    orphaned_bytes: orphanedBytes,
    orphaned_human: orphanedHuman,
    orphaned_percentage: orphanedPercentage,
    redis_bytes: redisBytes,
    redis_human: redisHuman,
    redis_percentage: redisPercentage,
  } = storageData;

  return (
    <Box display="flex" flexDirection="column" flex={1} minH={0} overflow="hidden">
      <Flex justify="space-between" align="center" mb={6} wrap="wrap" gap={2}>
        <Text fontSize="2xl" fontWeight="bold">
          {t('storageUsage')}
        </Text>
        <Button
          leftIcon={<FiTrash2 />}
          colorScheme="red"
          variant="outline"
          onClick={() => cleanupMutation.mutate()}
          isLoading={cleanupMutation.isPending}
          isDisabled={orphanedBytes === 0}
        >
          {t('cleanupOrphaned')}
        </Button>
      </Flex>

      <Card bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} mb={6}>
        <CardBody>
          <VStack align="stretch" spacing={4}>
            <HStack justify="space-between">
              <HStack>
                <Icon as={FiHardDrive} boxSize={5} color="brand.500" />
                <Text fontWeight="semibold">{t('totalStorage')}</Text>
              </HStack>
              <Text fontSize="xl" fontWeight="bold">{totalHuman}</Text>
            </HStack>
          </VStack>
        </CardBody>
      </Card>

      <Card bg={cardBg} borderRadius="lg" borderWidth="1px" borderColor={borderColor} mb={6}>
        <CardBody>
          <Text fontWeight="semibold" mb={4}>{t('byAssignment')}</Text>
          <VStack spacing={3} align="stretch">
            {byAssignment.map((item: any) => (
              <Box key={item.assignment_id}>
                <HStack justify="space-between" mb={1} wrap="wrap" spacing={1}>
                  <Text fontSize="sm" fontWeight="medium" noOfLines={1} flex={1}>
                    {item.assignment_name}
                  </Text>
                  <HStack spacing={2}>
                    <Text fontSize="sm" color="gray.500">{item.size_human}</Text>
                    <Badge variant="subtle" colorScheme="gray" fontSize="xs">
                      {item.percentage}%
                    </Badge>
                  </HStack>
                </HStack>
                <Progress
                  value={item.percentage}
                  size="sm"
                  colorScheme="brand"
                  borderRadius="full"
                />
              </Box>
            ))}

            {orphanedBytes > 0 && (
              <Box>
                <HStack justify="space-between" mb={1} wrap="wrap" spacing={1}>
                  <Text fontSize="sm" fontWeight="medium" color="red.500">
                    {t('orphanedTasks')}
                  </Text>
                  <HStack spacing={2}>
                    <Text fontSize="sm" color="red.500">{orphanedHuman}</Text>
                    <Badge variant="subtle" colorScheme="red" fontSize="xs">
                      {orphanedPercentage}%
                    </Badge>
                  </HStack>
                </HStack>
                <Progress
                  value={orphanedPercentage}
                  size="sm"
                  colorScheme="red"
                  borderRadius="full"
                />
              </Box>
            )}

            <Box>
              <HStack justify="space-between" mb={1}>
                <Text fontSize="sm" fontWeight="medium">{t('redisCache')}</Text>
                <HStack spacing={2}>
                  <Text fontSize="sm" color="gray.500">{redisHuman}</Text>
                  <Badge variant="subtle" colorScheme="gray" fontSize="xs">
                    {redisPercentage}%
                  </Badge>
                </HStack>
              </HStack>
              <Progress
                value={redisPercentage}
                size="sm"
                colorScheme="gray"
                borderRadius="full"
              />
            </Box>
          </VStack>
        </CardBody>
      </Card>

      <Button
        leftIcon={<FiRefreshCw />}
        variant="outline"
        onClick={() => queryClient.invalidateQueries({ queryKey: ['storage', 'usage'] })}
        alignSelf="flex-start"
      >
        {t('common:refresh')}
      </Button>
    </Box>
  );
};

export default Storage;
