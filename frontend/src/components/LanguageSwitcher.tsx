import { Menu, MenuButton, MenuList, MenuItem, Icon, Text, Button } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { FiGlobe } from 'react-icons/fi';

const LanguageSwitcher = () => {
  const { i18n } = useTranslation();

  const languages = [
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'ru', name: 'Русский', flag: '🇷🇺' },
  ];

  const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0];

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng, (err, t) => {
      if (err) return console.error('Failed to change language:', err);
      localStorage.setItem('language', lng);
    });
  };

  return (
    <Menu>
      <MenuButton
        as={Button}
        variant="ghost"
        size="md"
        aria-label="Switch language"
        leftIcon={<FiGlobe />}
      >
        {currentLanguage.flag}
      </MenuButton>
      <MenuList>
        {languages.map((lang) => (
          <MenuItem
            key={lang.code}
            onClick={() => changeLanguage(lang.code)}
            bg={i18n.language === lang.code ? 'brand.500' : 'transparent'}
            color={i18n.language === lang.code ? 'white' : 'inherit'}
            _hover={{
              bg: i18n.language === lang.code ? 'brand.600' : 'gray.100',
            }}
          >
            <Text mr={2}>{lang.flag}</Text>
            {lang.name}
          </MenuItem>
        ))}
      </MenuList>
    </Menu>
  );
};

export default LanguageSwitcher;
