import React, { useState } from 'react';
import { Box, Button, FormControl, FormLabel, Input, Heading, Alert, AlertIcon, VStack, Text } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';

const Profile: React.FC = () => {
  const { user, changePassword, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { t } = useTranslation();

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      setMessage(t('passwordChangedSuccessfully'));
      setCurrentPassword('');
      setNewPassword('');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || t('failedToChangePassword'));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    // redirect handled by interceptor
  };

  if (!user) return null;

  return (
    <Box maxW="md" mx="auto" mt={8} p={4}>
      <Heading mb={6}>{t('profile')}</Heading>
      <Text mb={4}>{t('labels.email')} {user.email}</Text>
      <form onSubmit={handleChangePassword}>
        <VStack spacing={4} align="stretch">
          <FormControl isRequired>
            <FormLabel>{t('currentPassword')}</FormLabel>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </FormControl>
          <FormControl isRequired>
            <FormLabel>{t('newPassword')}</FormLabel>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </FormControl>
          <Button type="submit" colorScheme="brand" isLoading={loading}>
            {t('changePassword')}
          </Button>
        </VStack>
      </form>
      {error && (
        <Alert status="error" mt={4}>
          <AlertIcon />
          {error}
        </Alert>
      )}
      {message && (
        <Alert status="success" mt={4}>
          <AlertIcon />
          {message}
        </Alert>
      )}
      <Button mt={6} variant="outline" onClick={handleLogout} colorScheme="red">
        {t('logout')}
      </Button>
    </Box>
  );
};

export default Profile;
