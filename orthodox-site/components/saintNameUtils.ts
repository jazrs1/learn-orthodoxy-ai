export function normalizeSaintKey(value: string): string {
  return (value || "")
    .replace(/\*\*/g, "")
    .replace(/^\d+[\.)]\s*/, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/^(?:(?:st\.?|saint|pope|patriarch|abba|anba)\s+)+/i, "")
    .replace(/\bkyrillos\b/g, "cyril")
    .replace(/\bkyrillos\b/g, "cyril")
    .replace(/\bcyrillus\b/g, "cyril");
}

export function buildSaintLookup(names: string[]): Set<string> {
  return new Set(names.map(normalizeSaintKey).filter(Boolean));
}

export function looksLikeSaintName(value: string): boolean {
  const normalized = normalizeSaintKey(value);
  if (!normalized) return false;

  const words = normalized.split(" ").filter(Boolean);
  if (words.length < 1) return false;

  return (
    /\b(theotokos|virgin mary)\b/i.test(value) ||
    /^(?:st\.?|saint)\s+/i.test(value) ||
    words.length >= 2
  );
}

export function isValidSaintName(value: string, saintLookup: Set<string>): boolean {
  const normalized = normalizeSaintKey(value);
  if (!normalized) return false;
  if (saintLookup.size === 0) return looksLikeSaintName(value);
  return saintLookup.has(normalized) || looksLikeSaintName(value);
}
