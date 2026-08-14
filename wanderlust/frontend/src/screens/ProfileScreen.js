import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../context/AuthContext';
import { AuthAPI } from '../api/services';
import DestinationCard from '../components/DestinationCard';
import {
  Card,
  DestinationCardSkeleton,
  EmptyState,
  Field,
  PrimaryButton,
} from '../components/ui';
import { colors, radius, spacing, type } from '../theme/theme';
import { API_BASE_URL } from '../config';

export default function ProfileScreen({ navigation }) {
  const { user, logout, setUser, refreshUser } = useAuth();
  const insets = useSafeAreaInsets();

  const [email, setEmail] = useState(user?.email || '');
  const [homeCountry, setHomeCountry] = useState(user?.home_country || '');
  const [bio, setBio] = useState(user?.bio || '');
  const [prefs, setPrefs] = useState(user?.travel_preferences || '');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [favorites, setFavorites] = useState([]);
  const [loadingFavs, setLoadingFavs] = useState(true);

  // The backend returns saved destinations directly, so this no longer
  // downloads the whole catalogue to filter it on the phone.
  const loadFavorites = useCallback(async () => {
    try {
      const res = await AuthAPI.favorites();
      setFavorites(res.data);
    } catch (e) {
      setFavorites([]);
    } finally {
      setLoadingFavs(false);
    }
  }, []);

  // Refresh on focus so a heart tapped on another tab shows up here.
  useFocusEffect(
    useCallback(() => {
      loadFavorites();
    }, [loadFavorites])
  );

  useEffect(() => {
    setEmail(user?.email || '');
    setHomeCountry(user?.home_country || '');
    setBio(user?.bio || '');
    setPrefs(user?.travel_preferences || '');
  }, [user]);

  const onSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const res = await AuthAPI.updateMe({
        email,
        home_country: homeCountry,
        bio,
        travel_preferences: prefs,
      });
      setUser(res.data);
      setSaved(true);
    } catch (e) {
      const data = e.response?.data;
      const message = data
        ? Object.entries(data)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : v}`)
            .join('\n')
        : 'Please check your connection and try again.';
      Alert.alert('Could not save', message);
    } finally {
      setSaving(false);
    }
  };

  const removeFavorite = async (destinationId) => {
    setFavorites((prev) => prev.filter((d) => d.id !== destinationId));
    try {
      await AuthAPI.toggleFavorite(destinationId);
      await refreshUser();
    } catch (e) {
      loadFavorites();
    }
  };

  const confirmLogout = () => {
    Alert.alert('Log out', 'Are you sure you want to log out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Log out', style: 'destructive', onPress: () => logout() },
    ]);
  };

  const initial = (user?.username || '?').charAt(0).toUpperCase();

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xxl }} showsVerticalScrollIndicator={false}>
        <View style={[styles.header, { paddingTop: insets.top + spacing.lg }]}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initial}</Text>
          </View>
          <Text style={styles.username}>{user?.username}</Text>
          {user?.email ? <Text style={styles.email}>{user.email}</Text> : null}

          <View style={styles.counters}>
            <Counter value={user?.favorite_count ?? favorites.length} label="Saved" />
            <View style={styles.counterDivider} />
            <Counter value={user?.review_count ?? 0} label="Reviews" />
          </View>
        </View>

        <View style={styles.section}>
          <Card>
            <View style={styles.cardHeader}>
              <Ionicons name="person-circle-outline" size={19} color={colors.primary} />
              <Text style={styles.cardTitle}>Travel profile</Text>
            </View>
            <Text style={styles.hint}>
              Your travel preferences are what the recommender uses when you ask for
              suggestions without typing a query, and what the "Use my profile"
              switch blends into the ranking.
            </Text>

            <Field
              label="Email"
              icon="mail-outline"
              value={email}
              onChangeText={(t) => {
                setEmail(t);
                setSaved(false);
              }}
              autoCapitalize="none"
              keyboardType="email-address"
              placeholder="you@example.com"
            />
            <Field
              label="Home country"
              icon="flag-outline"
              value={homeCountry}
              onChangeText={(t) => {
                setHomeCountry(t);
                setSaved(false);
              }}
              placeholder="e.g. Pakistan"
            />
            <Field
              label="Short bio"
              value={bio}
              onChangeText={(t) => {
                setBio(t);
                setSaved(false);
              }}
              placeholder="A sentence about you"
              multiline
            />
            <Field
              label="Travel preferences"
              value={prefs}
              onChangeText={(t) => {
                setPrefs(t);
                setSaved(false);
              }}
              placeholder="e.g. quiet beaches, local food, hiking, history"
              hint="Write it the way you would describe a trip out loud."
              multiline
              style={{ minHeight: 72, textAlignVertical: 'top' }}
            />

            <PrimaryButton
              title={saved ? 'Saved' : 'Save changes'}
              icon={saved ? 'checkmark-circle' : undefined}
              onPress={onSave}
              loading={saving}
            />
          </Card>
        </View>

        <View style={styles.section}>
          <View style={styles.savedHeader}>
            <Ionicons name="heart" size={18} color={colors.danger} />
            <Text style={styles.cardTitle}>
              Saved places{favorites.length ? ` (${favorites.length})` : ''}
            </Text>
          </View>

          {loadingFavs ? (
            <DestinationCardSkeleton />
          ) : favorites.length === 0 ? (
            <Card>
              <EmptyState
                icon="bookmark-outline"
                message="You haven't saved any destinations yet. Tap the heart on a place to add it here."
              />
            </Card>
          ) : (
            favorites.map((item) => (
              <DestinationCard
                key={item.id}
                item={item}
                onToggleFavorite={() => removeFavorite(item.id)}
                onPress={() =>
                  navigation.navigate('DestinationDetail', { id: item.id, name: item.name })
                }
              />
            ))
          )}
        </View>

        <View style={styles.section}>
          <PrimaryButton title="Log out" onPress={confirmLogout} variant="outline" icon="log-out-outline" />
          <Text style={styles.server}>Connected to {API_BASE_URL}</Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Counter({ value, label }) {
  return (
    <View style={styles.counter}>
      <Text style={styles.counterValue}>{value}</Text>
      <Text style={styles.counterLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  header: {
    backgroundColor: colors.surface,
    alignItems: 'center',
    paddingBottom: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  avatar: {
    width: 82,
    height: 82,
    borderRadius: radius.pill,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  avatarText: { ...type.display, fontSize: 34, color: colors.white },
  username: { ...type.title, color: colors.text },
  email: { ...type.bodySm, color: colors.textMuted, marginTop: 2 },

  counters: { flexDirection: 'row', alignItems: 'center', marginTop: spacing.base },
  counter: { alignItems: 'center', paddingHorizontal: spacing.lg },
  counterDivider: { width: 1, height: 28, backgroundColor: colors.border },
  counterValue: { ...type.heading, fontSize: 20, color: colors.text },
  counterLabel: { ...type.micro, color: colors.textMuted, marginTop: 2 },

  section: { paddingHorizontal: spacing.base, marginTop: spacing.base },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 6 },
  savedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    marginBottom: spacing.md,
    marginTop: spacing.sm,
  },
  cardTitle: { ...type.heading, color: colors.text },
  hint: { ...type.caption, color: colors.textMuted, marginBottom: spacing.base, lineHeight: 17 },
  server: { ...type.caption, fontSize: 10.5, color: colors.textFaint, textAlign: 'center', marginTop: spacing.base },
});
