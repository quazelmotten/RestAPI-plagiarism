import React, { createContext, useContext, useState } from 'react';

interface AssignmentInfo {
  name: string;
  filesCount: number;
  tasksCount: number;
}

interface AssignmentContextValue {
  assignmentInfo: AssignmentInfo | null;
  setAssignmentInfo: (info: AssignmentInfo | null) => void;
}

const AssignmentContext = createContext<AssignmentContextValue>({
  assignmentInfo: null,
  setAssignmentInfo: () => {},
});

export const AssignmentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [assignmentInfo, setAssignmentInfo] = useState<AssignmentInfo | null>(null);
  return (
    <AssignmentContext.Provider value={{ assignmentInfo, setAssignmentInfo }}>
      {children}
    </AssignmentContext.Provider>
  );
};

export const useAssignmentInfo = () => useContext(AssignmentContext);