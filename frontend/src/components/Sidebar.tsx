import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router';
import { keyframes } from '@emotion/react';
import {
  Box,
  VStack,
  Text,
  Icon,
  Flex,
  useColorModeValue,
  Divider,
  Spinner,
  Badge,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  FiHome,
  FiFileText,
  FiShare2,
  FiUpload,
  FiBarChart2,
  FiColumns,
  FiBookOpen,
  FiPlus,
  FiChevronDown,
  FiChevronRight,
} from 'react-icons/fi';
import api, { API_ENDPOINTS } from '../services/api';
import { useViewMode } from '../contexts/ViewModeContext';
import { SIDEBAR_WIDTH_PX } from '../constants/layout';

const blink = keyframes`
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
`;

interface Assignment {
  id: string;
  name: string;
  description: string | null;
  tasks_count: number;
  files_count: number;
}

interface AssignmentsResponse {
  items: Assignment[];
}

const classicMenuItems = [
  { path: '/dashboard', label: 'overview', icon: FiHome },
  { path: '/dashboard/assignments', label: 'assignments', icon: FiBookOpen },
  { path: '/dashboard/submissions', label: 'submissions', icon: FiFileText },
  { path: '/dashboard/graph', label: 'plagiarismGraph', icon: FiShare2 },
  { path: '/dashboard/upload', label: 'uploadFiles', icon: FiUpload },
  { path: '/dashboard/results', label: 'results', icon: FiBarChart2 },
  { path: '/dashboard/pair-comparison', label: 'pairComparison', icon: FiColumns },
];

