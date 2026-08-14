import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../context/AuthContext';
import { ErrorNotice, Field, PrimaryButton } from '../components/ui';
import { colors, radius, spacing, type } from '../theme/theme';

export default function LoginScreen({ navigation }) {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const onSubmit = async () => {
    if (!username || !password) {
      setError('Please enter your username and password.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await login(username.trim(), password);
    } catch (e) {
      setError(
        e.response?.data?.detail ||
          'Login failed. Check your credentials and that the server is running.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <LinearGradient
          colors={[colors.primary, colors.primaryDarker]}
          style={styles.logo}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <Ionicons name="earth" size={40} color={colors.white} />
        </LinearGradient>

        <Text style={styles.title}>Wanderlust</Text>
        <Text style={styles.subtitle}>Discover your next journey</Text>

        <View style={styles.form}>
          <ErrorNotice message={error} />

          <Field
            label="Username"
            icon="person-outline"
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            autoCorrect={false}
            placeholder="your username"
            returnKeyType="next"
          />
          <Field
            label="Password"
            icon="lock-closed-outline"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="••••••••"
            returnKeyType="go"
            onSubmitEditing={onSubmit}
          />

          <PrimaryButton title="Log in" onPress={onSubmit} loading={loading} />

          <Pressable
            style={({ pressed }) => [styles.linkWrap, pressed && { opacity: 0.6 }]}
            onPress={() => navigation.navigate('Register')}
          >
            <Text style={styles.linkMuted}>New here? </Text>
            <Text style={styles.link}>Create an account</Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  logo: {
    width: 76,
    height: 76,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.base,
  },
  title: { ...type.display, fontSize: 32, color: colors.text },
  subtitle: { ...type.body, color: colors.textMuted, marginTop: 4, marginBottom: spacing.xl },
  form: { width: '100%', maxWidth: 380 },
  linkWrap: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.lg,
    paddingVertical: spacing.sm,
  },
  linkMuted: { ...type.bodySm, color: colors.textMuted },
  link: { ...type.bodySm, color: colors.primary, fontWeight: '700' },
});
