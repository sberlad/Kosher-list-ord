import React, { createContext, useContext, useState } from "react";

export interface AppSettings {
  pesachMode: boolean;
  kitniyotAllowed: boolean;
  setPesachMode: (v: boolean) => void;
  setKitniyotAllowed: (v: boolean) => void;
}

const AppSettingsContext = createContext<AppSettings>({
  pesachMode: false,
  kitniyotAllowed: false,
  setPesachMode: () => {},
  setKitniyotAllowed: () => {},
});

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  const [pesachMode, setPesachMode] = useState(false);
  const [kitniyotAllowed, setKitniyotAllowed] = useState(false);

  return (
    <AppSettingsContext.Provider
      value={{ pesachMode, kitniyotAllowed, setPesachMode, setKitniyotAllowed }}
    >
      {children}
    </AppSettingsContext.Provider>
  );
}

export function useAppSettings(): AppSettings {
  return useContext(AppSettingsContext);
}
