import React from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import {
  categoryMeta,
  colors,
  elevation,
  modelFor,
  radius,
  spacing,
  type,
} from '../theme/theme';
import { StarRating } from './ui';

const MEDIA_HEIGHT = 200;
const HEART_SIZE = 36;

/**
 * A destination in a list.
 *
 * The full card overlays the name and location on the photograph behind a
 * gradient scrim, which reads as a travel product rather than a database row.
 * The scrim is not decoration: text over an unknown photograph is unreadable
 * without it, and the photographs here come from Wikipedia so their brightness
 * is unpredictable.
 *
 * `compact` drops the image for the side-by-side comparison, where two columns
 * of photographs would leave no room for the text that matters there.
 */
export default function DestinationCard({
  item,
  onPress,
  onToggleFavorite,
  score,
  model,
  explanation,
  rank,
  compact = false,
}) {
  const meta = categoryMeta[item.category] || {};
  const modelStyle = model ? modelFor(model) : null;
  const percent = score != null ? Math.round(Math.max(0, Math.min(score, 1)) * 100) : null;

  if (compact) {
    return (
      <Pressable
        onPress={onPress}
        style={({ pressed }) => [styles.compactCard, pressed && styles.pressed]}
      >
        <View style={styles.compactHeader}>
          {rank != null ? (
            <View style={[styles.rankChip, { backgroundColor: modelStyle?.soft || colors.surfaceAlt }]}>
              <Text style={[styles.rankText, { color: modelStyle?.color || colors.textSecondary }]}>
                {rank}
              </Text>
            </View>
          ) : null}
          <View style={{ flex: 1 }}>
            <Text style={styles.compactName} numberOfLines={2}>
              {item.name}
            </Text>
            <Text style={styles.compactLocation} numberOfLines={1}>
              {item.country}
            </Text>
          </View>
        </View>

        {percent != null ? (
          <View style={styles.compactScoreRow}>
            <View style={styles.compactTrack}>
              <View
                style={[
                  styles.compactFill,
                  {
                    width: `${Math.max(percent, 2)}%`,
                    backgroundColor: modelStyle?.color || colors.primary,
                  },
                ]}
              />
            </View>
            <Text style={[styles.compactScore, { color: modelStyle?.color || colors.primary }]}>
              {percent}%
            </Text>
          </View>
        ) : null}

        {explanation ? (
          <Text style={styles.compactWhy} numberOfLines={3}>
            {explanation}
          </Text>
        ) : null}
      </Pressable>
    );
  }

  return (
    // The card body and the favourite control are siblings, not nested
    // pressables: a button inside a button is invalid HTML on web and makes
    // the hit targets ambiguous everywhere.
    <View style={[styles.card, elevation.md]}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={`${item.name}, ${item.country}`}
        style={({ pressed }) => [pressed && styles.pressed]}
      >
        <View style={styles.media}>
        {item.image_url ? (
          <Image source={{ uri: item.image_url }} style={styles.image} resizeMode="cover" />
        ) : (
          <View style={[styles.image, styles.imageFallback, { backgroundColor: meta.color || colors.primary }]}>
            <Ionicons name={meta.icon || 'image-outline'} size={38} color={colors.white} />
          </View>
        )}

        {/* Scrim: dark at the base, clear at the top, so the title stays legible
            over any photograph without dimming the whole image. */}
        <LinearGradient
          colors={['transparent', 'rgba(11,26,26,0.18)', 'rgba(11,26,26,0.82)']}
          locations={[0, 0.45, 1]}
          style={StyleSheet.absoluteFill}
          pointerEvents="none"
        />

        <View style={styles.topRow}>
          <View style={styles.categoryChip}>
            <Ionicons name={meta.icon || 'location-outline'} size={11} color={colors.white} />
            <Text style={styles.categoryText}>{meta.label || item.category}</Text>
          </View>

          {percent != null ? (
            <View style={[styles.scoreChip, { backgroundColor: modelStyle?.color || colors.accent }]}>
              <Ionicons name={modelStyle?.icon || 'sparkles'} size={11} color={colors.white} />
              <Text style={styles.scoreText}>{percent}%</Text>
            </View>
          ) : null}
        </View>

        <View style={styles.overlayText}>
          <Text style={styles.name} numberOfLines={1}>
            {item.name}
          </Text>
          <View style={styles.locationRow}>
            <Ionicons name="location" size={11} color="rgba(255,255,255,0.85)" />
            <Text style={styles.location} numberOfLines={1}>
              {item.city ? `${item.city}, ` : ''}
              {item.country}
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.body}>
        <Text style={styles.desc} numberOfLines={2}>
          {item.short_description}
        </Text>

        {explanation ? (
          <View style={[styles.why, { backgroundColor: modelStyle?.soft || colors.primarySoft }]}>
            <Ionicons name="bulb" size={12} color={modelStyle?.color || colors.primaryDark} />
            <Text style={[styles.whyText, { color: modelStyle?.color || colors.primaryDark }]}>
              {explanation}
            </Text>
          </View>
        ) : null}

        <View style={styles.footer}>
          {item.rating != null ? (
            <View style={styles.footerItem}>
              <StarRating value={item.rating} size={12} showValue />
              {item.review_count ? (
                <Text style={styles.reviewCount}>({item.review_count})</Text>
              ) : null}
            </View>
          ) : (
            <Text style={styles.noRating}>No reviews yet</Text>
          )}

          <View style={styles.costWrap}>
            <Text style={styles.cost}>${item.average_cost_per_day_usd}</Text>
            <Text style={styles.costUnit}>/day</Text>
          </View>
        </View>
        </View>
      </Pressable>

      {onToggleFavorite ? (
        <Pressable
          onPress={onToggleFavorite}
          hitSlop={12}
          style={({ pressed }) => [styles.heart, pressed && { opacity: 0.7 }]}
          accessibilityRole="button"
          accessibilityLabel={item.is_favorite ? 'Remove from saved' : 'Save destination'}
        >
          <Ionicons
            name={item.is_favorite ? 'heart' : 'heart-outline'}
            size={18}
            color={item.is_favorite ? colors.danger : colors.white}
          />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    marginBottom: spacing.base,
    overflow: 'hidden',
  },
  pressed: { transform: [{ scale: 0.99 }], opacity: 0.96 },

  media: { height: MEDIA_HEIGHT, width: '100%' },
  image: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.surfaceAlt },
  imageFallback: { alignItems: 'center', justifyContent: 'center' },

  topRow: {
    position: 'absolute',
    top: spacing.md,
    left: spacing.md,
    right: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(11,26,26,0.55)',
    paddingHorizontal: spacing.md,
    paddingVertical: 5,
    borderRadius: radius.pill,
  },
  categoryText: { ...type.micro, color: colors.white, fontSize: 10 },
  scoreChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: 5,
    borderRadius: radius.pill,
  },
  scoreText: { ...type.micro, color: colors.white, fontSize: 10.5 },

  heart: {
    position: 'absolute',
    right: spacing.md,
    // Positioned against the card rather than the image, because the control
    // is a sibling of the card body — see the comment on the render tree.
    top: MEDIA_HEIGHT - HEART_SIZE - spacing.md,
    width: HEART_SIZE,
    height: HEART_SIZE,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(11,26,26,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },

  overlayText: {
    position: 'absolute',
    left: spacing.base,
    right: 60,
    bottom: spacing.md,
  },
  name: { ...type.title, fontSize: 21, color: colors.white },
  locationRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 3 },
  location: { ...type.caption, color: 'rgba(255,255,255,0.88)' },

  body: { padding: spacing.base },
  desc: { ...type.bodySm, color: colors.textSecondary },

  why: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.xs,
  },
  whyText: { ...type.caption, fontSize: 11.5, fontWeight: '600', flex: 1, lineHeight: 16 },

  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  footerItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  reviewCount: { ...type.caption, color: colors.textFaint },
  noRating: { ...type.caption, color: colors.textFaint, fontStyle: 'italic' },
  costWrap: { flexDirection: 'row', alignItems: 'baseline' },
  cost: { ...type.subheading, color: colors.primary, fontSize: 16 },
  costUnit: { ...type.caption, color: colors.textMuted, marginLeft: 1 },

  compactCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  compactHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  rankChip: {
    width: 20,
    height: 20,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankText: { ...type.micro, fontSize: 10 },
  compactName: { ...type.label, fontSize: 13, color: colors.text, lineHeight: 17 },
  compactLocation: { ...type.caption, fontSize: 11, color: colors.textMuted, marginTop: 1 },
  compactScoreRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: spacing.sm },
  compactTrack: {
    flex: 1,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    overflow: 'hidden',
  },
  compactFill: { height: '100%', borderRadius: radius.pill },
  compactScore: { ...type.mono, fontSize: 10 },
  compactWhy: { ...type.caption, fontSize: 10.5, color: colors.textMuted, marginTop: 6, lineHeight: 14 },
});
