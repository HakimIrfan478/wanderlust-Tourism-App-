import React, { useCallback, useEffect, useState } from 'react';
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { EvaluationAPI, RecommendAPI } from '../api/services';
import DestinationCard from '../components/DestinationCard';
import {
  Badge,
  Card,
  ComparisonBar,
  EmptyState,
  ErrorNotice,
  InfoNotice,
  Loading,
  PrimaryButton,
  SegmentedControl,
  Stat,
} from '../components/ui';
import { colors, elevation, modelFor, radius, spacing, type } from '../theme/theme';
import { MODELS } from '../config';

const COMPARE = 'compare';
const BENCHMARK = 'benchmark';

const SUGGESTED = [
  'somewhere peaceful by the sea to switch off completely',
  'I want to learn to cook the local dishes',
  'photograph rare animals in their natural habitat',
  'skiing and snowboarding holiday',
];

/**
 * The research half of the app.
 *
 * "Head to head" runs one query through both recommenders side by side;
 * "Benchmark" shows the offline evaluation over the labelled query set.
 * Together they put the project's research question inside the product rather
 * than only in the report.
 */
export default function ResearchScreen({ navigation, route }) {
  const [tab, setTab] = useState(COMPARE);
  const insets = useSafeAreaInsets();

  return (
    <View style={styles.screen}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={styles.headerTop}>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>Model Lab</Text>
            <Text style={styles.headerSub}>
              Does the transformer actually beat the keyword baseline?
            </Text>
          </View>
          <View style={styles.headerIcon}>
            <Ionicons name="flask" size={19} color={colors.primary} />
          </View>
        </View>

        <SegmentedControl
          style={{ marginTop: spacing.base }}
          value={tab}
          onChange={setTab}
          options={[
            { value: COMPARE, label: 'Head to head', icon: 'git-compare' },
            { value: BENCHMARK, label: 'Benchmark', icon: 'stats-chart' },
          ]}
        />
      </View>

      {tab === COMPARE ? (
        <CompareTab navigation={navigation} initialQuery={route.params?.query} />
      ) : (
        <BenchmarkTab />
      )}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Head to head                                                                */
/* -------------------------------------------------------------------------- */
function CompareTab({ navigation, initialQuery }) {
  const [query, setQuery] = useState(initialQuery || SUGGESTED[0]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const run = useCallback(async (text) => {
    const q = (text || '').trim();
    if (!q) {
      setError('Type a query to compare the two models on.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await RecommendAPI.compare(q, { topK: 5 });
      setData(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not run the comparison. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialQuery) run(initialQuery);
  }, [initialQuery, run]);

  const runs = data?.runs || {};
  const semantic = runs[MODELS.SEMANTIC];
  const tfidf = runs[MODELS.TFIDF];
  const agreement = data?.agreement;
  const hasAgreement = agreement && Object.keys(agreement).length > 0;

  return (
    <ScrollView
      contentContainerStyle={styles.body}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Describe a trip…"
        placeholderTextColor={colors.textFaint}
        style={styles.input}
        multiline
      />

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={{ marginBottom: spacing.base }}
        contentContainerStyle={{ paddingRight: spacing.base }}
      >
        {SUGGESTED.map((s) => (
          <Pressable
            key={s}
            style={({ pressed }) => [styles.chip, pressed && { opacity: 0.7 }]}
            onPress={() => {
              setQuery(s);
              run(s);
            }}
          >
            <Text style={styles.chipText}>{s}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <ErrorNotice message={error} />
      <PrimaryButton title="Run both models" icon="play" onPress={() => run(query)} loading={loading} />

      {!data && !loading ? (
        <EmptyState
          icon="git-compare-outline"
          title="Nothing compared yet"
          message="Run a query to see where the two recommenders agree and where they part company."
        />
      ) : null}

      {hasAgreement ? (
        <Card style={styles.agreementCard} level="md">
          <View style={styles.agreementTop}>
            <View style={styles.agreementDial}>
              <Text style={styles.agreementNumber}>{agreement.overlap_count}</Text>
              <Text style={styles.agreementDenominator}>of {agreement.top_k}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.agreementLabel}>destinations in common</Text>
              <Text style={styles.agreementText}>{data.interpretation}</Text>
            </View>
          </View>
          <View style={styles.statRow}>
            <Stat label="Jaccard" value={agreement.jaccard?.toFixed(2) ?? '—'} />
            <View style={styles.statDivider} />
            <Stat
              label="Kendall τ"
              value={agreement.kendall_tau != null ? agreement.kendall_tau.toFixed(2) : '—'}
            />
            <View style={styles.statDivider} />
            <Stat
              label="Same #1"
              value={agreement.same_top_1 ? 'Yes' : 'No'}
              tint={agreement.same_top_1 ? colors.success : colors.accent}
            />
          </View>
        </Card>
      ) : null}

      {data && !semantic ? (
        <InfoNotice message="Only the TF-IDF baseline is available on this server, so there is nothing to compare against." />
      ) : null}

      {semantic && tfidf ? (
        <>
          <View style={styles.columns}>
            <RankingColumn run={semantic} agreement={agreement} navigation={navigation} />
            <RankingColumn run={tfidf} agreement={agreement} navigation={navigation} />
          </View>
          <Text style={styles.legend}>
            A coloured edge marks a destination that appears in only one of the two
            rankings. Percentages are each model's own similarity score and are not
            comparable across columns — the ordering is what matters.
          </Text>
        </>
      ) : null}
    </ScrollView>
  );
}

function RankingColumn({ run, agreement, navigation }) {
  const meta = modelFor(run.model);
  const uniqueIds = new Set(
    run.model === MODELS.SEMANTIC ? agreement?.only_semantic || [] : agreement?.only_tfidf || []
  );

  return (
    <View style={styles.column}>
      <View style={[styles.columnHeader, { backgroundColor: meta.soft, borderColor: meta.border }]}>
        <Ionicons name={meta.icon} size={13} color={meta.color} />
        <Text style={[styles.columnTitle, { color: meta.color }]}>{meta.label}</Text>
      </View>
      <Text style={styles.columnTiming}>{run.elapsed_ms} ms</Text>

      {run.results.map((item) => (
        <View
          key={item.id}
          style={uniqueIds.has(item.id) ? [styles.unique, { borderLeftColor: meta.color }] : null}
        >
          <DestinationCard
            compact
            item={item}
            rank={item.rank}
            score={item.match_score}
            model={run.model}
            explanation={item.explanation}
            onPress={() =>
              navigation.navigate('DestinationDetail', { id: item.id, name: item.name })
            }
          />
        </View>
      ))}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Benchmark                                                                   */
/* -------------------------------------------------------------------------- */
function BenchmarkTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const res = await EvaluationAPI.results();
      setData(res.data);
    } catch (e) {
      setError(
        e.response?.data?.detail ||
          'No evaluation results yet. Run `python manage.py run_evaluation` on the backend.'
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <Loading text="Loading evaluation results…" />;

  if (error && !data) {
    return (
      <ScrollView contentContainerStyle={styles.body}>
        <ErrorNotice
          message={error}
          onRetry={() => {
            setLoading(true);
            load();
          }}
        />
      </ScrollView>
    );
  }

  const semantic = data.models?.[MODELS.SEMANTIC];
  const tfidf = data.models?.[MODELS.TFIDF];
  const headline = data.headline;
  const comparison = data.comparison || {};

  const series = (metric) =>
    [
      semantic && {
        key: MODELS.SEMANTIC,
        value: semantic.overall[metric],
        color: modelFor(MODELS.SEMANTIC).color,
      },
      tfidf && {
        key: MODELS.TFIDF,
        value: tfidf.overall[metric],
        color: modelFor(MODELS.TFIDF).color,
      },
    ].filter(Boolean);

  const positive = (headline?.difference ?? 0) > 0;

  return (
    <ScrollView
      contentContainerStyle={styles.body}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          tintColor={colors.primary}
          onRefresh={() => {
            setRefreshing(true);
            load();
          }}
        />
      }
    >
      <View style={styles.legendRow}>
        {[MODELS.SEMANTIC, MODELS.TFIDF]
          .filter((id) => data.models?.[id])
          .map((id) => {
            const m = modelFor(id);
            return <Badge key={id} label={m.label} color={m.color} soft={m.soft} icon={m.icon} />;
          })}
      </View>

      {headline ? (
        <Card style={styles.verdictCard} level="md">
          <Text style={styles.verdictLabel}>RESULT</Text>
          <Text style={styles.verdictText}>{headline.verdict}</Text>
          <View style={styles.statRow}>
            <Stat
              label="Semantic nDCG@5"
              value={headline.semantic?.toFixed(3)}
              tint={modelFor(MODELS.SEMANTIC).color}
            />
            <View style={styles.statDivider} />
            <Stat
              label="TF-IDF nDCG@5"
              value={headline.tfidf?.toFixed(3)}
              tint={modelFor(MODELS.TFIDF).color}
            />
            <View style={styles.statDivider} />
            <Stat
              label="Difference"
              value={`${positive ? '+' : ''}${headline.difference?.toFixed(3)}`}
              tint={Math.abs(headline.difference) < 0.01 ? colors.textMuted : colors.text}
            />
          </View>
        </Card>
      ) : null}

      <Section title="Ranking quality" subtitle="Normalised discounted cumulative gain at each cut-off.">
        {['ndcg@1', 'ndcg@3', 'ndcg@5', 'ndcg@10'].map((m) => (
          <ComparisonBar key={m} label={m.toUpperCase()} series={series(m)} />
        ))}
      </Section>

      <Section title="Precision">
        {['precision@1', 'precision@3', 'precision@5', 'precision@10'].map((m) => (
          <ComparisonBar key={m} label={m} series={series(m)} />
        ))}
      </Section>

      <Section title="Other measures">
        <ComparisonBar label="MRR" series={series('mrr')} />
        <ComparisonBar label="MAP" series={series('map')} />
      </Section>

      {semantic && tfidf ? (
        <Section
          title="Where the difference actually is"
          subtitle="nDCG@5 split by query type. Lexical queries reuse catalogue vocabulary; paraphrase queries express the same intent in different words."
          highlight
        >
          {Object.keys(semantic.by_query_type || {}).map((t) => (
            <ComparisonBar
              key={t}
              label={`${t}  (n=${semantic.by_query_type[t].query_count})`}
              series={[
                {
                  key: MODELS.SEMANTIC,
                  value: semantic.by_query_type[t]['ndcg@5'],
                  color: modelFor(MODELS.SEMANTIC).color,
                },
                {
                  key: MODELS.TFIDF,
                  value: tfidf.by_query_type[t]['ndcg@5'],
                  color: modelFor(MODELS.TFIDF).color,
                },
              ]}
            />
          ))}
        </Section>
      ) : null}

      {comparison.latency ? (
        <Section title="Cost of the transformer">
          <ComparisonBar
            label="Mean query latency"
            max={Math.max(comparison.latency.semantic_mean_ms, comparison.latency.tfidf_mean_ms)}
            formatValue={(v) => `${v.toFixed(1)}ms`}
            series={[
              {
                key: MODELS.SEMANTIC,
                value: comparison.latency.semantic_mean_ms,
                color: modelFor(MODELS.SEMANTIC).color,
              },
              {
                key: MODELS.TFIDF,
                value: comparison.latency.tfidf_mean_ms,
                color: modelFor(MODELS.TFIDF).color,
              },
            ]}
          />
          <Text style={styles.note}>
            The semantic model costs {comparison.latency.semantic_slowdown_x}× the
            latency of the baseline per query.
          </Text>
        </Section>
      ) : null}

      {data.meta ? (
        <Card style={styles.metaCard} level="none">
          <Text style={styles.metaTitle}>How this was measured</Text>
          <MetaRow label="Catalogue" value={`${data.meta.catalogue_size} destinations`} />
          <MetaRow
            label="Queries"
            value={`${data.meta.query_set?.query_count} labelled · ${data.meta.query_set?.relevance_judgements} judgements`}
          />
          <MetaRow label="Embedding model" value={data.meta.embedding_model} />
          <MetaRow
            label="Generated"
            value={(data.meta.generated_at || '').slice(0, 16).replace('T', ' ')}
          />
          <Text style={styles.caveat}>
            Relevance grades are single-annotator judgements by the project author,
            so these figures are indicative rather than conclusive.
          </Text>
        </Card>
      ) : null}
    </ScrollView>
  );
}

function Section({ title, subtitle, children, highlight }) {
  return (
    <Card style={[styles.section, highlight && styles.sectionHighlight]}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle ? <Text style={styles.sectionSub}>{subtitle}</Text> : null}
      {children}
    </Card>
  );
}

function MetaRow({ label, value }) {
  if (!value) return null;
  return (
    <View style={styles.metaRow}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text style={styles.metaValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  body: { padding: spacing.base, paddingBottom: spacing.xxl },

  header: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.base,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTop: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md },
  headerTitle: { ...type.display, fontSize: 27, color: colors.text },
  headerSub: { ...type.bodySm, color: colors.textMuted, marginTop: 2 },
  headerIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },

  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.base,
    minHeight: 76,
    textAlignVertical: 'top',
    ...type.bodySm,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.base,
    ...elevation.sm,
  },
  chip: {
    backgroundColor: colors.primarySoft,
    paddingHorizontal: spacing.base,
    paddingVertical: 9,
    borderRadius: radius.pill,
    marginRight: spacing.sm,
    maxWidth: 250,
  },
  chipText: { ...type.caption, color: colors.primaryDark, fontWeight: '600' },

  agreementCard: { marginTop: spacing.lg },
  agreementTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.base },
  agreementDial: {
    width: 64,
    height: 64,
    borderRadius: radius.pill,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  agreementNumber: { ...type.title, fontSize: 26, color: colors.primary },
  agreementDenominator: { ...type.caption, fontSize: 10, color: colors.primaryDark, marginTop: -3 },
  agreementLabel: { ...type.subheading, color: colors.text },
  agreementText: { ...type.caption, color: colors.textMuted, marginTop: 4, lineHeight: 17 },

  statRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.base,
    paddingTop: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  statDivider: { width: 1, height: 28, backgroundColor: colors.border },

  columns: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.lg },
  column: { flex: 1 },
  columnHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    paddingVertical: 8,
    borderRadius: radius.xs,
    borderWidth: 1,
  },
  columnTitle: { ...type.micro, fontSize: 11 },
  columnTiming: {
    ...type.caption,
    fontSize: 10,
    color: colors.textFaint,
    textAlign: 'center',
    marginVertical: 6,
  },
  unique: { borderLeftWidth: 3, borderRadius: radius.xs, paddingLeft: 4 },
  legend: {
    ...type.caption,
    fontSize: 11,
    color: colors.textFaint,
    lineHeight: 16,
    marginTop: spacing.base,
  },
  legendRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.base },

  verdictCard: { borderColor: colors.primaryBorder, borderWidth: 1.5, marginBottom: spacing.base },
  verdictLabel: { ...type.micro, color: colors.primary, marginBottom: 6 },
  verdictText: { ...type.body, color: colors.text, fontWeight: '600' },

  section: { marginBottom: spacing.base },
  sectionHighlight: { borderColor: colors.primaryBorder, backgroundColor: colors.primarySoft },
  sectionTitle: { ...type.subheading, color: colors.text, marginBottom: 4 },
  sectionSub: { ...type.caption, color: colors.textMuted, lineHeight: 17, marginBottom: spacing.base },
  note: { ...type.caption, color: colors.textMuted, lineHeight: 17 },

  metaCard: { backgroundColor: colors.surfaceAlt, borderColor: 'transparent' },
  metaTitle: { ...type.label, color: colors.textSecondary, marginBottom: spacing.md },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
    gap: spacing.base,
  },
  metaLabel: { ...type.caption, color: colors.textMuted },
  metaValue: { ...type.caption, color: colors.text, flexShrink: 1, textAlign: 'right', fontWeight: '600' },
  caveat: {
    ...type.caption,
    fontSize: 10.5,
    color: colors.textMuted,
    marginTop: spacing.md,
    lineHeight: 15,
    fontStyle: 'italic',
  },
});
