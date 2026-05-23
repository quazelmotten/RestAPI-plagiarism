import React, { useState } from 'react';
import { Box, Text, Tabs, TabList, Tab, TabPanels, TabPanel, useColorModeValue } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import Overview from '../Overview';
import Storage from '../Storage';
import Users from '../Users';

const Stat: React.FC<{ label: string; value: string | number; color?: string }> = ({ label, value, color }) => {
  const colorScheme = color || 'brand';
  return (
    <Box p={4} bg={useColorModeValue('white', 'gray.700')} borderRadius="lg" borderWidth="1px" borderColor={useColorModeValue('gray.200', 'gray.600')}>
      <Text fontSize="3xl" fontWeight="bold" color={`${colorScheme}.500`}>{value}</Text>
      <Text fontSize="sm" color="gray.500">{label}</Text>
    </Box>
  );
};

const Admin: React.FC<{ initialTab?: number }> = ({ initialTab = 0 }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState(initialTab);
  return (
    <Box>
      <Tabs index={activeTab} onChange={setActiveTab}>
        <TabList>
          <Tab>{t('common:stats') || 'Stats'}</Tab>
          <Tab>{t('common:storage') || 'Storage'}</Tab>
          <Tab>{t('common:adminUsers') || 'Users'}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel px={0} pt={4}>
            <Overview />
          </TabPanel>
          <TabPanel px={0} pt={4}>
            <Storage />
          </TabPanel>
          <TabPanel px={0} pt={4}>
            <Users />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
};

export default Admin;
