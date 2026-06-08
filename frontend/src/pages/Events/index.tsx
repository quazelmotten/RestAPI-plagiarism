import React, { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Text,
  Card,
  CardBody,
  HStack,
  Badge,
  Spinner,
  Flex,
  Select,
  Input,
  Button,
  Icon,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  useColorModeValue,
  IconButton,
} from '@chakra-ui/react';
import { FiChevronLeft, FiChevronRight, FiClock, FiFileText, FiCheckCircle, FiTrash2, FiMove, FiUpload, FiRefreshCw, FiAlertCircle } from 'react-icons/fi';
import { useTaskEvents } from '../../hooks/useFileQueries';

const EVENT_ICONS: Record<string, React.ReactElement> = {
  upload_queued: <FiUpload />,
  upload_completed: <FiCheckCircle />,
  upload_failed: <FiAlertCircle />,
  file_uploaded: <FiFileText />,
  file_deleted: <FiTrash2 />,
  file_moved: <FiMove />,
  file_transferred: <FiMove />,
  reanalysis_triggered: <FiRefreshCw />,
};

const EVENT_COLORS: Record<string, string> = {
  upload_queued: 'blue',
  upload_completed: 'green',
  upload_failed: 'red',
  file_uploaded: 'purple',
  file_deleted: 'orange',
  file_moved: 'teal',
  file_transferred: 'teal',
  reanalysis_triggered: 'yellow',
};

const EVENT_TYPES = (t: (key: string) => string) => [
  { value: '', label: t('events:eventTypes.allTypes') },
  { value: 'upload_queued', label: t('events:eventTypes.upload_queued') },
  { value: 'upload_completed', label: t('events:eventTypes.upload_completed') },
  { value: 'upload_failed', label: t('events:eventTypes.upload_failed') },
  { value: 'file_uploaded', label: t('events:eventTypes.file_uploaded') },
  { value: 'file_deleted', label: t('events:eventTypes.file_deleted') },
  { value: 'file_moved', label: t('events:eventTypes.file_moved') },
  { value: 'file_transferred', label: t('events:eventTypes.file_transferred') },
  { value: 'reanalysis_triggered', label: t('events:eventTypes.reanalysis_triggered') },
];

const PAGE_SIZE = 50;

