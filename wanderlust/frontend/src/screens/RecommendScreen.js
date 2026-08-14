import React, { useCallback, useEffect, useState } from 'react';
import {
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { AuthAPI, RecommendAPI } from '../api/services';
import { useAuth } from '../context/AuthContext';
import DestinationCard from '../components/DestinationCard';
import {
  Badge,
  DestinationCardSkeleton,
  EmptyState,
  ErrorNotice,
  InfoNotice,
  PrimaryButton,
  SegmentedControl,
} from '../components/ui';
import { colors, elevation, modelFor, radius, spacing, type } from '../theme/theme';
import { MODELS } from '../config';

const EXAMPLES = [
  { text: 'Quiet beaches with great seafood and no big crowds', icon: 'sunny-outline' },
  { text: 'Somewhere peaceful by the sea to switch off completely', icon: 'moon-outline' },
  { text: 'Ancient ruins and museums with amazing local food', icon: 'hourglass-outline' },
  { text: 'Photograph rare animals in their natural habitat', icon: 'camera-outline' },
  { text: 'Somewhere very cheap for a long backpacking trip', icon: 'wallet-outline' },
  { text: 'Extreme adventure sports in the mountains', icon: 'trail-sign-outline' },
];

export default function RecommendScreen({ navigation }) {
  const { user, refreshUser } = useAuth();
  const insets = useSafeAreaInsets();

  const [query, setQuery] = useState('');
  const [model, setModel] = useState(MODELS.SEMANTIC);
  const [personalize, setPersonalize] = useState(false);
  const [available, setAvailable] = useState(null);
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Ask the backend which models it can run, so the selector never offers one
  // this deployment cannot serve.
  useEffect(() => {
    let cancelled = false;
    RecommendAPI.models()
      .then((res) => {
        if (cancelled) return;
        setAvailable(res.data.models);
        const semantic = res.data.models.find((m) => m.id === MODELS.SEMANTIC);
        if (semantic && !semantic.available) setModel(MODELS.TFIDF);
      })
      .catch(() => {
        if (!cancelled) setAvailable([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const isAvailable = (id) => {
    if (!available) return true;
    return available.find((m) => m.id === id)?.available ?? false;
  };

  const run = useCallback(
    async (text, overrideModel) => {
      const chosen = overrideModel || model;
      const q = (text ?? query).trim();
      if (!q) {
        setError('Describe the kind of trip you want first.');
        return;
      }
      if (text) setQuery(text);
      setLoading(true);
      setError('');
      try {
        const res = await RecommendAPI.get(q, {
          model: chosen,
          topK: 8,
          personalize: personalize && !!user,
        });
        setResponse(res.data);
      } catch (e) {
        setError(
          e.response?.data?.detail || 'Could not get recommendations. Is the backend running?'
        );
      } finally {
        setLoading(false);
      }
    },
    [model, personalize, query, user]
  );

  // Re-run on model switch so the difference is one tap away, not a retype.
  const onModelChange = (next) => {
    setModel(next);
    if (response && query.trim()) run(query, next);
  };

  const toggleFavorite = async (destinationId) => {
    try {
      await AuthAPI.toggleFavorite(destinationId);
      await refreshUser();
      setResponse((prev) =>
        prev
          ? {
              ...prev,
              results: prev.results.map((r) =>
                r.id === destinationId ? { ...r, is_favorite: !r.is_favorite } : r
              ),
            }
          : prev
      );
    } catch (e) {
      /* a failed save is not worth interrupting the results for */
    }
  };

  const activeModel = response ? modelFor(response.model) : null;

  return (
    <View style={styles.screen}>
      <FlatList
        data={loading ? [] : response?.results || []}
        keyExtractor={(item) => String(item.id)}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          <View>
            <View style={[styles.hero, { paddingTop: insets.top + spacing.base }]}>
              <View style={styles.heroIcon}>
                <Ionicons name="sparkles" size={22} color={colors.primary} />
              </View>
              <Text style={styles.title}>Trip Finder</Text>
              <Text style={styles.subtitle}>
                Describe your ideal trip in your own words, then choose which
                recommender answers it.
              </Text>
            </View>

            <View style={styles.composer}>
              <TextInput
                value={query}
                onChangeText={setQuery}
                placeholder="e.g. peaceful beaches, local food, light hiking…"
                placeholderTextColor={colors.textFaint}
                style={styles.input}
                multiline
              />
              {query.length > 0 ? (
                <Pressable onPress={() => setQuery('')} hitSlop={10} style={styles.clear}>
                  <Ionicons name="close-circle" size={18} color={colors.textFaint} />
                </Pressable>
              ) : null}
            </View>

            <Text style={styles.sectionLabel}>Recommender</Text>
            <SegmentedControl
              value={model}
              onChange={onModelChange}
              options={[MODELS.SEMANTIC, MODELS.TFIDF].map((id) => {
                const m = modelFor(id);
                return {
                  value: id,
                  label: m.label,
                  icon: m.icon,
                  color: m.color,
                  disabled: !isAvailable(id),
                };
              })}
            />
            <Text style={styles.modelBlurb}>{modelFor(model).blurb}</Text>

            {available && !isAvailable(MODELS.SEMANTIC) ? (
              <InfoNotice message="The semantic model is not available on this server, so only the TF-IDF baseline can run." />
            ) : null}

            {user ? (
              <View style={styles.personalizeRow}>
                <Ionicons name="person-circle-outline" size={20} color={colors.primary} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.personalizeLabel}>Use my profile</Text>
                  <Text style={styles.personalizeHint}>
                    Nudges results toward your saved places and stated preferences.
                  </Text>
                </View>
                <Switch
                  value={personalize}
                  onValueChange={setPersonalize}
                  trackColor={{ true: colors.primary, false: colors.borderStrong }}
                  thumbColor={colors.white}
                />
              </View>
            ) : null}

            <Text style={styles.sectionLabel}>Try an example</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={{ marginBottom: spacing.base }}
              contentContainerStyle={{ paddingRight: spacing.base }}
            >
              {EXAMPLES.map((example) => (
                <Pressable
                  key={example.text}
                  style={({ pressed }) => [styles.chip, pressed && { opacity: 0.7 }]}
                  onPress={() => run(example.text)}
                >
                  <Ionicons name={example.icon} size={13} color={colors.primaryDark} />
                  <Text style={styles.chipText}>{example.text}</Text>
                </Pressable>
              ))}
            </ScrollView>

            <ErrorNotice message={error} onRetry={() => run()} />

            <PrimaryButton
              title="Find my destinations"
              icon="compass"
              onPress={() => run()}
              loading={loading}
            />

            <Pressable
              style={({ pressed }) => [styles.compareLink, pressed && { opacity: 0.6 }]}
              onPress={() => navigation.navigate('Research', { query: query.trim() || undefined })}
            >
              <Ionicons name="git-compare" size={15} color={colors.primary} />
              <Text style={styles.compareLinkText}>Compare both models on this query</Text>
              <Ionicons name="chevron-forward" size={14} color={colors.primary} />
            </Pressable>

            {response && !loading ? (
              <View style={styles.resultHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.resultTitle}>Top matches</Text>
                  <Text style={styles.resultMeta}>
                    {response.count} of {response.candidate_count} · {response.elapsed_ms}ms
                  </Text>
                </View>
                <Badge
                  label={activeModel.longLabel}
                  color={activeModel.color}
                  soft={activeModel.soft}
                  icon={activeModel.icon}
                />
              </View>
            ) : null}

            {response?.fallback && !loading ? (
              <InfoNotice message={response.note} />
            ) : null}
            {response?.query_from_profile && !loading ? (
              <InfoNotice
                tone="info"
                icon="person-circle"
                message="Using the travel preferences saved on your profile."
              />
            ) : null}

            {loading ? (
              <View style={{ marginTop: spacing.lg }}>
                {[0, 1].map((i) => (
                  <DestinationCardSkeleton key={i} />
                ))}
              </View>
            ) : null}
          </View>
        }
        renderItem={({ item }) => (
          <DestinationCard
            item={item}
            score={item.match_score}
            model={response?.model}
            explanation={item.explanation}
            onToggleFavorite={user ? () => toggleFavorite(item.id) : undefined}
            onPress={() =>
              navigation.navigate('DestinationDetail', { id: item.id, name: item.name })
            }
          />
        )}
        ListEmptyComponent={
          response && !loading ? (
            <EmptyState
              icon="telescope-outline"
              title="No matches found"
              message="Try describing the trip differently, or switch models."
            />
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  list: { paddingHorizontal: spacing.base, paddingBottom: spacing.xxl },

  hero: { alignItems: 'center', paddingBottom: spacing.lg },
  heroIcon: {
    width: 48,
    height: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  title: { ...type.title, color: colors.text },
  subtitle: {
    ...type.bodySm,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: 6,
    maxWidth: 300,
  },

  composer: { position: 'relative', marginBottom: spacing.lg },
  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.base,
    paddingRight: spacing.xl,
    minHeight: 96,
    textAlignVertical: 'top',
    ...type.body,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    ...elevation.sm,
  },
  clear: { position: 'absolute', top: spacing.md, right: spacing.md },

  sectionLabel: {
    ...type.micro,
    color: colors.textMuted,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
  },
  modelBlurb: {
    ...type.caption,
    color: colors.textMuted,
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
    textAlign: 'center',
  },

  personalizeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.lg,
  },
  personalizeLabel: { ...type.subheading, color: colors.text },
  personalizeHint: { ...type.caption, color: colors.textMuted, marginTop: 2, lineHeight: 16 },

  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.primarySoft,
    paddingHorizontal: spacing.base,
    paddingVertical: 10,
    borderRadius: radius.pill,
    marginRight: spacing.sm,
    maxWidth: 260,
  },
  chipText: { ...type.caption, color: colors.primaryDark, fontWeight: '600', flexShrink: 1 },

  compareLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: spacing.base,
    paddingVertical: spacing.sm,
  },
  compareLinkText: { ...type.label, color: colors.primary },

  resultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xl,
    marginBottom: spacing.base,
    gap: spacing.md,
  },
  resultTitle: { ...type.heading, color: colors.text },
  resultMeta: { ...type.caption, color: colors.textMuted, marginTop: 2 },
});
