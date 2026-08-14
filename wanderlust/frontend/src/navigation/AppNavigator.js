import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';

import { useAuth } from '../context/AuthContext';
import { Loading } from '../components/ui';
import { colors } from '../theme/theme';

import LoginScreen from '../screens/LoginScreen';
import RegisterScreen from '../screens/RegisterScreen';
import HomeScreen from '../screens/HomeScreen';
import RecommendScreen from '../screens/RecommendScreen';
import ResearchScreen from '../screens/ResearchScreen';
import ProfileScreen from '../screens/ProfileScreen';
import DestinationDetailScreen from '../screens/DestinationDetailScreen';

const RootStack = createNativeStackNavigator();
const AuthStack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

// Signed-out flow: login + registration.
function AuthNavigator() {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="Register" component={RegisterScreen} />
    </AuthStack.Navigator>
  );
}

const TAB_ICONS = {
  Discover: ['compass', 'compass-outline'],
  Recommend: ['sparkles', 'sparkles-outline'],
  Research: ['stats-chart', 'stats-chart-outline'],
  Profile: ['person', 'person-outline'],
};

// Signed-in bottom tabs.
function TabsNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: {
          borderTopColor: colors.border,
          backgroundColor: colors.surface,
          height: 60,
          paddingBottom: 7,
          paddingTop: 7,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '700', letterSpacing: -0.1 },
        tabBarIcon: ({ focused, color, size }) => {
          const [on, off] = TAB_ICONS[route.name] || ['ellipse', 'ellipse-outline'];
          return <Ionicons name={focused ? on : off} size={size - 1} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Discover" component={HomeScreen} />
      <Tab.Screen name="Recommend" component={RecommendScreen} />
      <Tab.Screen
        name="Research"
        component={ResearchScreen}
        options={{ tabBarLabel: 'Model Lab' }}
      />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

/**
 * Root navigator.
 *
 * The detail screen lives at the root (a sibling of the tab navigator) so it
 * can be opened from any tab via navigation.navigate('DestinationDetail', ...).
 */
export default function AppNavigator() {
  const { user, booting } = useAuth();

  if (booting) {
    return <Loading text="Starting Wanderlust..." />;
  }

  if (!user) {
    return <AuthNavigator />;
  }

  return (
    <RootStack.Navigator>
      <RootStack.Screen
        name="Tabs"
        component={TabsNavigator}
        options={{ headerShown: false }}
      />
      {/* The detail screen draws its own back control over the hero image, so
          the navigation header would only cover the photograph. */}
      <RootStack.Screen
        name="DestinationDetail"
        component={DestinationDetailScreen}
        options={{ headerShown: false }}
      />
    </RootStack.Navigator>
  );
}
