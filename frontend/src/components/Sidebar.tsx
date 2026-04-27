import React, { useState, useCallback } from 'react';
import { NavLink, useLocation } from 'react-router';
import { keyframes } from '@emotion/react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Icon,
  Flex,
  useColorModeValue,
  Divider,
  Spinner,
  Badge,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Button,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  useDisclosure,
} from '@chakra-ui/react';
import { FiMenu } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  DndContext,
  closestCenter,
  DragOverlay,
} from '@dnd-kit/core';
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
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
  FiFolder,
  FiList,
  FiGlobe,
  FiUsers,
} from 'react-icons/fi';
import { useAuth } from '../contexts/AuthContext';
import { MdDragIndicator } from 'react-icons/md';
import api, { API_ENDPOINTS } from '../services/api';
import { useViewMode } from '../contexts/ViewModeContext';
import { SIDEBAR_WIDTH_PX } from '../constants/layout';
import { useSidebar } from '../contexts/SidebarContext';

const blink = keyframes`
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
`;

interface Assignment {
  id: string;
  name: string;
  description: string | null;
  subject_id: string | null;
  tasks_count: number;
  files_count: number;
}

interface AssignmentsResponse {
  items: Assignment[];
}

interface SubjectWithAssignments {
  id: string;
  name: string;
  description: string | null;
  created_at: string | null;
  assignments_count: number;
  assignments: Assignment[];
}

interface SubjectsWithAssignmentsResponse {
  subjects: SubjectWithAssignments[];
  uncategorized: Assignment[];
}

interface SubjectGroup {
  id: string;
  name: string;
  isUncategorized: boolean;
  assignments: Assignment[];
}

const SIDEBAR_LOCAL_STORAGE_KEY = 'sidebar-subjects-collapsed';

const classicMenuItems = [
  { path: '/dashboard', label: 'overview', icon: FiHome },
  { path: '/dashboard/assignments', label: 'assignments', icon: FiBookOpen },
  { path: '/dashboard/submissions', label: 'submissions', icon: FiFileText },
  { path: '/dashboard/graph', label: 'plagiarismGraph', icon: FiShare2 },
  { path: '/dashboard/upload', label: 'uploadFiles', icon: FiUpload },
  { path: '/dashboard/results', label: 'results', icon: FiBarChart2 },
  { path: '/dashboard/pair-comparison', label: 'pairComparison', icon: FiColumns },
];

const SortableAssignment: React.FC<{
  assignment: Assignment;
  isCurrent: boolean;
  hoverBg: string;
  t: (key: string) => string;
  isDragging?: boolean;
}> = ({ assignment, isCurrent, hoverBg, t, isDragging }) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: assignment.id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  const path = `/dashboard/assignments/${assignment.id}`;

  return (
    <Box ref={setNodeRef} style={style} {...attributes}>
      <NavLink to={path} style={{ textDecoration: 'none' }}>
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
          <Icon
            as={MdDragIndicator}
            boxSize={3}
            flexShrink={0}
            opacity={0.4}
            cursor="grab"
            {...listeners}
          />
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
    </Box>
  );
};