const Sidebar: React.FC = () => {
  const { t } = useTranslation('navigation');
  const location = useLocation();
  const { mode } = useViewMode();
  const [assignmentsExpanded, setAssignmentsExpanded] = useState(true);
  const [isBlinking, setIsBlinking] = useState(false);

  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.700');
  const logoColor = useColorModeValue('black', 'white');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');
  const sectionColor = useColorModeValue('gray.400', 'gray.500');
  const scrollbarBg = useColorModeValue('gray.300', 'gray.600');

  const { data: assignmentsData, isLoading: assignmentsLoading } = useQuery<AssignmentsResponse>({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data;
    },
  });

  const assignments = assignmentsData?.items || [];

  const isActive = (path: string) => location.pathname === path || location.pathname === `${path}/`;

  return (
    <Box
      as="nav"
      pos="fixed"
      left="0"
      h="full"
      w={SIDEBAR_WIDTH_PX}
      bg={bgColor}
      borderRight="1px"
      borderColor={borderColor}
      py={6}
      px={4}
      display="flex"
      flexDirection="column"
      overflow="hidden"
    >
      <Box mb={6} px={4} cursor="pointer" onClick={() => setIsBlinking(!isBlinking)} title="Click to toggle blink">
        <Text
          fontSize="1.6rem"
          fontWeight="bold"
          fontFamily="monospace"
          letterSpacing="0.05em"
          userSelect="none"
          whiteSpace="nowrap"
        >
          <span style={{ color: logoColor }}>plagi</span>
          <span style={{ color: '#38A169' }}>type</span>
          <Box as="span" sx={isBlinking ? { animation: `${blink} 1s infinite` } : undefined}>_</Box>
        </Text>
      </Box>

      {mode === 'classic' ? (
        // Classic mode: original flat navigation
        <VStack spacing={2} align="stretch">
          {classicMenuItems.map((item) => (
            <NavLink key={item.path} to={item.path} style={{ textDecoration: 'none' }}>
              <Flex
                align="center"
                px={4}
                py={3}
                borderRadius="md"
                bg={isActive(item.path) ? 'brand.500' : 'transparent'}
                color={isActive(item.path) ? 'white' : 'inherit'}
                _hover={{
                  bg: isActive(item.path) ? 'brand.600' : hoverBg,
                }}
                transition="all 0.2s"
              >
                <Icon as={item.icon} boxSize={5} mr={3} />
                <Text fontWeight="medium">{t(item.label)}</Text>
              </Flex>
            </NavLink>
          ))}
        </VStack>
      ) : (
        // Assignment mode: assignment-first navigation
        <>
          <VStack spacing={1} align="stretch" flexShrink={0}>
            <NavLink to="/dashboard" style={{ textDecoration: 'none' }}>
              <Flex
                align="center"
                px={4}
                py={2.5}
                borderRadius="md"
                bg={isActive('/dashboard') ? 'brand.500' : 'transparent'}
                color={isActive('/dashboard') ? 'white' : 'inherit'}
                _hover={{ bg: isActive('/dashboard') ? 'brand.600' : hoverBg }}
                transition="all 0.2s"
              >
                <Icon as={FiHome} boxSize={4.5} mr={3} />
                <Text fontWeight="medium" fontSize="sm">{t('overview')}</Text>
              </Flex>
            </NavLink>
          </VStack>

          <Divider my={4} />

          {/* Assignments section header */}
          <Flex
            align="center"
            justify="space-between"
            px={4}
            mb={2}
            cursor="pointer"
            onClick={() => setAssignmentsExpanded(!assignmentsExpanded)}
            userSelect="none"
          >
            <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" letterSpacing="wider" color={sectionColor}>
              {t('assignments')}
            </Text>
            <Icon
              as={assignmentsExpanded ? FiChevronDown : FiChevronRight}
              boxSize={3.5}
              color={sectionColor}
            />
          </Flex>

          {/* Assignment links */}
          {assignmentsExpanded && (
            <VStack spacing={0} align="stretch" flex="1" minH={0} overflowY="auto" css={{
              '&::-webkit-scrollbar': { width: '4px' },
              '&::-webkit-scrollbar-thumb': { bg: scrollbarBg, borderRadius: '2px' },
            }}>
              {assignmentsLoading ? (
                <Flex justify="center" py={4}>
                  <Spinner size="sm" />
                </Flex>
              ) : assignments.length === 0 ? (
                <Text fontSize="xs" color={mutedColor} px={4} py={2}>
                  {t('noAssignments')}
                </Text>
              ) : (
                assignments.map((assignment) => {
                  const path = `/dashboard/assignments/${assignment.id}`;
                  const isCurrent = location.pathname.startsWith(path);

                  return (
                    <NavLink key={assignment.id} to={path} style={{ textDecoration: 'none' }}>
                      <Flex
                        align="center"
                        px={4}
                        py={2}
                        borderRadius="md"
                        bg={isCurrent ? 'brand.500' : 'transparent'}
                        color={isCurrent ? 'white' : 'inherit'}
                        _hover={{ bg: isCurrent ? 'brand.600' : hoverBg }}
                        transition="all 0.2s"
                        gap={2}
                      >
                        <Icon as={FiBookOpen} boxSize={4} flexShrink={0} />
                        <Box flex={1} minW={0}>
                          <Text fontSize="sm" fontWeight="medium" noOfLines={1}>
                            {assignment.name}
                          </Text>
                          {assignment.tasks_count > 0 && (
                            <Text fontSize="xs" opacity={isCurrent ? 0.8 : 0.6}>
                              {assignment.tasks_count} {t('tasks')} · {assignment.files_count} {t('filesLabel')}
                            </Text>
                          )}
                        </Box>
                        {assignment.files_count > 0 && (
                          <Badge
                            size="sm"
                            colorScheme={isCurrent ? 'whiteAlpha' : 'gray'}
                            variant={isCurrent ? 'solid' : 'subtle'}
                            flexShrink={0}
                          >
                            {assignment.files_count}
                          </Badge>
                        )}
                      </Flex>
                    </NavLink>
                  );
                })
              )}

              {/* New Assignment link */}
              <NavLink to="/dashboard/assignments" style={{ textDecoration: 'none' }}>
                <Flex
                  align="center"
                  px={4}
                  py={2}
                  borderRadius="md"
                  color={mutedColor}
                  _hover={{ bg: hoverBg, color: 'inherit' }}
                  transition="all 0.2s"
                  gap={2}
                  mt={1}
                >
                  <Icon as={FiPlus} boxSize={4} />
                  <Text fontSize="sm">{t('newAssignment')}</Text>
                </Flex>
              </NavLink>
            </VStack>
          )}
        </>
      )}
    </Box>
  );
};

export default Sidebar;
