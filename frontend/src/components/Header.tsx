import React, { useMemo } from 'react';
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
import { useLocation, useNavigate } from 'react-router';
import { FiMoon, FiSun } from 'react-icons/fi';
import LanguageSwitcher from './LanguageSwitcher';
import { useViewMode } from '../contexts/ViewModeContext';
import { SIDEBAR_WIDTH_PX } from '../constants/layout';

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

const Header: React.FC = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const { t } = useTranslation('navigation');
  const { mode, setMode } = useViewMode();
  const navigate = useNavigate();
  const location = useLocation();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  const pageTitle = useMemo(() => {
    const path = location.pathname;
    for (const [route, titleKey] of Object.entries(ROUTE_TITLES)) {
      if (path === route || path.startsWith(`${route}/`)) {
        return t(titleKey);
      }
    }
    return t('overview');
  }, [location.pathname, t]);

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
      left={SIDEBAR_WIDTH_PX}
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
          {pageTitle}
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