const Sidebar: React.FC = () => {
  const { t: tNav } = useTranslation('navigation');
  const { t: tCommon } = useTranslation();
  const location = useLocation();
  const { mode } = useViewMode();
  const { user } = useAuth();
  const { isMobileOpen, closeMobile } = useSidebar();
  const [assignmentsExpanded, setAssignmentsExpanded] = useState(true);
  const [isBlinking, setIsBlinking] = useState(false);
  const [collapsedSubjects, setCollapsedSubjects] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem(SIDEBAR_LOCAL_STORAGE_KEY);
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [activeDragId, setActiveDragId] = useState<string | null>(null);

  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.700');
  const logoColor = useColorModeValue('black', 'white');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');
  const sectionColor = useColorModeValue('gray.400', 'gray.500');
  const scrollbarBg = useColorModeValue('gray.300', 'gray.600');
  const subjectHeaderBg = useColorModeValue('gray.50', 'gray.700');
  const subjectHeaderHoverBg = useColorModeValue('gray.100', 'gray.600');

  const { data: assignmentsData, isLoading: assignmentsLoading } = useQuery<AssignmentsResponse>({
    queryKey: ['assignments'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.ASSIGNMENTS);
      return res.data;
    },
  });

  const assignments = assignmentsData?.items || [];

  const { data: subjectsData, isLoading: subjectsLoading } = useQuery<SubjectsWithAssignmentsResponse>({
    queryKey: ['subjects', 'with-uncategorized'],
    queryFn: async () => {
      const res = await api.get(API_ENDPOINTS.SUBJECTS);
      return res.data;
    },
    staleTime: 60_000,
  });

  const subjects = subjectsData?.subjects || [];
  const uncategorizedAssignments = subjectsData?.uncategorized || [];

  const isLoading = assignmentsLoading || subjectsLoading;

  const isActive = (path: string) => location.pathname === path || location.pathname === `${path}/`;

  const toggleSubject = (subjectId: string) => {
    setCollapsedSubjects(prev => {
      const next = new Set(prev);
      if (next.has(subjectId)) {
        next.delete(subjectId);
      } else {
        next.add(subjectId);
      }
      try {
        localStorage.setItem(SIDEBAR_LOCAL_STORAGE_KEY, JSON.stringify(Array.from(next)));
      } catch { /* ignore */ }
      return next;
    });
  };

  const buildSubjectGroups = useCallback((): SubjectGroup[] => {
    const subjectMap = new Map<string, Assignment[]>();
    if (subjects) {
      for (const s of subjects) {
        subjectMap.set(s.id, s.assignments || []);
      }
    }
    // Use uncategorized from the API response, not from assignments
    const uncategorized = uncategorizedAssignments || [];

    const sortAssignments = (groupId: string, arr: Assignment[]) => {
      try {
        const saved = JSON.parse(localStorage.getItem(`sidebar-order-${groupId}`) || '[]');
        if (saved.length > 0) {
          const idSet = new Set(arr.map(a => a.id));
          const assignmentMap = new Map(arr.map(a => [a.id, a]));
          const ordered: Assignment[] = [];
          for (const id of saved) {
            if (idSet.has(id)) {
              const assignment = assignmentMap.get(id);
              if (assignment) ordered.push(assignment);
            }
          }
          const remaining = arr.filter(a => !ordered.includes(a));
          return [...ordered, ...remaining];
        }
      } catch { /* ignore */ }
      return arr;
    };

    const groups: SubjectGroup[] = [];

    for (const [id, subAssignments] of subjectMap) {
      const subject = subjects?.find(s => s.id === id);
      if (subAssignments.length > 0 || subject) {
        groups.push({
          id,
          name: subject?.name || '',
          isUncategorized: false,
          assignments: sortAssignments(id, subAssignments),
        });
      }
    }

    if (uncategorized.length > 0) {
      groups.push({
        id: '__uncategorized__',
        name: tCommon('uncategorized'),
        isUncategorized: true,
        assignments: sortAssignments('__uncategorized__', uncategorized),
      });
    }

    return groups;
  }, [assignments, subjects, tCommon, uncategorizedAssignments]);

  const subjectGroups = buildSubjectGroups();

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveDragId(null);

    if (!over || active.id === over.id) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    const activeGroup = subjectGroups.find(g => g.assignments.some(a => a.id === activeId));
    const overGroup = subjectGroups.find(g => g.id === overId || g.assignments.some(a => a.id === overId));

    if (!activeGroup || !overGroup) return;

    if (activeGroup.id !== overGroup.id) return;

    const newOrder = [...activeGroup.assignments.map(a => a.id)];
    const activeIdx = newOrder.indexOf(activeId);
    const overIdx = newOrder.indexOf(overId);
    if (activeIdx === -1 || overIdx === -1) return;

    const [moved] = newOrder.splice(activeIdx, 1);
    newOrder.splice(overIdx, 0, moved);

    const groupKey = `sidebar-order-${activeGroup.id}`;
    try {
      localStorage.setItem(groupKey, JSON.stringify(newOrder));
    } catch { /* ignore */ }
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveDragId(event.active.id as string);
  };

  return (
    <>
      {/* Desktop fixed sidebar - hidden on mobile */}
      <Box
        as="nav"
        pos="fixed"
        left="0"
        top="0"
        h="full"
        w={{ base: 0, lg: SIDEBAR_WIDTH_PX }}
        bg={bgColor}
        borderRight={{ base: 'none', lg: '1px' }}
        borderColor={borderColor}
        py={6}
        px={4}
        display={{ base: 'none', lg: 'flex' }}
        flexDirection="column"
        overflow="hidden"
      >
      <Box mb={6} px={4} cursor="pointer" onClick={() => setIsBlinking(!isBlinking)} title={tCommon('toggleBlink')}>
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
                <Text fontWeight="medium">{tNav(item.label)}</Text>
              </Flex>
            </NavLink>
          ))}
           {user?.is_global_admin && (
             <NavLink to="/dashboard/users" style={{ textDecoration: 'none' }}>
               <Flex
                 align="center"
                 px={4}
                 py={3}
                 borderRadius="md"
                 bg={isActive('/dashboard/users') ? 'brand.500' : 'transparent'}
                 color={isActive('/dashboard/users') ? 'white' : 'inherit'}
                 _hover={{
                   bg: isActive('/dashboard/users') ? 'brand.600' : hoverBg,
                 }}
                 transition="all 0.2s"
               >
                 <Icon as={FiUsers} boxSize={5} mr={3} />
                 <Text fontWeight="medium">{tCommon('users')}</Text>
               </Flex>
             </NavLink>
           )}
        </VStack>
      ) : (
        <DndContext
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
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
                <Text fontWeight="medium" fontSize="sm">{tNav('overview')}</Text>
              </Flex>
            </NavLink>

            <NavLink to="/dashboard/assignments" style={{ textDecoration: 'none' }}>
              <Flex
                align="center"
                px={4}
                py={2.5}
                borderRadius="md"
                bg={isActive('/dashboard/assignments') ? 'brand.500' : 'transparent'}
                color={isActive('/dashboard/assignments') ? 'white' : 'inherit'}
                _hover={{ bg: isActive('/dashboard/assignments') ? 'brand.600' : hoverBg }}
                transition="all 0.2s"
                gap={2}
              >
                <Icon as={FiList} boxSize={4.5} mr={1} />
                <Text fontWeight="medium" fontSize="sm">{tNav('viewAllAssignments')}</Text>
              </Flex>
            </NavLink>
          </VStack>

          <Divider my={4} />

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
              {tCommon('assignments')}
            </Text>
            <Icon
              as={assignmentsExpanded ? FiChevronDown : FiChevronRight}
              boxSize={3.5}
              color={sectionColor}
            />
          </Flex>

          {assignmentsExpanded && (
            <VStack spacing={0} align="stretch" flex="1" minH={0} overflowY="auto" css={{
              '&::-webkit-scrollbar': { width: '4px' },
              '&::-webkit-scrollbar-thumb': { bg: scrollbarBg, borderRadius: '2px' },
            }}>
              {isLoading ? (
                <Flex justify="center" py={4}>
                  <Spinner size="sm" />
                </Flex>
              ) : subjectGroups.length === 0 ? (
                <Text fontSize="xs" color={mutedColor} px={4} py={2}>
                  {tCommon('noAssignments')}
                </Text>
              ) : (
                subjectGroups.map((group) => {
                  const isCollapsed = collapsedSubjects.has(group.id);

                  return (
                    <Box key={group.id} mb={1}>
                      <Flex
                        align="center"
                        justify="space-between"
                        px={3}
                        py={1.5}
                        borderRadius="md"
                        cursor="pointer"
                        onClick={() => toggleSubject(group.id)}
                        userSelect="none"
                        bg={subjectHeaderBg}
                        _hover={{ bg: subjectHeaderHoverBg }}
                        transition="all 0.15s"
                      >
                        <HStack spacing={2} flex={1} minW={0}>
                          <Icon
                            as={isCollapsed ? FiChevronRight : FiChevronDown}
                            boxSize={3}
                            color={mutedColor}
                            flexShrink={0}
                          />
                          <Icon
                            as={FiFolder}
                            boxSize={3.5}
                            color={group.isUncategorized ? 'gray.400' : 'purple.500'}
                            flexShrink={0}
                          />
                          <Text
                            fontSize="xs"
                            fontWeight="semibold"
                            noOfLines={1}
                            color={group.isUncategorized ? mutedColor : 'inherit'}
                          >
                            {group.name}
                          </Text>
                          <Badge size="sm" colorScheme={group.isUncategorized ? 'gray' : 'purple'} flexShrink={0}>
                            {group.assignments.length}
                          </Badge>
                        </HStack>
                      </Flex>

                      {!isCollapsed && (
                        <VStack spacing={0} align="stretch" pl={2}>
                          <SortableContext items={group.assignments.map(a => a.id)} strategy={verticalListSortingStrategy}>
                            {group.assignments.map((assignment) => {
                              const path = `/dashboard/assignments/${assignment.id}`;
                              const isCurrent = location.pathname.startsWith(path);
                              const isDragging = activeDragId === assignment.id;

                              return (
                                <SortableAssignment
                                  key={assignment.id}
                                  assignment={assignment}
                                  isCurrent={isCurrent}
                                  hoverBg={hoverBg}
                                  t={tCommon}
                                  isDragging={isDragging}
                                />
                              );
                            })}
                          </SortableContext>
                        </VStack>
                      )}
                    </Box>
                  );
                })
              )}


            </VStack>
          )}

          <DragOverlay>
            {activeDragId ? (
              (() => {
                const assignment = assignments.find(a => a.id === activeDragId);
                if (!assignment) return null;
                return (
                <Box
                  bg={bgColor}
                  borderRadius="md"
                  shadow="lg"
                  px={3}
                  py={2}
                  opacity={0.9}
                  border="1px"
                  borderColor={borderColor}
                  pointerEvents="none"
                >
                    <Flex align="center" gap={2}>
                      <Icon as={FiBookOpen} boxSize={4} />
                      <Text fontSize="sm" fontWeight="medium">{assignment.name}</Text>
                    </Flex>
                  </Box>
                );
              })()
            ) : null}
           </DragOverlay>
         </DndContext>
       )}

      {/* Footer with language switcher */}
      <Box mt="auto" pt={4} borderTopWidth="1px" borderColor={borderColor} px={4}>
        <LanguageSwitcherFooter />
      </Box>
    </Box>

    {/* Mobile drawer sidebar */}
    <Drawer isOpen={isMobileOpen} placement="left" onClose={closeMobile} size="xs">
      <DrawerOverlay />
      <DrawerContent bg={bgColor}>
        <DrawerCloseButton />
        <DrawerHeader px={4}>
          <Box cursor="pointer" onClick={() => { setIsBlinking(!isBlinking); closeMobile(); }} title={tCommon('toggleBlink')}>
            <Text
              fontSize="1.4rem"
              fontWeight="bold"
              fontFamily="monospace"
              letterSpacing="0.05em"
              userSelect="none"
            >
              <span style={{ color: logoColor }}>plagi</span>
              <span style={{ color: '#38A169' }}>type</span>
              <Box as="span" sx={isBlinking ? { animation: `${blink} 1s infinite` } : undefined}>_</Box>
            </Text>
          </Box>
        </DrawerHeader>
        <DrawerBody p={0} overflow="auto">
          {/* Classic menu items for mobile */}
          <VStack spacing={1} align="stretch" px={2} py={2}>
            {classicMenuItems.map((item) => (
              <NavLink key={item.path} to={item.path} style={{ textDecoration: 'none' }} onClick={closeMobile}>
                <Flex
                  align="center"
                  px={3}
                  py={2.5}
                  borderRadius="md"
                  bg={isActive(item.path) ? 'brand.500' : 'transparent'}
                  color={isActive(item.path) ? 'white' : 'inherit'}
                  _hover={{ bg: isActive(item.path) ? 'brand.600' : hoverBg }}
                  transition="all 0.2s"
                >
                  <Icon as={item.icon} boxSize={4.5} mr={3} />
                  <Text fontWeight="medium" fontSize="sm">{tNav(item.label)}</Text>
                </Flex>
              </NavLink>
            ))}
            {user?.is_global_admin && (
              <NavLink to="/dashboard/users" style={{ textDecoration: 'none' }} onClick={closeMobile}>
                <Flex
                  align="center"
                  px={3}
                  py={2.5}
                  borderRadius="md"
                  bg={isActive('/dashboard/users') ? 'brand.500' : 'transparent'}
                  color={isActive('/dashboard/users') ? 'white' : 'inherit'}
                  _hover={{ bg: isActive('/dashboard/users') ? 'brand.600' : hoverBg }}
                  transition="all 0.2s"
                >
                  <Icon as={FiUsers} boxSize={4.5} mr={3} />
                  <Text fontWeight="medium" fontSize="sm">{tCommon('users')}</Text>
                </Flex>
              </NavLink>
            )}
            <Divider my={2} />
            <NavLink to="/dashboard/assignments" style={{ textDecoration: 'none' }} onClick={closeMobile}>
              <Flex
                align="center"
                px={3}
                py={2}
                borderRadius="md"
                bg={isActive('/dashboard/assignments') ? 'brand.500' : 'transparent'}
                color={isActive('/dashboard/assignments') ? 'white' : 'inherit'}
                _hover={{ bg: isActive('/dashboard/assignments') ? 'brand.600' : hoverBg }}
                transition="all 0.2s"
              >
                <Icon as={FiList} boxSize={4.5} mr={3} />
                <Text fontWeight="medium" fontSize="sm">{tNav('viewAllAssignments')}</Text>
              </Flex>
            </NavLink>
          </VStack>

          {/* Assignments list for mobile */}
          <Box px={2} py={2} overflow="auto" maxH="calc(100vh - 280px)">
            {isLoading ? (
              <Flex justify="center" py={4}>
                <Spinner size="sm" />
              </Flex>
            ) : subjectGroups.length === 0 ? (
              <Text fontSize="xs" color={mutedColor} px={2} py={2}>
                {tCommon('noAssignments')}
              </Text>
            ) : (
              <VStack spacing={1} align="stretch">
                {subjectGroups.map((group) => {
                  const isCollapsed = collapsedSubjects.has(group.id);
                  return (
                    <Box key={group.id}>
                      <Flex
                        align="center"
                        justify="space-between"
                        px={2}
                        py={1.5}
                        borderRadius="md"
                        cursor="pointer"
                        onClick={() => toggleSubject(group.id)}
                        userSelect="none"
                        bg={subjectHeaderBg}
                        _hover={{ bg: subjectHeaderHoverBg }}
                        transition="all 0.15s"
                      >
                        <HStack spacing={1.5} flex={1} minW={0}>
                          <Icon
                            as={isCollapsed ? FiChevronRight : FiChevronDown}
                            boxSize={3}
                            color={mutedColor}
                          />
                          <Icon
                            as={FiFolder}
                            boxSize={3.5}
                            color={group.isUncategorized ? 'gray.400' : 'purple.500'}
                          />
                          <Text fontSize="xs" fontWeight="semibold" noOfLines={1}>
                            {group.name}
                          </Text>
                          <Badge size="sm" colorScheme={group.isUncategorized ? 'gray' : 'purple'} flexShrink={0}>
                            {group.assignments.length}
                          </Badge>
                        </HStack>
                      </Flex>
                      {!isCollapsed && (
                        <VStack spacing={0} align="stretch" pl={1}>
                          {group.assignments.map((assignment) => (
                            <NavLink
                              key={assignment.id}
                              to={`/dashboard/assignments/${assignment.id}`}
                              style={{ textDecoration: 'none' }}
                              onClick={closeMobile}
                            >
                              <Flex
                                align="center"
                                px={3}
                                py={1.5}
                                borderRadius="md"
                                _hover={{ bg: hoverBg }}
                                transition="all 0.15s"
                              >
                                <Icon as={FiBookOpen} boxSize={3.5} mr={2} opacity={0.6} />
                                <Text fontSize="xs" noOfLines={1}>{assignment.name}</Text>
                              </Flex>
                            </NavLink>
                          ))}
                        </VStack>
                      )}
                    </Box>
                  );
                })}
              </VStack>
            )}
          </Box>
        </DrawerBody>
      </DrawerContent>
    </Drawer>
    </>
  );
};

