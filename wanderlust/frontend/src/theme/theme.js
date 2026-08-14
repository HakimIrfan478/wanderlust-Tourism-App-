import { Platform } from 'react-native';

/**
 * Design tokens.
 *
 * Everything visual comes from here so the app reads as one system rather than
 * a set of screens that happen to share a colour. Screens should reach for a
 * token, never a raw hex value or a magic number.
 */

/* -------------------------------------------------------------------------- */
/* Colour                                                                      */
/* -------------------------------------------------------------------------- */
// A single teal ramp plus warm neutrals. Neutrals are very slightly green so
// they sit with the brand rather than against it — pure grey looks dirty next
// to teal.
const teal = {
  50: '#EEF6F6',
  100: '#D7EAEA',
  200: '#A9D3D3',
  300: '#6FB4B3',
  400: '#2F9391',
  500: '#0E7C7B',
  600: '#0A6463',
  700: '#084E4D',
  800: '#063A39',
};

const ink = {
  0: '#FFFFFF',
  50: '#F7F9F9',
  100: '#EFF3F3',
  200: '#E2E7E7',
  300: '#C9D2D2',
  400: '#94A3A3',
  500: '#667878',
  600: '#4A5A5A',
  700: '#2E3C3C',
  900: '#16211F',
};

export const colors = {
  primary: teal[500],
  primaryDark: teal[600],
  primaryDarker: teal[700],
  primarySoft: teal[50],
  primaryMuted: teal[100],
  primaryBorder: teal[200],

  accent: '#E08A3C',
  accentSoft: '#FDF1E4',

  bg: ink[50],
  surface: ink[0],
  surfaceAlt: ink[100],

  text: ink[900],
  textSecondary: ink[600],
  textMuted: ink[500],
  textFaint: ink[400],

  border: ink[200],
  borderStrong: ink[300],

  danger: '#C62B41',
  dangerSoft: '#FDEEF0',
  success: '#1E8A55',
  successSoft: '#E8F5EE',
  warning: '#9A6300',
  warningSoft: '#FFF6E5',

  star: '#E8A317',
  white: '#FFFFFF',
  black: '#000000',

  scrim: 'rgba(11,26,26,0.55)',
  scrimSoft: 'rgba(11,26,26,0.28)',
};

/* -------------------------------------------------------------------------- */
/* Spacing — a 4pt grid                                                        */
/* -------------------------------------------------------------------------- */
export const spacing = {
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const radius = {
  xs: 6,
  sm: 10,
  md: 14,
  lg: 20,
  xl: 28,
  pill: 999,
};

/* -------------------------------------------------------------------------- */
/* Typography                                                                  */
/* -------------------------------------------------------------------------- */
// Negative tracking on large text and positive on small caps is what makes
// type look considered rather than default.
export const type = {
  display: { fontSize: 30, fontWeight: '800', letterSpacing: -0.6, lineHeight: 36 },
  title: { fontSize: 23, fontWeight: '800', letterSpacing: -0.4, lineHeight: 29 },
  heading: { fontSize: 18, fontWeight: '700', letterSpacing: -0.2, lineHeight: 24 },
  subheading: { fontSize: 15, fontWeight: '700', letterSpacing: -0.1, lineHeight: 20 },
  body: { fontSize: 15, fontWeight: '400', lineHeight: 22 },
  bodySm: { fontSize: 13.5, fontWeight: '400', lineHeight: 19 },
  label: { fontSize: 13, fontWeight: '600', lineHeight: 17 },
  caption: { fontSize: 12, fontWeight: '500', lineHeight: 16 },
  micro: { fontSize: 10.5, fontWeight: '700', letterSpacing: 0.5, lineHeight: 14 },
  mono: {
    fontSize: 12,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
    letterSpacing: -0.2,
  },
};

/* -------------------------------------------------------------------------- */
/* Elevation                                                                   */
/* -------------------------------------------------------------------------- */
// iOS and Android express depth differently; these keep them consistent.
// Shadows are tinted toward the ink colour rather than pure black, which stops
// cards looking like they are floating over a grey smudge.
const shadow = (y, blur, opacity, elevation) =>
  Platform.select({
    ios: {
      shadowColor: '#0B1A1A',
      shadowOffset: { width: 0, height: y },
      shadowOpacity: opacity,
      shadowRadius: blur,
    },
    android: { elevation },
    default: {
      boxShadow: `0 ${y}px ${blur}px rgba(11,26,26,${opacity})`,
    },
  });

export const elevation = {
  none: {},
  sm: shadow(1, 3, 0.06, 1),
  md: shadow(3, 10, 0.09, 3),
  lg: shadow(8, 22, 0.13, 8),
};

/* -------------------------------------------------------------------------- */
/* Domain vocabulary                                                           */
/* -------------------------------------------------------------------------- */
export const categoryMeta = {
  beach: { label: 'Beach', icon: 'sunny-outline', color: '#0E8FA8' },
  mountain: { label: 'Mountain', icon: 'triangle-outline', color: '#5C6E80' },
  city: { label: 'City', icon: 'business-outline', color: '#7A5FBF' },
  historical: { label: 'Historical', icon: 'hourglass-outline', color: '#A9762F' },
  nature: { label: 'Nature', icon: 'leaf-outline', color: '#3E8E4E' },
  adventure: { label: 'Adventure', icon: 'trail-sign-outline', color: '#D2632C' },
  cultural: { label: 'Cultural', icon: 'color-palette-outline', color: '#BF5185' },
};

/**
 * Each recommender has one colour and one label used everywhere it is named —
 * chart, badge, results header, comparison column. Keeping it in one place
 * means those can never disagree about which model is which.
 */
export const modelMeta = {
  semantic: {
    label: 'Semantic',
    longLabel: 'Sentence-transformer',
    short: 'MiniLM',
    icon: 'sparkles',
    color: teal[500],
    soft: teal[50],
    border: teal[200],
    blurb: 'Matches the meaning of your description.',
  },
  tfidf: {
    label: 'TF-IDF',
    longLabel: 'TF-IDF keyword baseline',
    short: 'TF-IDF',
    icon: 'text',
    color: '#A85B22',
    soft: '#FBF0E6',
    border: '#EBD3BC',
    blurb: 'Matches the words you actually typed.',
  },
};

export const modelFor = (id) =>
  modelMeta[id] || {
    label: id || 'Unknown',
    longLabel: id || 'Unknown model',
    short: id || '?',
    icon: 'help-circle',
    color: colors.textMuted,
    soft: colors.surfaceAlt,
    border: colors.border,
    blurb: '',
  };
