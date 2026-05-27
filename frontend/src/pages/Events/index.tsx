import React, { useCallback, useMemo, useState } from 'react';
import {
  Box,
  Text,
  Card,
  CardBody,
  VStack,
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
import { useTranslation } from 'react-i18next';
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

const EVENT_TYPES = [
  { value: '', label: 'All types' },
  { value: 'upload_queued', label: 'Upload Queued' },
  { value: 'upload_completed', label: 'Upload Completed' },
  { value: 'upload_failed', label: 'Upload Failed' },
  { value: 'file_uploaded', label: 'File Uploaded' },
  { value: 'file_deleted', label: 'File Deleted' },
  { value: 'file_moved', label: 'File Moved' },
  { value: 'file_transferred', label: 'File Transferred' },
  { value: 'reanalysis_triggered', label: 'Reanalysis Triggered' },
];

const PAGE_SIZE = 50;

const Events: React.FC = () => {
  const { t } = useTranslation('navigation');
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
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const goNext = useCallback(() => {
    if (page < totalPages - 1) setPage(p => p + 1);
  }, [page, totalPages]);

  const goPrev = useCallback(() => {
    if (page > 0) setPage(p => p - 1);
  }, [page]);

  const handleFilterReset = useCallback(() => {
    setEventType('');
    setUserEmail('');
    setDateFrom('');
    setDateTo('');
    setPage(0);
  }, []);

  const hoverBg = useColorModeValue('gray.50', 'gray.700');

  return (
    <Box h="100%" display="flex" flexDirection="column">
      <Text fontSize="2xl" fontWeight="bold" mb={4}>
        {t('events', 'Events')}
      </Text>

      <Card mb={4}>
        <CardBody>
          <HStack spacing={4} wrap="wrap">
            <Select
              value={eventType}
              onChange={e => { setEventType(e.target.value); setPage(0); }}
              width="200px"
              placeholder=" "
            >
              {EVENT_TYPES.map(et => (
                <option key={et.value} value={et.value}>{et.label}</option>
              ))}
            </Select>
            <Input
              placeholder="Filter by user email"
              value={userEmail}
              onChange={e => setUserEmail(e.target.value)}
              width="250px"
            />
            <Input
              type="date"
              value={dateFrom}
              onChange={e => { setDateFrom(e.target.value); setPage(0); }}
              width="180px"
              placeholder="From date"
            />
            <Input
              type="date"
              value={dateTo}
              onChange={e => { setDateTo(e.target.value); setPage(0); }}
              width="180px"
              placeholder="To date"
            />
            <Button onClick={handleFilterReset} size="sm">Reset</Button>
          </HStack>
        </CardBody>
      </Card>

      {isLoading ? (
        <Flex justify="center" py={16}>
          <Spinner size="xl" />
        </Flex>
      ) : events.length === 0 ? (
        <Flex direction="column" align="center" justify="center" py={16} color="gray.500">
          <Icon as={FiClock} boxSize={10} mb={2} />
          <Text>No events found</Text>
        </Flex>
      ) : (
        <>
          <TableContainer flex="1" overflowY="auto">
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th width="40px"></Th>
                  <Th>Event</Th>
                  <Th>Assignment</Th>
                  <Th>User</Th>
                  <Th isNumeric>Files</Th>
                  <Th>Timestamp</Th>
                </Tr>
              </Thead>
              <Tbody>
                {events.map(event => {
                  const icon = EVENT_ICONS[event.event_type] || <FiClock />;
                  const color = EVENT_COLORS[event.event_type] || 'gray';
                  const meta = event.metadata ?? {};

                  return (
                    <Tr key={event.id} _hover={{ bg: hoverBg }}>
                      <Td>
                        <Icon as={() => icon} boxSize={5} color={`${color}.500`} />
                      </Td>
                      <Td>
                        <Badge colorScheme={color}>
                          {event.event_type}
                        </Badge>
                        {event.task_name && (
                          <Text fontSize="xs" color="gray.500" mt={1}>
                            {event.task_name}
                          </Text>
                        )}
                      </Td>
                      <Td>
                        <Text>{event.assignment_name || '-'}</Text>
                      </Td>
                      <Td>
                        <Text>{event.user_email || '-'}</Text>
                      </Td>
                      <Td isNumeric>
                        {event.files_count !== null && event.files_count !== undefined
                          ? String(event.files_count)
                          : '-'}
                      </Td>
                      <Td>
                        <Text fontSize="sm" color="gray.500" whiteSpace="nowrap">
                          {event.created_at
                            ? new Date(event.created_at).toLocaleString()
                            : '-'}
                        </Text>
                      </Td>
                    </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </TableContainer>

          <HStack justify="space-between" mt={4} pt={4} borderTop="1px" borderColor="gray.200">
            <Text fontSize="sm" color="gray.500">
              {total} total events — page {page + 1} of {totalPages}
            </Text>
            <HStack>
              <IconButton
                icon={<FiChevronLeft />}
                aria-label="Previous page"
                isDisabled={page === 0}
                onClick={goPrev}
                size="sm"
              />
              <IconButton
                icon={<FiChevronRight />}
                aria-label="Next page"
                isDisabled={page >= totalPages - 1}
                onClick={goNext}
                size="sm"
              />
            </HStack>
          </HStack>
        </>
      )}
    </Box>
  );
};

export default Events;