const LanguageSwitcherFooter: React.FC = () => {
    const { t, i18n } = useTranslation();

    const languages = [
      { code: 'en', name: t('languageNames.en'), flag: '🇺🇸' },
      { code: 'ru', name: t('languageNames.ru'), flag: '🇷🇺' },
    ];

   const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0];

   const changeLanguage = (lng: string) => {
     i18n.changeLanguage(lng, (err) => {
       if (err) return console.error('Failed to change language:', err);
       try {
         localStorage.setItem('language', lng);
       } catch { /* ignore */ }
     });
   };

   return (
     <Menu>
       <MenuButton
         as={Button}
         variant="ghost"
         size="sm"
         w="full"
         justifyContent="flex-start"
         leftIcon={<FiGlobe />}
       >
         <HStack spacing={2}>
           <Text fontSize="lg">{currentLanguage.flag}</Text>
           <Text fontSize="sm" isTruncated>{currentLanguage.name}</Text>
         </HStack>
       </MenuButton>
       <MenuList>
         {languages.map((lang) => (
           <MenuItem
             key={lang.code}
             onClick={() => changeLanguage(lang.code)}
             bg={i18n.language === lang.code ? 'brand.50' : 'transparent'}
             _hover={{ bg: i18n.language === lang.code ? 'brand.100' : 'gray.100' }}
           >
             <HStack spacing={2}>
               <Text fontSize="lg">{lang.flag}</Text>
               <Text>{lang.name}</Text>
             </HStack>
           </MenuItem>
         ))}
       </MenuList>
     </Menu>
   );
 };

export default Sidebar;
