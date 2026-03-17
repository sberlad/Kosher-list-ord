<<<<<<< Updated upstream
import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import 'react-native-reanimated';

import { useColorScheme } from '@/hooks/use-color-scheme';
=======
import { DarkTheme, DefaultTheme, ThemeProvider } from "@react-navigation/native";
import { Stack } from "expo-router";
import { useColorScheme } from "../hooks/use-color-scheme";
>>>>>>> Stashed changes

export default function RootLayout() {
  const colorScheme = useColorScheme();

  return (
    <ThemeProvider value={colorScheme === "dark" ? DarkTheme : DefaultTheme}>
      <Stack>
        <Stack.Screen name="index" options={{ headerShown: false }} />
<<<<<<< Updated upstream
        <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
=======
        <Stack.Screen name="modal" options={{ presentation: "modal", title: "Modal" }} />
>>>>>>> Stashed changes
      </Stack>
    </ThemeProvider>
  );
}