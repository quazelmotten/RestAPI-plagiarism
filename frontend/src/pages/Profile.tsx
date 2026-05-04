import React from 'react';
import { Box, Button, Heading, VStack, Text } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';

const Profile: React.FC = () => {
  const { user, logout } = useAuth();

  const { t } = useTranslation();



  const handleLogout = async () => {
    await logout();
    // redirect handled by interceptor
  };

  if (!user) return null;

  return (
    <Box maxW="md" mx="auto" mt={8} p={4}>
      <Heading mb={6}>{t('profile')}</Heading>
      <VStack align="stretch" spacing={4}>
        <Box>
          <Text fontSize="sm" fontWeight="medium" mb={2}>{t('currentEmail') || 'Current email'}</Text>
          <Text>{user?.email || '—'}</Text>
        </Box>
        <Box>
          <Text fontSize="sm" fontWeight="medium" mb={2}>{t('currentUsername') || 'Current username'}</Text>
          <Text>{user?.username || '—'}</Text>
        </Box>
        <Text color="gray.500" fontSize="sm">
          {t('changePasswordInSettings') || 'Change your password in the Settings page.'}
        </Text>
      </VStack>
      <Button mt={6} variant="outline" onClick={handleLogout} colorScheme="red">
        {t('logout')}
      </Button>
    </Box>
  );
};

export default Profile;
