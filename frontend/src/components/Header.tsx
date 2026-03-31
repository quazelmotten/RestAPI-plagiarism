import React from 'react';
import {
  Box,
  Flex,
  Text,
  IconButton,
  useColorModeValue,
  useColorMode,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiMoon, FiSun } from 'react-icons/fi';
import LanguageSwitcher from './LanguageSwitcher';

const Header: React.FC = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const { t } = useTranslation('navigation');
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

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
          {t('dashboard')}
        </Text>

        <Flex align="center" gap={2}>
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
