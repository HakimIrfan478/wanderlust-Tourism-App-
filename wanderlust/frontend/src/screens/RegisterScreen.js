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
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../context/AuthContext';
import { ErrorNotice, Field, InfoNotice, PrimaryButton } from '../components/ui';
import { colors, spacing, type } from '../theme/theme';

export default function RegisterScreen({ navigation }) {
  const { register } = useAuth();
  const insets = useSafeAreaInsets();
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    home_country: '',
    travel_preferences: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (key) => (val) => setForm((f) => ({ ...f, [key]: val }));

  const onSubmit = async () => {
    if (!form.username || !form.password) {
      setError('Username and password are required.');
      return;
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await register(form);
    } catch (e) {
      const data = e.response?.data;
      setError(
        data
          ? Object.entries(data)
              .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : v}`)
              .join('\n')
          : 'Registration failed.'
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
      <ScrollView
        contentContainerStyle={[styles.container, { paddingTop: insets.top + spacing.lg }]}
        keyboardShouldPersistTaps="handled"
      >
        <Pressable
          onPress={() => navigation.goBack()}
          hitSlop={10}
          style={({ pressed }) => [styles.back, pressed && { opacity: 0.6 }]}
        >
          <Ionicons name="chevron-back" size={22} color={colors.textSecondary} />
        </Pressable>

        <Text style={styles.title}>Create account</Text>
        <Text style={styles.subtitle}>
          Tell us what you love — the recommender uses it to suggest destinations.
        </Text>

        <View style={styles.form}>
          <ErrorNotice message={error} />

          <Field
            label="Username *"
            icon="person-outline"
            value={form.username}
            onChangeText={set('username')}
            autoCapitalize="none"
            autoCorrect={false}
            placeholder="janedoe"
          />
          <Field
            label="Email"
            icon="mail-outline"
            value={form.email}
            onChangeText={set('email')}
            keyboardType="email-address"
            autoCapitalize="none"
            placeholder="jane@email.com"
          />
          <Field
            label="Password *"
            icon="lock-closed-outline"
            value={form.password}
            onChangeText={set('password')}
            secureTextEntry
            placeholder="At least 8 characters"
            hint="Avoid common passwords — the server checks."
          />
          <Field
            label="Home country"
            icon="flag-outline"
            value={form.home_country}
            onChangeText={set('home_country')}
            placeholder="Pakistan"
          />
          <Field
            label="Travel preferences"
            value={form.travel_preferences}
            onChangeText={set('travel_preferences')}
            placeholder="e.g. quiet beaches, local food, hiking, history"
            multiline
            style={{ minHeight: 76, textAlignVertical: 'top' }}
          />

          <InfoNotice
            tone="info"
            icon="sparkles"
            message="Your preferences power the recommender when you ask for suggestions without typing a query."
          />

          <PrimaryButton title="Create account" onPress={onSubmit} loading={loading} />

          <Pressable
            style={({ pressed }) => [styles.linkWrap, pressed && { opacity: 0.6 }]}
            onPress={() => navigation.goBack()}
          >
            <Text style={styles.linkMuted}>Already have an account? </Text>
            <Text style={styles.link}>Log in</Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, padding: spacing.lg, paddingBottom: spacing.xxl },
  back: { alignSelf: 'flex-start', marginBottom: spacing.base },
  title: { ...type.display, color: colors.text },
  subtitle: { ...type.bodySm, color: colors.textMuted, marginTop: 6, marginBottom: spacing.xl },
  form: { width: '100%', maxWidth: 420, alignSelf: 'center' },
  linkWrap: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.lg,
    paddingVertical: spacing.sm,
  },
  linkMuted: { ...type.bodySm, color: colors.textMuted },
  link: { ...type.bodySm, color: colors.primary, fontWeight: '700' },
});
