import React from 'react';
import {
  Box,
  Flex,
  Text,
  Button,
  IconButton,
  useColorModeValue,
  useColorMode,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useMatch, useNavigate } from 'react-router';
import { FiMoon, FiSun } from 'react-icons/fi';
import LanguageSwitcher from './LanguageSwitcher';
import { useViewMode } from '../contexts/ViewModeContext';

const Header: React.FC = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const { t } = useTranslation('navigation');
  const { mode, setMode } = useViewMode();
  const navigate = useNavigate();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  // All hooks called unconditionally in same order
  const matchOverview = useMatch('/dashboard');
  const matchOverviewSlash = useMatch('/dashboard/');
  const matchAssignmentDetail = useMatch('/dashboard/assignments/:assignmentId');
  const matchAssignments = useMatch('/dashboard/assignments');
  const matchAssignmentsSlash = useMatch('/dashboard/assignments/');
  const matchSubmissions = useMatch('/dashboard/submissions');
  const matchGraph = useMatch('/dashboard/graph');
  const matchUpload = useMatch('/dashboard/upload');
  const matchResults = useMatch('/dashboard/results');
  const matchPairComparison = useMatch('/dashboard/pair-comparison');

  const getPageTitle = () => {
    if (matchOverview || matchOverviewSlash) return t('overview');
    if (matchAssignmentDetail) return t('assignments');
    if (matchAssignments || matchAssignmentsSlash) return t('assignments');
    if (matchSubmissions) return t('submissions');
    if (matchGraph) return t('plagiarismGraph');
    if (matchUpload) return t('uploadFiles');
    if (matchResults) return t('results');
    if (matchPairComparison) return t('pairComparison');
    return t('overview');
  };

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
      left="250px"
      right="0"
      h="16"
      bg={bgColor}
      borderBottom="1px"
      borderColor={borderColor}
      px={8}
      zIndex="sticky"
    >
      <Flex h="full" align="center" justify="space-between">
        <Text fontSize="lg" fontWeight="semibold">
          {getPageTitle()}
        </Text>

        <Flex align="center" gap={4}>
          {/* View mode toggle */}
          <Flex
            bg={useColorModeValue('gray.100', 'gray.700')}
            borderRadius="md"
            p="2px"
            flexShrink={0}
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

          <LanguageSwitcher />
          <IconButton
            aria-label="Toggle dark mode"
            icon={colorMode === 'light' ? <FiMoon /> : <FiSun />}
            onClick={toggleColorMode}
            variant="ghost"
            size="md"
          />
        </Flex>
      </Flex>
    </Box>
  );
};

export default Header;
