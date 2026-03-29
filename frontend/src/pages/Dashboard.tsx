import React from 'react';
import { Routes, Route } from 'react-router';
import {
  Box,
  Flex,
  useColorModeValue,
} from '@chakra-ui/react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import Overview from './Overview';
import Submissions from './Submissions';
import PlagiarismGraph from './PlagiarismGraph';
import Upload from './Upload';
import Results from './Results';
import PairComparison from './PairComparison';
import Assignments from './Assignments';

const Dashboard: React.FC = () => {
  return (
    <Flex h="100vh" bg={useColorModeValue('gray.100', 'gray.900')}>
      <Sidebar />
      <Box flex="1" ml="250px" display="flex" flexDirection="column" overflow="hidden">
        <Header />
        <Box as="main" p={8} pt={24} flex="1" overflow="hidden" minH="0" display="flex" flexDirection="column">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="assignments" element={<Assignments />} />
            <Route path="submissions" element={<Submissions />} />
            <Route path="graph" element={<PlagiarismGraph />} />
            <Route path="upload" element={<Upload />} />
            <Route path="results" element={<Results />} />
            <Route path="pair-comparison" element={<PairComparison />} />
          </Routes>
        </Box>
      </Box>
    </Flex>
  );
};

export default Dashboard;
