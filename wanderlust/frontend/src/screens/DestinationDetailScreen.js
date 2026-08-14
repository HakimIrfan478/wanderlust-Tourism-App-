import React, { useCallback, useEffect, useState } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { AuthAPI, DestinationAPI, IntegrationAPI } from '../api/services';
import { useAuth } from '../context/AuthContext';
import {
  Card,
  EmptyState,
  ErrorNotice,
  Loading,
  PrimaryButton,
  StarRating,
} from '../components/ui';
import { categoryMeta, colors, elevation, radius, spacing, type } from '../theme/theme';

const WEATHER_ICONS = {
  sunny: 'sunny',
  cloudy: 'cloud',
  rain: 'rainy',
  snow: 'snow',
  fog: 'cloudy',
  storm: 'thunderstorm',
};

export default function DestinationDetailScreen({ route, navigation }) {
  const { id } = route.params;
  const { user, refreshUser } = useAuth();
  const insets = useSafeAreaInsets();

  const [dest, setDest] = useState(null);
  const [weather, setWeather] = useState(null);
  const [country, setCountry] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [myRating, setMyRating] = useState(0);
  const [myComment, setMyComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [reviewError, setReviewError] = useState('');

  const loadDetail = useCallback(async () => {
    const res = await DestinationAPI.detail(id);
    setDest(res.data);
    return res.data;
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadDetail();
        // Weather and country facts arrive in one request; both are optional
        // decoration, so a failure here never blocks the page.
        const res = await IntegrationAPI.context(id);
        if (cancelled) return;
        setWeather(res.data.weather);
        setCountry(res.data.country);
      } catch (e) {
        if (!cancelled) setLoadError('Could not load this destination.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, loadDetail]);

  const submitReview = async () => {
    if (myRating === 0) {
      setReviewError('Please pick a star rating.');
      return;
    }
    setSubmitting(true);
    setReviewError('');
    try {
      await DestinationAPI.addReview(id, myRating, myComment);
      setMyRating(0);
      setMyComment('');
      await loadDetail();
    } catch (e) {
      const data = e.response?.data;
      setReviewError(
        (Array.isArray(data) ? data[0] : data?.detail) || 'Could not submit your review.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const toggleFavorite = async () => {
    if (!user) return;
    setDest((prev) => (prev ? { ...prev, is_favorite: !prev.is_favorite } : prev));
    try {
      await AuthAPI.toggleFavorite(id);
      await refreshUser();
    } catch (e) {
      setDest((prev) => (prev ? { ...prev, is_favorite: !prev.is_favorite } : prev));
    }
  };

  if (loading) return <Loading text="Loading destination…" />;
  if (!dest) {
    return (
      <View style={styles.center}>
        <ErrorNotice message={loadError || 'Destination not found.'} />
      </View>
    );
  }

  const meta = categoryMeta[dest.category] || {};
  const alreadyReviewed = dest.reviews?.some((r) => r.author_username === user?.username);

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} showsVerticalScrollIndicator={false}>
      <View style={styles.hero}>
        {dest.image_url ? (
          <Image source={{ uri: dest.image_url }} style={StyleSheet.absoluteFill} resizeMode="cover" />
        ) : (
          <View style={[StyleSheet.absoluteFill, styles.heroFallback, { backgroundColor: meta.color || colors.primary }]}>
            <Ionicons name={meta.icon || 'image-outline'} size={56} color={colors.white} />
          </View>
        )}
        <LinearGradient
          colors={['rgba(11,26,26,0.55)', 'transparent', 'rgba(11,26,26,0.75)']}
          locations={[0, 0.4, 1]}
          style={StyleSheet.absoluteFill}
          pointerEvents="none"
        />

        <View style={[styles.heroTop, { top: insets.top + spacing.sm }]}>
          <Pressable
            onPress={() => navigation.goBack()}
            style={({ pressed }) => [styles.circleBtn, pressed && { opacity: 0.7 }]}
            accessibilityRole="button"
            accessibilityLabel="Go back"
            hitSlop={8}
          >
            <Ionicons name="chevron-back" size={21} color={colors.white} />
          </Pressable>

          {user ? (
            <Pressable
              onPress={toggleFavorite}
              style={({ pressed }) => [styles.circleBtn, pressed && { opacity: 0.7 }]}
              accessibilityRole="button"
              accessibilityLabel={dest.is_favorite ? 'Remove from saved' : 'Save destination'}
              hitSlop={8}
            >
              <Ionicons
                name={dest.is_favorite ? 'heart' : 'heart-outline'}
                size={20}
                color={dest.is_favorite ? colors.danger : colors.white}
              />
            </Pressable>
          ) : null}
        </View>

        <View style={styles.heroText}>
          <View style={styles.categoryChip}>
            <Ionicons name={meta.icon || 'location-outline'} size={11} color={colors.white} />
            <Text style={styles.categoryText}>{meta.label || dest.category}</Text>
          </View>
          <Text style={styles.title}>{dest.name}</Text>
          <View style={styles.locationRow}>
            <Ionicons name="location" size={13} color="rgba(255,255,255,0.85)" />
            <Text style={styles.location}>
              {dest.city ? `${dest.city}, ` : ''}
              {dest.country}
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.content}>
        <Card style={styles.quickFacts} level="md">
          <View style={styles.factItem}>
            {dest.rating != null ? (
              <>
                <StarRating value={dest.rating} size={13} />
                <Text style={styles.factLabel}>
                  {dest.rating} · {dest.review_count} review{dest.review_count === 1 ? '' : 's'}
                </Text>
              </>
            ) : (
              <>
                <Ionicons name="star-outline" size={15} color={colors.textFaint} />
                <Text style={styles.factLabel}>No reviews</Text>
              </>
            )}
          </View>
          <View style={styles.factDivider} />
          <View style={styles.factItem}>
            <Text style={styles.factValue}>${dest.average_cost_per_day_usd}</Text>
            <Text style={styles.factLabel}>per day</Text>
          </View>
          {dest.best_season ? (
            <>
              <View style={styles.factDivider} />
              <View style={[styles.factItem, { flex: 1.4 }]}>
                <Ionicons name="calendar-outline" size={15} color={colors.primary} />
                <Text style={styles.factLabel} numberOfLines={2}>
                  {dest.best_season}
                </Text>
              </View>
            </>
          ) : null}
        </Card>

        <Text style={styles.body}>{dest.description}</Text>

        {dest.tags?.length > 0 && (
          <View style={styles.tagWrap}>
            {dest.tags.map((t) => (
              <View key={t} style={styles.tag}>
                <Text style={styles.tagText}>{t}</Text>
              </View>
            ))}
          </View>
        )}

        {/* ---- LIVE WEATHER (Open-Meteo) ---- */}
        <SectionTitle icon="partly-sunny" text="Current weather" />
        {weather?.available ? (
          <Card level="sm">
            <View style={styles.weatherNow}>
              <Ionicons
                name={WEATHER_ICONS[weather.current.icon] || 'partly-sunny'}
                size={42}
                color={colors.primary}
              />
              <Text style={styles.temp}>{Math.round(weather.current.temperature_c)}°</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.condition}>{weather.current.condition}</Text>
                <Text style={styles.muted}>
                  Humidity {weather.current.humidity_pct}% · Wind{' '}
                  {Math.round(weather.current.wind_speed_kmh)} km/h
                </Text>
              </View>
            </View>
            <View style={styles.forecastRow}>
              {weather.forecast.slice(0, 5).map((day) => (
                <View key={day.date} style={styles.forecastDay}>
                  <Text style={styles.forecastDate}>
                    {new Date(day.date).toLocaleDateString(undefined, { weekday: 'short' })}
                  </Text>
                  <Ionicons
                    name={WEATHER_ICONS[day.icon] || 'partly-sunny'}
                    size={17}
                    color={colors.textMuted}
                    style={{ marginVertical: 5 }}
                  />
                  <Text style={styles.forecastTemp}>{Math.round(day.temp_max_c)}°</Text>
                  <Text style={styles.forecastLow}>{Math.round(day.temp_min_c)}°</Text>
                </View>
              ))}
            </View>
            <Text style={styles.attribution}>Live data from Open-Meteo</Text>
          </Card>
        ) : (
          <Text style={styles.muted}>
            {weather?.detail || 'Live weather is unavailable right now.'}
          </Text>
        )}

        {/* ---- COUNTRY FACTS ---- */}
        <SectionTitle icon="flag" text="Country info" />
        {country?.available ? (
          <Card level="sm">
            <View style={styles.countryHeader}>
              {country.flag_png ? (
                <Image source={{ uri: country.flag_png }} style={styles.flag} />
              ) : null}
              <View style={{ flex: 1 }}>
                <Text style={styles.countryName}>{country.official_name || country.name}</Text>
                <Text style={styles.muted}>
                  {country.region}
                  {country.subregion ? ` · ${country.subregion}` : ''}
                </Text>
              </View>
            </View>
            <View style={styles.infoGrid}>
              <InfoCell icon="business-outline" label="Capital" value={country.capital} />
              <InfoCell
                icon="people-outline"
                label="Population"
                value={country.population?.toLocaleString()}
              />
              <InfoCell
                icon="cash-outline"
                label="Currency"
                value={country.currencies?.map((c) => `${c.name} (${c.symbol || c.code})`).join(', ')}
              />
              <InfoCell
                icon="chatbubbles-outline"
                label="Languages"
                value={country.languages?.join(', ')}
              />
              <InfoCell icon="time-outline" label="Timezone" value={country.timezones?.[0]} />
            </View>
            <Text style={styles.attribution}>Data from {country.source}</Text>
          </Card>
        ) : (
          <Text style={styles.muted}>
            {country?.detail || 'Country information is unavailable right now.'}
          </Text>
        )}

        {/* ---- REVIEWS ---- */}
        <SectionTitle icon="chatbox-ellipses" text={`Reviews (${dest.reviews?.length || 0})`} />

        {user && !alreadyReviewed ? (
          <Card level="sm" style={{ marginBottom: spacing.md }}>
            <Text style={styles.reviewPrompt}>Leave a review</Text>
            <View style={styles.starPicker}>
              {[1, 2, 3, 4, 5].map((i) => (
                <Pressable
                  key={i}
                  onPress={() => setMyRating(i)}
                  hitSlop={4}
                  accessibilityRole="button"
                  accessibilityLabel={`Rate ${i} out of 5`}
                >
                  <Ionicons
                    name={i <= myRating ? 'star' : 'star-outline'}
                    size={32}
                    color={i <= myRating ? colors.star : colors.borderStrong}
                  />
                </Pressable>
              ))}
            </View>
            <TextInput
              value={myComment}
              onChangeText={setMyComment}
              placeholder="Share your experience…"
              placeholderTextColor={colors.textFaint}
              multiline
              style={styles.reviewInput}
            />
            <ErrorNotice message={reviewError} />
            <PrimaryButton title="Submit review" onPress={submitReview} loading={submitting} />
          </Card>
        ) : null}

        {user && alreadyReviewed ? (
          <Text style={styles.muted}>You have already reviewed this destination.</Text>
        ) : null}
        {!user ? <Text style={styles.muted}>Sign in to leave a review.</Text> : null}

        {dest.reviews?.map((r) => (
          <Card key={r.id} level="none" style={styles.reviewItem}>
            <View style={styles.reviewHeader}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>
                  {(r.author_username || '?').charAt(0).toUpperCase()}
                </Text>
              </View>
              <Text style={styles.reviewAuthor}>{r.author_username}</Text>
              <StarRating value={r.rating} size={12} />
            </View>
            {r.comment ? <Text style={styles.reviewComment}>{r.comment}</Text> : null}
          </Card>
        ))}
        {(!dest.reviews || dest.reviews.length === 0) && (
          <EmptyState icon="chatbubble-outline" message="No reviews yet. Be the first." />
        )}

        {dest.image_attribution ? (
          <Text style={styles.credit}>{dest.image_attribution}</Text>
        ) : null}
      </View>
    </ScrollView>
  );
}

function SectionTitle({ icon, text }) {
  return (
    <View style={styles.sectionTitleRow}>
      <Ionicons name={icon} size={16} color={colors.primary} />
      <Text style={styles.sectionTitle}>{text}</Text>
    </View>
  );
}

function InfoCell({ icon, label, value }) {
  if (!value) return null;
  return (
    <View style={styles.infoCell}>
      <Ionicons name={icon} size={13} color={colors.textFaint} />
      <View style={{ flex: 1 }}>
        <Text style={styles.infoLabel}>{label}</Text>
        <Text style={styles.infoValue}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { height: 300, width: '100%', backgroundColor: colors.surfaceAlt },
  heroFallback: { alignItems: 'center', justifyContent: 'center' },
  heroTop: {
    position: 'absolute',
    left: spacing.base,
    right: spacing.base,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  circleBtn: {
    width: 38,
    height: 38,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(11,26,26,0.42)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroText: { position: 'absolute', left: spacing.base, right: spacing.base, bottom: spacing.xl },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    backgroundColor: 'rgba(11,26,26,0.5)',
    paddingHorizontal: spacing.md,
    paddingVertical: 5,
    borderRadius: radius.pill,
    marginBottom: spacing.sm,
  },
  categoryText: { ...type.micro, color: colors.white, fontSize: 10 },
  title: { ...type.display, color: colors.white },
  locationRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 3 },
  location: { ...type.bodySm, color: 'rgba(255,255,255,0.9)' },

  content: {
    padding: spacing.base,
    marginTop: -spacing.lg,
    backgroundColor: colors.bg,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingBottom: spacing.xxl,
  },

  quickFacts: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.base },
  factItem: { flex: 1, alignItems: 'center', gap: 4 },
  factDivider: { width: 1, height: 32, backgroundColor: colors.border },
  factValue: { ...type.subheading, color: colors.primary, fontSize: 17 },
  factLabel: { ...type.caption, fontSize: 11, color: colors.textMuted, textAlign: 'center' },

  body: { ...type.body, color: colors.textSecondary, marginTop: spacing.sm },
  tagWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: spacing.base },
  tag: {
    backgroundColor: colors.primarySoft,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
  },
  tagText: { ...type.caption, color: colors.primaryDark, fontWeight: '600' },

  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  sectionTitle: { ...type.heading, color: colors.text },

  weatherNow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  temp: { ...type.display, fontSize: 38, color: colors.primary },
  condition: { ...type.subheading, color: colors.text },
  forecastRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.base,
    paddingTop: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  forecastDay: { alignItems: 'center', flex: 1 },
  forecastDate: { ...type.caption, fontSize: 11, color: colors.textMuted, fontWeight: '700' },
  forecastTemp: { ...type.label, color: colors.text },
  forecastLow: { ...type.caption, fontSize: 11, color: colors.textFaint },
  attribution: {
    ...type.caption,
    fontSize: 10,
    color: colors.textFaint,
    marginTop: spacing.md,
    fontStyle: 'italic',
  },

  countryHeader: { flexDirection: 'row', gap: spacing.md, alignItems: 'center' },
  flag: { width: 56, height: 38, borderRadius: radius.xs, backgroundColor: colors.surfaceAlt },
  countryName: { ...type.subheading, color: colors.text },
  infoGrid: {
    marginTop: spacing.base,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.md,
  },
  infoCell: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  infoLabel: { ...type.caption, fontSize: 10.5, color: colors.textFaint, textTransform: 'uppercase' },
  infoValue: { ...type.bodySm, color: colors.text },

  reviewPrompt: { ...type.label, color: colors.textSecondary, marginBottom: spacing.md },
  starPicker: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.base },
  reviewInput: {
    backgroundColor: colors.bg,
    borderRadius: radius.sm,
    padding: spacing.base,
    minHeight: 80,
    textAlignVertical: 'top',
    ...type.bodySm,
    color: colors.text,
    marginBottom: spacing.base,
    borderWidth: 1,
    borderColor: colors.border,
  },
  reviewItem: { marginBottom: spacing.sm, backgroundColor: colors.surface },
  reviewHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: 6 },
  avatar: {
    width: 26,
    height: 26,
    borderRadius: radius.pill,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { ...type.micro, color: colors.primaryDark, fontSize: 11 },
  reviewAuthor: { ...type.label, color: colors.text, flex: 1 },
  reviewComment: { ...type.bodySm, color: colors.textSecondary },

  credit: {
    ...type.caption,
    fontSize: 10,
    color: colors.textFaint,
    marginTop: spacing.lg,
    textAlign: 'center',
    lineHeight: 15,
  },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
  muted: { ...type.bodySm, color: colors.textMuted },
});
