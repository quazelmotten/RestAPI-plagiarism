import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Icon,
  useColorModeValue,
  Portal,
  Flex,
} from '@chakra-ui/react';
import { FiFolder, FiChevronDown, FiCheck } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useSubjectsWithAssignments } from '../../hooks/useSubjects';
import type { SubjectWithAssignments, Assignment } from '../../types';

interface DropdownPosition {
  top: number;
  left: number;
  width: number;
}

interface AssignmentFilterProps {
  selectedAssignmentId: string | null;
  onSelect: (assignmentId: string | null) => void;
}

const NO_SELECTION = '__none__';

export const AssignmentFilter: React.FC<AssignmentFilterProps> = ({
  selectedAssignmentId,
  onSelect,
}) => {
  const { t } = useTranslation(['review', 'common']);
  const [isOpen, setIsOpen] = useState(false);
  const [dropdownPos, setDropdownPos] = useState<DropdownPosition | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  const { data: subjects, isLoading } = useSubjectsWithAssignments();

  const bg = useColorModeValue('white', 'gray.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.600');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const selectedBg = useColorModeValue('brand.50', 'whiteAlpha.100');

  const subjectHeaderBg = useColorModeValue('gray.50', 'gray.800');

  const updatePosition = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + 4 + window.scrollY,
        left: rect.left + window.scrollX,
        width: Math.max(rect.width, 280),
      });
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      updatePosition();
      window.addEventListener('scroll', updatePosition, true);
      window.addEventListener('resize', updatePosition);
      return () => {
        window.removeEventListener('scroll', updatePosition, true);
        window.removeEventListener('resize', updatePosition);
      };
    }
  }, [isOpen, updatePosition]);

  const getSelectedLabel = () => {
    if (!selectedAssignmentId) return t('review:allAssignments', { defaultValue: 'All Assignments' });
    for (const subject of subjects || []) {
      for (const assignment of subject.assignments || []) {
        if (assignment.id === selectedAssignmentId) {
          return assignment.name;
        }
      }
    }
    return t('review:allAssignments', { defaultValue: 'All Assignments' });
  };

  const handleSelect = (value: string) => {
    if (value === NO_SELECTION) {
      onSelect(null);
    } else {
      onSelect(value);
    }
    setIsOpen(false);
  };

  if (isLoading || !subjects) {
    return (
      <Box
        display="inline-flex"
        alignItems="center"
        gap={2}
        px={3}
        py={1.5}
        bg={bg}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="md"
        fontSize="sm"
        minW="200px"
        cursor="default"
      >
        <Icon as={FiFolder} boxSize={3.5} color="gray.400" />
        <Text color={mutedColor} noOfLines={1} flex={1}>
          {t('common:loading', { defaultValue: 'Loading...' })}
        </Text>
        <Icon as={FiChevronDown} boxSize={3.5} color="gray.400" />
      </Box>
    );
  }

  const allAssignments: { subjectName: string | null; assignment: Assignment }[] = [];
  for (const subject of subjects) {
    for (const assignment of subject.assignments || []) {
      allAssignments.push({ subjectName: subject.name, assignment });
    }
  }

  return (
    <Box position="relative" display="inline-block">
      <Box
        ref={triggerRef}
        display="inline-flex"
        alignItems="center"
        gap={2}
        px={3}
        py={1.5}
        bg={bg}
        borderWidth={1}
        borderColor={isOpen ? 'brand.400' : borderColor}
        borderRadius="md"
        fontSize="sm"
        minW="200px"
        maxW="300px"
        cursor="pointer"
        onClick={() => setIsOpen(!isOpen)}
        _hover={{ borderColor: 'brand.300' }}
        role="button"
        tabIndex={0}
      >
        <Icon as={FiFolder} boxSize={3.5} color="purple.400" />
        <Text noOfLines={1} flex={1}>
          {getSelectedLabel()}
        </Text>
        <Icon as={FiChevronDown} boxSize={3.5} color="gray.400" />
      </Box>

      {isOpen && dropdownPos && (
        <>
          <Box
            position="fixed"
            top={0}
            left={0}
            right={0}
            bottom={0}
            zIndex={10}
            onClick={() => setIsOpen(false)}
          />
          <Portal>
            <VStack
              spacing={0}
              position="absolute"
              top={dropdownPos.top}
              left={dropdownPos.left}
              minW={dropdownPos.width}
              maxW="400px"
              maxH="400px"
              overflowY="auto"
              bg={bg}
              borderWidth={1}
              borderColor={borderColor}
              borderRadius="md"
              boxShadow="lg"
              zIndex={20}
              align="stretch"
              css={{
                '&::-webkit-scrollbar': { width: '6px' },
                '&::-webkit-scrollbar-thumb': { bg: 'gray.300', borderRadius: '3px' },
              }}
            >
              <Flex
                px={3}
                py={2}
                align="center"
                gap={2}
                cursor="pointer"
                bg={!selectedAssignmentId ? selectedBg : 'transparent'}
                _hover={{ bg: hoverBg }}
                onClick={() => handleSelect(NO_SELECTION)}
              >
                <Icon as={FiFolder} boxSize={3.5} color="purple.400" />
                <Text fontSize="sm" fontWeight="medium" flex={1}>
                  {t('review:allAssignments', { defaultValue: 'All Assignments' })}
                </Text>
                {!selectedAssignmentId && <Icon as={FiCheck} boxSize={3.5} color="brand.500" />}
              </Flex>

              {subjects.map((subject: SubjectWithAssignments) => (
                <React.Fragment key={subject.id}>
                  <Box px={3} py={1.5} bg={subjectHeaderBg}>
                    <HStack spacing={1.5}>
                      <Icon as={FiFolder} boxSize={3} color="purple.300" />
                      <Text fontSize="xs" fontWeight="semibold" color={mutedColor} textTransform="uppercase" letterSpacing="wider">
                        {subject.name}
                      </Text>
                    </HStack>
                  </Box>
                  {(subject.assignments || []).map((assignment: Assignment) => (
                    <Flex
                      key={assignment.id}
                      px={3}
                      py={2}
                      pl={7}
                      align="center"
                      gap={2}
                      cursor="pointer"
                      bg={selectedAssignmentId === assignment.id ? selectedBg : 'transparent'}
                      _hover={{ bg: hoverBg }}
                      onClick={() => handleSelect(assignment.id)}
                    >
                      <Text fontSize="sm" noOfLines={1} flex={1}>
                        {assignment.name}
                      </Text>
                      {selectedAssignmentId === assignment.id && (
                        <Icon as={FiCheck} boxSize={3.5} color="brand.500" />
                      )}
                    </Flex>
                  ))}
                </React.Fragment>
              ))}

              {allAssignments.length === 0 && (
                <Flex px={3} py={4} justify="center">
                  <Text fontSize="sm" color={mutedColor}>
                    {t('review:noAssignments', { defaultValue: 'No assignments found' })}
                  </Text>
                </Flex>
              )}
            </VStack>
          </Portal>
        </>
      )}
    </Box>
  );
};

export default AssignmentFilter;