const Events: React.FC = () => {
  const { t } = useTranslation(['events', 'common']);
  const [page, setPage] = useState(0);
  const [eventType, setEventType] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const { data, isLoading } = useTaskEvents({
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    event_type: eventType || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const events = useMemo(() => data?.items ?? [], [data]);
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = Boolean(eventType || userEmail || dateFrom || dateTo);

  const goNext = useCallback(() => {
    if (page < totalPages - 1) setPage(p => p + 1);
  }, [page, totalPages]);

  const goPrev = useCallback(() => {
    if (page > 0) setPage(p => p - 1);
  }, [page]);

  const goToPage = useCallback(
    (p: number) => {
      setPage(Math.max(0, Math.min(p, totalPages - 1)));
    },
    [totalPages],
  );

  const handleFilterReset = useCallback(() => {
    setEventType('');
    setUserEmail('');
    setDateFrom('');
    setDateTo('');
    setPage(0);
  }, []);

  const hoverBg = useColorModeValue('gray.50', 'gray.700');
  const dividerColor = useColorModeValue('gray.100', 'gray.700');
  const headerBg = useColorModeValue('gray.50', 'gray.700');
  const containerBorderColor = useColorModeValue('gray.200', 'gray.600');

  return (
    <Box h="100%" display="flex" flexDirection="column">
      <Card variant="outline" mb={3}>
        <CardBody py={3}>
          <HStack spacing={3} wrap="wrap">
            <Select
              size="sm"
              w={{ base: 'full', md: '150px' }}
              value={eventType}
              onChange={e => { setEventType(e.target.value); setPage(0); }}
              placeholder={t('events:eventTypes.allTypes')}
            >
              {EVENT_TYPES(t).map(et => (
                <option key={et.value} value={et.value}>{et.label}</option>
              ))}
            </Select>
            <Input
              size="sm"
              w={{ base: 'full', md: '200px' }}
              placeholder={t('events:filterPlaceholder')}
              value={userEmail}
              onChange={e => setUserEmail(e.target.value)}
            />
            <Input
              size="sm"
              type="date"
              w={{ base: 'full', md: '150px' }}
              value={dateFrom}
              onChange={e => { setDateFrom(e.target.value); setPage(0); }}
              title={t('events:fromDate')}
            />
            <Input
              size="sm"
              type="date"
              w={{ base: 'full', md: '150px' }}
              value={dateTo}
              onChange={e => { setDateTo(e.target.value); setPage(0); }}
              title={t('events:toDate')}
            />
            {hasFilters && (
              <Button onClick={handleFilterReset} size="xs" variant="ghost">
                {t('events:clearFilters')}
              </Button>
            )}
          </HStack>
        </CardBody>
      </Card>

      {isLoading ? (
        <Flex justify="center" py={16}>
          <Spinner size="xl" />
        </Flex>
      ) : events.length === 0 ? (
          <Flex direction="column" align="center" justify="center" py={16} color="gray.500">
            <Icon as={FiClock} boxSize={10} mb={2} color="gray.300" />
            <Text>{t('events:noEventsFound')}</Text>
          </Flex>
      ) : (
        <>
          <TableContainer
            flex="1"
            overflowY="auto"
            borderWidth="1px"
            borderColor={containerBorderColor}
            borderRadius="md"
          >
            <Table size="sm" variant="simple">
              <Thead position="sticky" top={0} bg={headerBg} zIndex={1}>
                <Tr>
                  <Th width="32px" px={2} borderRightWidth="1px" borderColor={dividerColor}></Th>
                  <Th borderRightWidth="1px" borderColor={dividerColor}>{t('events:columns.event')}</Th>
                  <Th borderRightWidth="1px" borderColor={dividerColor}>{t('events:columns.upload')}</Th>
                  <Th borderRightWidth="1px" borderColor={dividerColor}>{t('events:columns.assignment')}</Th>
                  <Th borderRightWidth="1px" borderColor={dividerColor}>{t('events:columns.user')}</Th>
                  <Th isNumeric borderRightWidth="1px" borderColor={dividerColor}>{t('events:columns.files')}</Th>
                  <Th>{t('events:columns.timestamp')}</Th>
                </Tr>
              </Thead>
              <Tbody>
                {events.map(event => {
                  const icon = EVENT_ICONS[event.event_type] || <FiClock />;
                  const color = EVENT_COLORS[event.event_type] || 'gray';

                  return (
                    <Tr key={event.id} _hover={{ bg: hoverBg }}>
                      <Td width="32px" px={2} borderRightWidth="1px" borderColor={dividerColor}>
                        <Icon as={() => icon} boxSize={3.5} color={`${color}.500`} />
                      </Td>
                      <Td borderRightWidth="1px" borderColor={dividerColor}>
                        <HStack spacing={2} minW={0}>
                          <Badge colorScheme={color} fontSize="xs" flexShrink={0}>
                            {t('events:eventTypes.' + event.event_type, { defaultValue: event.event_type })}
                          </Badge>
                        </HStack>
                      </Td>
                      <Td borderRightWidth="1px" borderColor={dividerColor} maxW="200px">
                        <Text fontSize="sm" isTruncated title={event.task_name || ''}>
                          {event.task_name || '—'}
                        </Text>
                      </Td>
                      <Td borderRightWidth="1px" borderColor={dividerColor} maxW="200px">
                        <Text fontSize="sm" isTruncated title={event.assignment_name || ''}>
                          {event.assignment_name || '—'}
                        </Text>
                      </Td>
                      <Td borderRightWidth="1px" borderColor={dividerColor} maxW="200px">
                        <Text fontSize="sm" isTruncated title={event.user_email || ''}>
                          {event.user_email || '—'}
                        </Text>
                      </Td>
                      <Td isNumeric borderRightWidth="1px" borderColor={dividerColor}>
                        <Text fontSize="sm">
                          {event.files_count !== null && event.files_count !== undefined
                            ? event.files_count
                            : '—'}
                        </Text>
                      </Td>
                      <Td whiteSpace="nowrap">
                        <Text fontSize="sm" color="gray.500">
                          {event.created_at
                            ? new Date(event.created_at).toLocaleString()
                            : '—'}
                        </Text>
                      </Td>
                    </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </TableContainer>

          {total > 0 && (
            <HStack justify="space-between" mt={3} pt={3}>
              <Text fontSize="sm" color="gray.500">
                {t('events:showing', {
                  start: page * PAGE_SIZE + 1,
                  end: Math.min((page + 1) * PAGE_SIZE, total),
                  total: total.toLocaleString(),
                })}
              </Text>
              <HStack spacing={1}>
                <IconButton
                  icon={<FiChevronLeft />}
                  aria-label={t('common:aria.previousPage')}
                  isDisabled={page === 0}
                  onClick={goPrev}
                  size="xs"
                  variant="ghost"
                />
                <IconButton
                  icon={<FiChevronRight />}
                  aria-label={t('common:aria.nextPage')}
                  isDisabled={page >= totalPages - 1}
                  onClick={goNext}
                  size="xs"
                  variant="ghost"
                />
                <HStack spacing={1} ml={2}>
                  <Text fontSize="xs" color="gray.500">{t('events:goTo')}</Text>
                  <Select
                    size="xs"
                    w="70px"
                    value={page}
                    onChange={e => goToPage(Number(e.target.value))}
                  >
                    {Array.from({ length: totalPages }, (_, i) => (
                      <option key={i} value={i}>{i + 1}</option>
                    ))}
                  </Select>
                  <Text fontSize="xs" color="gray.500">{t('events:ofPages', { total: totalPages })}</Text>
                </HStack>
              </HStack>
            </HStack>
          )}
        </>
      )}
    </Box>
  );
};

export default Events;
