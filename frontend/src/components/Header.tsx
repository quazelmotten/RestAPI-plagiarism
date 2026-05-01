import React, { useMemo } from 'react';
import {
  Box,
  Flex,
  Text,
  Button,
  IconButton,
  useColorModeValue,
  useColorMode,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Badge,
  HStack,
  VStack,
  Spinner,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router';
import { FiMoon, FiSun, FiClock, FiChevronDown, FiMenu } from 'react-icons/fi';
import { FiCheckCircle, FiAlertCircle, FiActivity, FiLayers } from 'react-icons/fi';
import { useViewMode } from '../contexts/ViewModeContext';
import { useAssignmentInfo } from '../contexts/AssignmentContext';
import { useAuth } from '../contexts/AuthContext';
import { useSidebar } from '../contexts/SidebarContext';
import { SIDEBAR_WIDTH_PX } from '../constants/layout';
import { useRecentTasksList } from '../hooks/useTaskQueries';
import { getStatusColorScheme } from '../utils/statusColors';


const ROUTE_TITLES: Record<string, string> = {
  '/dashboard': 'overview',
  '/dashboard/': 'overview',
  '/dashboard/assignments': 'assignments',
  '/dashboard/submissions': 'submissions',
  '/dashboard/graph': 'plagiarismGraph',
  '/dashboard/upload': 'uploadFiles',
  '/dashboard/results': 'results',
  '/dashboard/pair-comparison': 'pairComparison',
};

const BREADCRUMB_MAP: Record<string, { labelKey: string; to?: string }[]> = {
  '/dashboard': [{ labelKey: 'overview', to: '/dashboard' }],
  '/dashboard/assignments': [{ labelKey: 'assignments', to: '/dashboard/assignments' }],
  '/dashboard/submissions': [{ labelKey: 'submissions', to: '/dashboard/submissions' }],
  '/dashboard/graph': [{ labelKey: 'plagiarismGraph', to: '/dashboard/graph' }],
  '/dashboard/upload': [{ labelKey: 'uploadFiles', to: '/dashboard/upload' }],
  '/dashboard/results': [{ labelKey: 'results', to: '/dashboard/results' }],
  '/dashboard/pair-comparison': [{ labelKey: 'pairComparison', to: '/dashboard/pair-comparison' }],
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed': return <FiCheckCircle color="#48bb78" />;
    case 'failed': return <FiAlertCircle color="#f56565" />;
    case 'storing_results': return <FiActivity color="#ed8936" />;
    case 'indexing': return <FiLayers color="#4299e1" />;
    case 'finding_intra_pairs':
    case 'finding_cross_pairs': return <FiLayers color="#805ad5" />;
    default: return <FiClock color="#a0aec0" />;
  }
};

