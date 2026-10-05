// suggest-slugs.ts — catalog slug recovery for unknown /m/[slug] URLs.
// Pure: no next/* or JSON imports, so the model page and unit tests share one
// ranking (normalized suffix / substring, then edit distance).

export function normalizeSlug(value: string): string {
  return value.trim().toLowerCase().replace(/[._]+/g, "-").replace(/-+/g, "-");
}

/** True when `candidate` is strictly longer and ends with `-{query}`. */
export function hasExactSuffix(query: string, candidate: string): boolean {
  const q = normalizeSlug(query);
  const c = normalizeSlug(candidate);
  return Boolean(q) && Boolean(c) && c !== q && c.endsWith(`-${q}`);
}

export function exactSuffixMatches(query: string, candidates: readonly string[]): string[] {
  return candidates.filter((item) => hasExactSuffix(query, item));
}

function levenshtein(a: string, b: string): number {
  const cols = b.length + 1;
  const dp = new Array<number>(cols);
  for (let j = 0; j < cols; j++) dp[j] = j;
  for (let i = 1; i <= a.length; i++) {
    let prev = dp[0]!;
    dp[0] = i;
    for (let j = 1; j < cols; j++) {
      const cur = dp[j]!;
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[j] = Math.min(cur + 1, dp[j - 1]! + 1, prev + cost);
      prev = cur;
    }
  }
  return dp[b.length]!;
}

export function suggestSlugs(slug: string, candidates: readonly string[], n = 5): string[] {
  const query = normalizeSlug(slug);
  if (!query || n <= 0) return [];
  const ranked = candidates
    .map((item) => {
      const candidate = normalizeSlug(item);
      if (!candidate || candidate === query) return null;
      if (hasExactSuffix(query, candidate) || hasExactSuffix(candidate, query)) {
        return { item, tier: 0, cost: Math.abs(candidate.length - query.length) };
      }
      if (candidate.includes(query) || query.includes(candidate)) {
        return { item, tier: 1, cost: Math.abs(candidate.length - query.length) };
      }
      return { item, tier: 2, cost: levenshtein(query, candidate) };
    })
    .filter((row): row is { item: string; tier: number; cost: number } => row != null)
    .sort((a, b) => a.tier - b.tier || a.cost - b.cost || a.item.localeCompare(b.item));
  return ranked.slice(0, n).map((row) => row.item);
}

/**
 * Parse the memory size (`NNNgb`) and multi-GPU suffix (`-xN`) of a rig key.
 * A key without a `-xN` suffix counts as a single GPU.
 */
export function parseRigTokens(key: string): { memoryGb: number | null; gpuCount: number } {
  const normalized = normalizeSlug(key);
  const memoryMatch = normalized.match(/(\d+)gb/);
  const gpuMatch = normalized.match(/-x(\d+)$/);
  return {
    memoryGb: memoryMatch ? parseInt(memoryMatch[1], 10) : null,
    gpuCount: gpuMatch ? parseInt(gpuMatch[1], 10) : 1,
  };
}

function sharedDashTokens(query: string, candidate: string): number {
  const queryTokens = new Set(normalizeSlug(query).split("-").filter(Boolean));
  const candidateTokens = new Set(normalizeSlug(candidate).split("-").filter(Boolean));
  let shared = 0;
  for (const token of queryTokens) {
    if (candidateTokens.has(token)) shared += 1;
  }
  return shared;
}

/**
 * Rank rig keys closest to an unknown rig query.
 * Order: same memory AND same GPU count first, then same memory,
 * then shared dash-separated tokens (more is better), then edit distance.
 * Ties break stably by key.
 */
export function suggestRigs(query: string, keys: readonly string[], n = 5): string[] {
  const q = normalizeSlug(query);
  if (!q || n <= 0) return [];
  const queryTokens = parseRigTokens(q);
  const ranked = keys
    .map((item) => {
      const candidate = normalizeSlug(item);
      if (!candidate || candidate === q) return null;
      const candidateTokens = parseRigTokens(candidate);
      const sameMemory =
        queryTokens.memoryGb !== null && queryTokens.memoryGb === candidateTokens.memoryGb;
      const sameMemoryAndGpu = sameMemory && queryTokens.gpuCount === candidateTokens.gpuCount;
      const tier = sameMemoryAndGpu ? 0 : sameMemory ? 1 : 2;
      return {
        item,
        tier,
        shared: sharedDashTokens(q, candidate),
        cost: levenshtein(q, candidate),
      };
    })
    .filter(
      (row): row is { item: string; tier: number; shared: number; cost: number } => row != null,
    )
    .sort(
      (a, b) =>
        a.tier - b.tier || b.shared - a.shared || a.cost - b.cost || a.item.localeCompare(b.item),
    );
  return ranked.slice(0, n).map((row) => row.item);
}
