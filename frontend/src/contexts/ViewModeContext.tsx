import { createContext, useContext } from 'react';

export type ViewMode = 'assignments' | 'classic';

interface ViewModeContextValue {
  mode: ViewMode;
  setMode: (mode: ViewMode) => void;
}

export const ViewModeContext = createContext<ViewModeContextValue | null>(null);

export const useViewMode = (): ViewModeContextValue => {
  const context = useContext(ViewModeContext);
  if (!context) {
    throw new Error('useViewMode must be used within a ViewModeContext.Provider');
  }
  return context;
};
