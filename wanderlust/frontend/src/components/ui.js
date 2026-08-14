import React, { useEffect, useRef } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, elevation, radius, spacing, type } from '../theme/theme';

/* -------------------------------------------------------------------------- */
/* Buttons                                                                     */
/* -------------------------------------------------------------------------- */
export function PrimaryButton({
  title,
  onPress,
  loading,
  disabled,
  variant = 'solid',
  icon,
  size = 'md',
}) {
  const isOutline = variant === 'outline';
  const isGhost = variant === 'ghost';
  const small = size === 'sm';
  const tint = isOutline || isGhost ? colors.primary : colors.white;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      style={({ pressed }) => [
        styles.btn,
        small && styles.btnSm,
        isOutline && styles.btnOutline,
        isGhost && styles.btnGhost,
        !isOutline && !isGhost && [styles.btnSolid, elevation.sm],
        (disabled || loading) && styles.btnDisabled,
        // A slight scale-down reads as a physical press; opacity alone feels flat.
        pressed && !disabled && !loading && styles.btnPressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={tint} size="small" />
      ) : (
        <View style={styles.btnInner}>
          {icon ? <Ionicons name={icon} size={small ? 15 : 17} color={tint} /> : null}
          <Text style={[styles.btnText, small && { fontSize: 14 }, { color: tint }]}>
            {title}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

/* -------------------------------------------------------------------------- */
/* Inputs                                                                      */
/* -------------------------------------------------------------------------- */
export function Field({ label, hint, error, icon, style, ...props }) {
  return (
    <View style={{ marginBottom: spacing.base }}>
      {label ? <Text style={styles.fieldLabel}>{label}</Text> : null}
      <View style={[styles.fieldWrap, error && styles.fieldWrapError]}>
        {icon ? (
          <Ionicons name={icon} size={17} color={colors.textFaint} style={styles.fieldIcon} />
        ) : null}
        <TextInput
          placeholderTextColor={colors.textFaint}
          style={[styles.input, icon && { paddingLeft: 0 }, style]}
          {...props}
        />
      </View>
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
      {hint && !error ? <Text style={styles.fieldHint}>{hint}</Text> : null}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Surfaces                                                                    */
/* -------------------------------------------------------------------------- */
export function Card({ children, style, level = 'sm', padded = true }) {
  return (
    <View style={[styles.card, elevation[level], padded && styles.cardPadded, style]}>
      {children}
    </View>
  );
}

export function SectionHeader({ title, subtitle, icon, action }) {
  return (
    <View style={styles.sectionHeader}>
      <View style={{ flex: 1 }}>
        <View style={styles.sectionTitleRow}>
          {icon ? <Ionicons name={icon} size={17} color={colors.primary} /> : null}
          <Text style={styles.sectionTitle}>{title}</Text>
        </View>
        {subtitle ? <Text style={styles.sectionSubtitle}>{subtitle}</Text> : null}
      </View>
      {action}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Loading                                                                     */
/* -------------------------------------------------------------------------- */
export function Loading({ text }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color={colors.primary} />
      {text ? <Text style={styles.loadingText}>{text}</Text> : null}
    </View>
  );
}

/**
 * A shimmering placeholder block.
 *
 * Skeletons beat spinners for lists: they show the shape of what is coming, so
 * the layout does not jump when data lands.
 */
export function Skeleton({ width = '100%', height = 14, style, radius: r = radius.xs }) {
  const shimmer = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(shimmer, {
          toValue: 1,
          duration: 850,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(shimmer, {
          toValue: 0,
          duration: 850,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [shimmer]);

  const opacity = shimmer.interpolate({ inputRange: [0, 1], outputRange: [0.45, 1] });

  return (
    <Animated.View
      style={[{ width, height, borderRadius: r, backgroundColor: colors.surfaceAlt, opacity }, style]}
    />
  );
}

export function DestinationCardSkeleton() {
  return (
    <View style={[styles.card, elevation.sm, { marginBottom: spacing.base, overflow: 'hidden' }]}>
      <Skeleton height={188} radius={0} />
      <View style={{ padding: spacing.base, gap: spacing.sm }}>
        <Skeleton width="62%" height={17} />
        <Skeleton width="40%" height={12} />
        <Skeleton width="90%" height={12} />
      </View>
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Indicators                                                                  */
/* -------------------------------------------------------------------------- */
export function StarRating({ value, size = 14, showValue = false }) {
  const rounded = Math.round(value || 0);
  return (
    <View style={styles.row} accessibilityLabel={`${value || 0} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Ionicons
          key={i}
          name={i <= rounded ? 'star' : 'star-outline'}
          size={size}
          color={i <= rounded ? colors.star : colors.borderStrong}
          style={{ marginRight: 1 }}
        />
      ))}
      {showValue && value != null ? (
        <Text style={styles.ratingValue}>{Number(value).toFixed(1)}</Text>
      ) : null}
    </View>
  );
}

export function Pill({ label, active, onPress, color, icon, count }) {
  const tint = color || colors.primary;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: !!active }}
      style={({ pressed }) => [
        styles.pill,
        active ? { backgroundColor: tint, borderColor: tint } : { borderColor: colors.border },
        pressed && { opacity: 0.75 },
      ]}
    >
      {icon ? (
        <Ionicons name={icon} size={13} color={active ? colors.white : tint} />
      ) : null}
      <Text style={[styles.pillText, active && { color: colors.white }]}>{label}</Text>
      {count != null ? (
        <Text style={[styles.pillCount, active && { color: colors.white, opacity: 0.85 }]}>
          {count}
        </Text>
      ) : null}
    </Pressable>
  );
}

export function Badge({ label, color, soft, icon, size = 'md' }) {
  const small = size === 'sm';
  return (
    <View
      style={[
        styles.badge,
        { backgroundColor: soft || colors.primarySoft },
        small && { paddingVertical: 3, paddingHorizontal: spacing.sm, gap: 3 },
      ]}
    >
      {icon ? (
        <Ionicons name={icon} size={small ? 10 : 12} color={color || colors.primaryDark} />
      ) : null}
      <Text
        style={[
          styles.badgeText,
          { color: color || colors.primaryDark },
          small && { fontSize: 10 },
        ]}
      >
        {label}
      </Text>
    </View>
  );
}

/**
 * Segmented control. Used for choosing a recommender and for switching between
 * the two Model Lab views.
 */
export function SegmentedControl({ options, value, onChange, style }) {
  return (
    <View style={[styles.segment, style]}>
      {options.map((option) => {
        const active = option.value === value;
        const tint = option.color || colors.primary;
        return (
          <Pressable
            key={option.value}
            onPress={() => onChange(option.value)}
            disabled={option.disabled}
            accessibilityRole="button"
            accessibilityState={{ selected: active, disabled: !!option.disabled }}
            style={[
              styles.segmentItem,
              active && [{ backgroundColor: tint }, elevation.sm],
              option.disabled && { opacity: 0.35 },
            ]}
          >
            {option.icon ? (
              <Ionicons
                name={option.icon}
                size={14}
                color={active ? colors.white : colors.textMuted}
              />
            ) : null}
            <Text numberOfLines={1} style={[styles.segmentText, active && { color: colors.white }]}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Data display                                                                */
/* -------------------------------------------------------------------------- */
export function Stat({ label, value, tint, align = 'center' }) {
  return (
    <View style={{ flex: 1, alignItems: align === 'center' ? 'center' : 'flex-start' }}>
      <Text style={[styles.statValue, tint && { color: tint }]}>{value}</Text>
      <Text style={[styles.statLabel, { textAlign: align }]}>{label}</Text>
    </View>
  );
}

/**
 * Horizontal bars comparing two series on a shared scale.
 *
 * Drawn with plain Views: the app needs exactly one chart shape, and a native
 * charting dependency would cost more than it returns.
 */
export function ComparisonBar({ label, series, max = 1, formatValue }) {
  const format = formatValue || ((v) => v.toFixed(3));
  const best = Math.max(...series.map((s) => s.value));

  return (
    <View style={styles.barRow}>
      <Text style={styles.barLabel}>{label}</Text>
      {series.map((item) => {
        const ratio = max > 0 ? Math.max(0, Math.min(item.value / max, 1)) : 0;
        const leading = item.value === best && series.length > 1;
        return (
          <View key={item.key} style={styles.barLine}>
            <View style={styles.barTrack}>
              <View
                style={[
                  styles.barFill,
                  {
                    // Always leave a sliver so a zero reads as "zero" rather
                    // than as a missing bar.
                    width: `${Math.max(ratio * 100, 1.5)}%`,
                    backgroundColor: item.color,
                    opacity: leading ? 1 : 0.62,
                  },
                ]}
              />
            </View>
            <Text style={[styles.barValue, { color: item.color }]}>{format(item.value)}</Text>
          </View>
        );
      })}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* States                                                                      */
/* -------------------------------------------------------------------------- */
export function EmptyState({ icon = 'search-outline', title, message, action }) {
  return (
    <View style={styles.emptyState}>
      <View style={styles.emptyIcon}>
        <Ionicons name={icon} size={26} color={colors.textFaint} />
      </View>
      {title ? <Text style={styles.emptyTitle}>{title}</Text> : null}
      {message ? <Text style={styles.emptyText}>{message}</Text> : null}
      {action ? <View style={{ marginTop: spacing.base }}>{action}</View> : null}
    </View>
  );
}

export function ErrorNotice({ message, onRetry }) {
  if (!message) return null;
  return (
    <View style={styles.errorBox}>
      <Ionicons name="alert-circle" size={18} color={colors.danger} />
      <Text style={styles.errorText}>{message}</Text>
      {onRetry ? (
        <Pressable onPress={onRetry} accessibilityRole="button" hitSlop={8}>
          <Text style={styles.retry}>Retry</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function InfoNotice({ message, tone = 'warning', icon = 'information-circle' }) {
  if (!message) return null;
  const palette = {
    warning: { bg: colors.warningSoft, fg: colors.warning },
    success: { bg: colors.successSoft, fg: colors.success },
    info: { bg: colors.primarySoft, fg: colors.primaryDark },
  }[tone];
  return (
    <View style={[styles.infoBox, { backgroundColor: palette.bg }]}>
      <Ionicons name={icon} size={15} color={palette.fg} />
      <Text style={[styles.infoText, { color: palette.fg }]}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center' },

  btn: {
    height: 52,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  btnSm: { height: 40, borderRadius: radius.sm, paddingHorizontal: spacing.base },
  btnSolid: { backgroundColor: colors.primary },
  btnOutline: { borderWidth: 1.5, borderColor: colors.primaryBorder, backgroundColor: colors.surface },
  btnGhost: { backgroundColor: 'transparent' },
  btnDisabled: { opacity: 0.45 },
  btnPressed: { transform: [{ scale: 0.985 }], opacity: 0.9 },
  btnInner: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  btnText: { ...type.subheading, fontSize: 15.5 },

  fieldLabel: { ...type.label, color: colors.textSecondary, marginBottom: 6 },
  fieldWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.base,
  },
  fieldWrapError: { borderColor: colors.danger },
  fieldIcon: { marginRight: spacing.sm },
  input: { flex: 1, ...type.body, color: colors.text, paddingVertical: 13 },
  fieldHint: { ...type.caption, color: colors.textFaint, marginTop: 5 },
  fieldError: { ...type.caption, color: colors.danger, marginTop: 5 },

  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardPadded: { padding: spacing.base },

  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    marginTop: spacing.lg,
    marginBottom: spacing.md,
    gap: spacing.md,
  },
  sectionTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  sectionTitle: { ...type.heading, color: colors.text },
  sectionSubtitle: { ...type.caption, color: colors.textMuted, marginTop: 3, lineHeight: 17 },

  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
  loadingText: { ...type.bodySm, color: colors.textMuted, marginTop: spacing.md },

  ratingValue: { ...type.caption, color: colors.textSecondary, marginLeft: 5, fontWeight: '700' },

  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: spacing.base,
    paddingVertical: 9,
    borderRadius: radius.pill,
    borderWidth: 1.2,
    marginRight: spacing.sm,
    backgroundColor: colors.surface,
  },
  pillText: { ...type.label, color: colors.textSecondary },
  pillCount: { ...type.caption, color: colors.textFaint, fontWeight: '700' },

  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 5,
    paddingHorizontal: spacing.md,
    paddingVertical: 5,
    borderRadius: radius.pill,
  },
  badgeText: { ...type.micro, letterSpacing: 0.3 },

  segment: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: 4,
  },
  segmentItem: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: radius.xs,
  },
  segmentText: { ...type.label, fontSize: 13, color: colors.textMuted },

  statValue: { ...type.heading, fontSize: 19, color: colors.text, fontVariant: ['tabular-nums'] },
  statLabel: { ...type.caption, fontSize: 11, color: colors.textMuted, marginTop: 2 },

  barRow: { marginBottom: spacing.base },
  barLabel: { ...type.caption, color: colors.textSecondary, fontWeight: '700', marginBottom: 7 },
  barLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginBottom: 6 },
  barTrack: {
    flex: 1,
    height: 10,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: radius.pill },
  barValue: { ...type.mono, width: 52, textAlign: 'right' },

  emptyState: { alignItems: 'center', paddingVertical: spacing.xl, paddingHorizontal: spacing.lg },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  emptyTitle: { ...type.subheading, color: colors.text, marginBottom: 5 },
  emptyText: { ...type.bodySm, color: colors.textMuted, textAlign: 'center', maxWidth: 280 },

  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.dangerSoft,
    borderRadius: radius.sm,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  errorText: { ...type.bodySm, color: colors.danger, flex: 1 },
  retry: { ...type.label, color: colors.danger, fontWeight: '800' },

  infoBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    borderRadius: radius.sm,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  infoText: { ...type.caption, flex: 1, lineHeight: 17 },
});