const Header: React.FC = () => {
  const { logout } = useAuth();
  const { colorMode, toggleColorMode } = useColorMode();
  const { t } = useTranslation(['navigation', 'common']);
  const { mode, setMode } = useViewMode();
  const { assignmentInfo } = useAssignmentInfo();
  const { openMobile } = useSidebar();
  const navigate = useNavigate();
  const location = useLocation();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  const recentTasksQuery = useRecentTasksList({ enabled: false });
  const recentTasks = useMemo(() => {
    const items = recentTasksQuery.data?.items ?? [];
    return items.slice(0, 5);
  }, [recentTasksQuery.data]);

  const pageTitle = useMemo(() => {
    const path = location.pathname;
    for (const [route, titleKey] of Object.entries(ROUTE_TITLES)) {
      if (path === route || path.startsWith(`${route}/`)) {
        return t(titleKey);
      }
    }
    return t('overview');
  }, [location.pathname, t]);

  const breadcrumbs = useMemo(() => {
    const path = location.pathname;
    const bc = BREADCRUMB_MAP[path];
    if (!bc) return [{ label: pageTitle }];

    // Convert labelKey to translated labels
    const translatedBc = bc.map(item => ({
      ...item,
      label: item.labelKey ? t(item.labelKey) : ''
    }));

    if (path.startsWith('/dashboard/assignments/') && path !== '/dashboard/assignments') {
      const parts = path.split('/');
      const assignmentId = parts[parts.length - 1];
      return [
        { label: t('assignments'), to: '/dashboard/assignments' },
        { label: assignmentId ? `${assignmentId.substring(0, 12)}...` : t('detail') },
      ];
    }
    return translatedBc;
  }, [location.pathname, pageTitle, t]);

  const handleModeSwitch = (newMode: 'assignments' | 'classic') => {
    setMode(newMode);
    if (newMode === 'assignments') {
      navigate('/dashboard/assignments');
    } else {
      navigate('/dashboard');
    }
  };

  return (
    <Box
      as="header"
      pos="fixed"
      top="0"
      left={{ base: 0, lg: SIDEBAR_WIDTH_PX }}
      right="0"
      h="16"
      bg={bgColor}
      borderBottom="1px"
      borderColor={borderColor}
      px={{ base: 4, md: 8 }}
      zIndex="sticky"
    >
      <Flex h="full" align="center" justify="space-between">
        <Flex align="center" gap={3} minW={0} flex={1}>
          {/* Mobile hamburger button */}
          <IconButton
            aria-label={t('common:aria.openSidebar')}
            icon={<FiMenu />}
            variant="ghost"
            size="md"
            display={{ base: 'flex', lg: 'none' }}
            onClick={openMobile}
          />
          {assignmentInfo && (
            <HStack spacing={2} flexShrink={0}>
              <Text fontSize="md" fontWeight="bold" isTruncated maxW="200px">{assignmentInfo.name}</Text>
              <Badge colorScheme="blue" fontSize="xs">{assignmentInfo.filesCount} {t('common:files')}</Badge>
              <Badge colorScheme="purple" fontSize="xs">{assignmentInfo.tasksCount} {t('common:tasks')}</Badge>
            </HStack>
          )}
          <BreadcrumbNav items={breadcrumbs} />
        </Flex>

        <Flex align="center" gap={{ base: 2, md: 4 }} flexShrink={0}>

           <Menu
              onOpen={() => {
                if (!recentTasksQuery.data || recentTasksQuery.isStale) {
                  recentTasksQuery.refetch();
                }
              }}
            >
                <MenuButton
                  as={Button}
                  size="xs"
                  variant="ghost"
                  rightIcon={<FiChevronDown />}
                  leftIcon={<FiClock />}
                  display={{ base: 'none', md: 'flex' }}
                >
                  {t('recent')}
                </MenuButton>
                <MenuList maxH="400px" overflowY="auto" minW="340px" maxW="400px">
                  {recentTasksQuery.isFetching && (
                    <Flex justify="center" align="center" p={4}>
                      <Spinner size="sm" />
                      <Text ml={2} fontSize="sm" color="gray.500">{t('common:loading')}</Text>
                    </Flex>
                  )}
                  {recentTasksQuery.isError && (
                    <Box p={4} color="red.500" fontSize="sm">
                      {t('common:errorLoading')}
                    </Box>
                  )}
                  {!recentTasksQuery.isFetching && !recentTasksQuery.isError && recentTasks.length === 0 && (
                    <Box p={4} fontSize="sm" color="gray.500">
                      {t('recentNoTasks')}
                    </Box>
                  )}
                  {!recentTasksQuery.isFetching && !recentTasksQuery.isError && recentTasks.map(task => (
                    <MenuItem
                      key={task.task_id}
                      onClick={() => navigate(`/dashboard/results?task=${task.task_id}`)}
                      _hover={{ bg: 'gray.50' }}
                    >
                      <VStack align="start" spacing={1} w="100%" maxW="100%" overflow="hidden">
                        <HStack justify="space-between" w="100%">
                          <HStack spacing={2} minW={0}>
                            {getStatusIcon(task.status)}
                            <Text fontSize="sm" isTruncated fontFamily="monospace">
                              {task.task_id.substring(0, 12)}...
                            </Text>
                          </HStack>
                          <Badge size="sm" colorScheme={getStatusColorScheme(task.status)} flexShrink={0}>
                             {t(`status:${task.status}`)}
                           </Badge>
                        </HStack>
                        {(task.subject_name || task.assignment_name) && (
                          <HStack spacing={2} w="100%" overflow="hidden">
                            {task.subject_name && (
                              <Text fontSize="2xs" color="purple.600" bg="purple.50" px={1} borderRadius="sm" isTruncated maxW="100%">
                                {task.subject_name}
                              </Text>
                            )}
                            {task.assignment_name && (
                              <Text fontSize="2xs" color="blue.600" bg="blue.50" px={1} borderRadius="sm" isTruncated maxW="100%">
                                {task.assignment_name}
                              </Text>
                            )}
                          </HStack>
                        )}
                        <HStack justify="space-between" w="100%">
                           <Text fontSize="2xs" color="gray.500">
                             {t('common:files')}: {task.files_count ?? 0}
                           </Text>
                           {task.progress && task.total_pairs > 0 && (
                             <Text fontSize="2xs" color="gray.500">
                               {t('common:pairs')}: {task.progress.display}
                             </Text>
                           )}
                         </HStack>
                      </VStack>
                    </MenuItem>
                  ))}
                </MenuList>
             </Menu>

          <Flex
            bg={useColorModeValue('gray.100', 'gray.700')}
            borderRadius="md"
            p="2px"
            flexShrink={0}
            display={{ base: 'none', lg: 'flex' }}
          >
            <Button
              size="xs"
              variant={mode === 'assignments' ? 'solid' : 'ghost'}
              colorScheme={mode === 'assignments' ? 'brand' : 'gray'}
              onClick={() => handleModeSwitch('assignments')}
              borderRadius="sm"
              px={3}
            >
              {t('modeAssignments')}
            </Button>
            <Button
              size="xs"
              variant={mode === 'classic' ? 'solid' : 'ghost'}
              colorScheme={mode === 'classic' ? 'brand' : 'gray'}
              onClick={() => handleModeSwitch('classic')}
              borderRadius="sm"
              px={3}
            >
              {t('modeClassic')}
            </Button>
          </Flex>

          <IconButton
            aria-label={t('common:aria.toggleDarkMode')}
            icon={colorMode === 'light' ? <FiMoon /> : <FiSun />}
            onClick={() => {
              toggleColorMode();
              try {
                localStorage.setItem('chakra-ui-color-mode', colorMode === 'light' ? 'dark' : 'light');
              } catch { /* ignore */ }
            }}
            variant="ghost"
            size="md"
          />
          {/* Logout button */}
           <Button
             size="xs"
             variant="ghost"
             onClick={async () => {
               await logout();
             }}
           >
             {t('common:logout')}
           </Button>
        </Flex>
      </Flex>
    </Box>
  );
};

const BreadcrumbNav: React.FC<{ items: { label: string; to?: string }[] }> = ({ items }) => {
  const mutedColor = useColorModeValue('gray.400', 'gray.500');
  if (items.length <= 1) return null;

  return (
    <HStack spacing={1} fontSize="sm" color={mutedColor} display={{ base: 'none', md: 'flex' }}>
      {items.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && <Text>/</Text>}
          {item.to ? (
            <Link
              to={item.to}
              style={{ textDecoration: 'none' }}
              onClick={() => window.location.hash = ''}
            >
              <Button
                as="span"
                variant="link"
                size="xs"
                color={mutedColor}
              >
                {item.label}
              </Button>
            </Link>
          ) : (
            <Text fontSize="xs" fontWeight="medium" isTruncated maxW="150px">
              {item.label}
            </Text>
          )}
        </React.Fragment>
      ))}
    </HStack>
  );
};

export default Header;
