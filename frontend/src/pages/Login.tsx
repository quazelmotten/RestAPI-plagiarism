import { useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Text,
  useToast,
  Container,
  Card,
  CardBody,
  HStack,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Icon,
} from '@chakra-ui/react';
import { FiGlobe } from 'react-icons/fi';
import { login, register, isAuthenticated } from '../services/api';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';

function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'signin' | 'signup'>('signin');
  const navigate = useNavigate();
  const toast = useToast();
  const { t, i18n } = useTranslation();

  if (isAuthenticated()) {
    navigate('/dashboard');
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      if (viewMode === 'signup') {
        await register(email, password);
        toast({
          title: t('registrationSuccessful'),
          status: 'success',
          duration: 3000,
        });
      } else {
        await login(email, password);
        toast({
          title: t('loginSuccessful'),
          status: 'success',
          duration: 3000,
        });
      }
      // Navigation is handled automatically at the top of the component
    } catch (error: unknown) {
      const message = error instanceof Error 
        ? error.message 
        : t(viewMode === 'signup' ? 'registrationFailed' : 'loginFailedCheckCredentials');
      toast({
        title: t(viewMode === 'signup' ? 'registrationFailed' : 'loginFailed'),
        description: message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

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
    <Container maxW="md" py={20}>
      <Card>
        <CardBody>
          <VStack spacing={6} as="form" onSubmit={handleSubmit}>
            <Heading size="lg">{viewMode === 'signin' ? t('signIn') : t('signUp')}</Heading>
            
            {/* View Toggle - Classic/Assignment style */}
            <Box 
              border="1px" 
              borderColor="gray.200" 
              borderRadius="md" 
              p={1}
              bg="gray.50"
            >
              <HStack spacing={1}>
                <Button
                  size="sm"
                  variant={viewMode === 'signin' ? 'solid' : 'ghost'}
                  colorScheme={viewMode === 'signin' ? 'brand' : 'gray'}
                  onClick={() => setViewMode('signin')}
                  flex={1}
                >
                  {t('signIn')}
                </Button>
                <Button
                  size="sm"
                  variant={viewMode === 'signup' ? 'solid' : 'ghost'}
                  colorScheme={viewMode === 'signup' ? 'brand' : 'gray'}
                  onClick={() => setViewMode('signup')}
                  flex={1}
                >
                  {t('signUp')}
                </Button>
              </HStack>
            </Box>

            <Text color="gray.600">
              {viewMode === 'signin' 
                ? t('enterCredentialsSignIn') 
                : t('createAccountSignUp')
              }
            </Text>
<FormControl isRequired>
  <FormLabel>{t('email')}</FormLabel>
  <Input
    type="email"
    value={email}
    onChange={(e) => setEmail(e.target.value)}
    placeholder={t('placeholders.email')}
  />
</FormControl>
<FormControl isRequired>
  <FormLabel>{t('password')}</FormLabel>
  <Input
    type="password"
    value={password}
    onChange={(e) => setPassword(e.target.value)}
    placeholder={t('placeholders.password')}
  />
</FormControl>
            <Button
              type="submit"
              colorScheme="brand"
              width="full"
              isLoading={isLoading}
            >
              {viewMode === 'signin' ? t('signIn') : t('signUp')}
            </Button>
          </VStack>
        </CardBody>
      </Card>
      
      {/* Subtle language switcher */}
      <Box mt={4} display="flex" justifyContent="center">
        <Menu>
          <MenuButton
            as={Button}
            variant="ghost"
            size="xs"
            opacity={0.6}
            _hover={{ opacity: 1 }}
            leftIcon={<Icon as={FiGlobe} boxSize={3} />}
          >
            <HStack spacing={1}>
              <Text fontSize="sm">{currentLanguage.flag}</Text>
              <Text fontSize="xs">{currentLanguage.name}</Text>
            </HStack>
          </MenuButton>
          <MenuList>
            {languages.map((lang) => (
              <MenuItem
                key={lang.code}
                onClick={() => changeLanguage(lang.code)}
                fontSize="xs"
                py={1.5}
                bg={i18n.language === lang.code ? 'brand.50' : 'transparent'}
                _hover={{ bg: i18n.language === lang.code ? 'brand.100' : 'gray.100' }}
              >
                <HStack spacing={2}>
                  <Text fontSize="sm">{lang.flag}</Text>
                  <Text fontSize="xs">{lang.name}</Text>
                </HStack>
              </MenuItem>
            ))}
          </MenuList>
        </Menu>
      </Box>
    </Container>
  );
}

export default Login;