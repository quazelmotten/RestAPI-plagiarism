import React from 'react';
import { Routes, Route } from 'react-router-dom';
import {
  Box,
  Flex,
  useColorModeValue,
} from '@chakra-ui/react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import Overview from './Overview';
import Students from './Students';
import Submissions from './Submissions';
import PlagiarismGraph from './PlagiarismGraph';
import Upload from './Upload';

const Dashboard: React.FC = () => {
  return (
    <Flex minH="100vh" bg={useColorModeValue('gray.100', 'gray.900')}>
      <Sidebar />
      <Box flex="1" ml="250px">
        <Header />
        <Box as="main" p={8} pt={24}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/students" element={<Students />} />
            <Route path="/submissions" element={<Submissions />} />
            <Route path="/graph" element={<PlagiarismGraph />} />
            <Route path="/upload" element={<Upload />} />
          </Routes>
        </Box>
      </Box>
    </Flex>
  );
};

export default Dashboard;
