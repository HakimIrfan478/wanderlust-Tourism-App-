import React, { useCallback, useEffect, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { AuthAPI, DestinationAPI } from '../api/services';
import { useAuth } from '../context/AuthContext';
import DestinationCard from '../components/DestinationCard';
import {
  DestinationCardSkeleton,
  EmptyState,
  ErrorNotice,
  Pill,
} from '../components/ui';
import { categoryMeta, colors, elevation, radius, spacing, type } from '../theme/theme';

const CATEGORIES = ['all', ...Object.keys(categoryMeta)];

const SORTS = [
  { value: 'name', label: 'A–Z', icon: 'text-outline' },
  { value: '-rating', label: 'Top rated', icon: 'star-outline' },
  { value: 'cost', label: 'Cheapest', icon: 'trending-down-outline' },
  { value: '-cost', label: 'Premium', icon: 'trending-up-outline' },
];

export default function HomeScreen({ navigation }) {
  const { user, refreshUser } = useAuth();
  const insets = useSafeAreaInsets();

  const [destinations, setDestinations] = useState([]);
  const [facets, setFacets] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState('name');
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const params = { sort };
      if (category !== 'all') params.category = category;
      if (search.trim()) params.search = search.trim();
      const res = await DestinationAPI.list(params);
      setDestinations(res.data.results || res.data);
    } catch (e) {
      setError('Could not load destinations. Is the backend running?');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [category, search, sort]);

  useEffect(() => {
    setLoading(true);
    // Debounce typing so a search does not fire a request per keystroke.
    const timer = setTimeout(load, search ? 350 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  useEffect(() => {
    DestinationAPI.facets()
      .then((res) => setFacets(res.data))
      .catch(() => setFacets(null));
  }, []);

  const countFor = (value) => {
    if (!facets) return null;
    if (value === 'all') return facets.total;
    return facets.categories.find((c) => c.value === value)?.count ?? 0;
  };

  const toggleFavorite = async (destinationId) => {
    if (!user) return;
    // Flip locally first so the heart responds instantly, then re-sync.
    const flip = (list) =>
      list.map((d) => (d.id === destinationId ? { ...d, is_favorite: !d.is_favorite } : d));
    setDestinations(flip);
    try {
      await AuthAPI.toggleFavorite(destinationId);
      await refreshUser();
    } catch (e) {
      setDestinations(flip);
    }
  };

  const greeting = user?.username ? `Hello, ${user.username}` : 'Explore';

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <Text style={styles.greeting}>{greeting}</Text>
        <Text style={styles.sub}>
          {facets ? `${facets.total} destinations across ${facets.countries.length} countries` : 'Find your next journey'}
        </Text>

        <View style={styles.searchBar}>
          <Ionicons name="search" size={17} color={colors.textFaint} />
          <TextInput
            value={search}
            onChangeText={setSearch}
            placeholder="Search places, countries or keywords"
            placeholderTextColor={colors.textFaint}
            style={styles.searchInput}
            returnKeyType="search"
          />
          {search.length > 0 && (
            <Ionicons
              name="close-circle"
              size={17}
              color={colors.textFaint}
              onPress={() => setSearch('')}
              suppressHighlighting
            />
          )}
        </View>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filterRow}
        contentContainerStyle={styles.filterContent}
      >
        {CATEGORIES.map((c) => (
          <Pill
            key={c}
            label={c === 'all' ? 'All' : categoryMeta[c].label}
            icon={c === 'all' ? 'apps-outline' : categoryMeta[c].icon}
            count={countFor(c)}
            active={category === c}
            color={c === 'all' ? colors.primary : categoryMeta[c].color}
            onPress={() => setCategory(c)}
          />
        ))}
      </ScrollView>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.sortRow}
        contentContainerStyle={styles.filterContent}
      >
        {SORTS.map((option) => (
          <Pill
            key={option.value}
            label={option.label}
            icon={option.icon}
            active={sort === option.value}
            color={colors.textSecondary}
            onPress={() => setSort(option.value)}
          />
        ))}
      </ScrollView>

      {loading ? (
        <ScrollView contentContainerStyle={styles.list} showsVerticalScrollIndicator={false}>
          {[0, 1, 2].map((i) => (
            <DestinationCardSkeleton key={i} />
          ))}
        </ScrollView>
      ) : error ? (
        <ScrollView contentContainerStyle={styles.list}>
          <ErrorNotice
            message={error}
            onRetry={() => {
              setLoading(true);
              load();
            }}
          />
        </ScrollView>
      ) : (
        <FlatList
          data={destinations}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              tintColor={colors.primary}
              colors={[colors.primary]}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
            />
          }
          renderItem={({ item }) => (
            <DestinationCard
              item={item}
              onToggleFavorite={user ? () => toggleFavorite(item.id) : undefined}
              onPress={() =>
                navigation.navigate('DestinationDetail', { id: item.id, name: item.name })
              }
            />
          )}
          ListEmptyComponent={
            <EmptyState
              icon="compass-outline"
              title="Nothing matches those filters"
              message="Try a different category, or clear the search box."
            />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  header: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.base,
  },
  greeting: { ...type.display, color: colors.text },
  sub: { ...type.bodySm, color: colors.textMuted, marginTop: 2, marginBottom: spacing.base },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bg,
    borderRadius: radius.md,
    paddingHorizontal: spacing.base,
    height: 48,
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  searchInput: { flex: 1, ...type.body, color: colors.text },

  filterRow: {
    flexGrow: 0,
    backgroundColor: colors.surface,
    borderBottomWidth: 0,
  },
  sortRow: {
    flexGrow: 0,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    ...elevation.sm,
  },
  filterContent: {
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.md,
    paddingTop: 2,
  },

  list: { padding: spacing.base, paddingBottom: spacing.xxl },
});
