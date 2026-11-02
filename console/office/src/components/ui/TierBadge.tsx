export function TierBadge({ tier }: { tier?: 'A' | 'B' | 'C' }) {
  return <span className="tier-badge" data-testid="tier-badge" title="Capability tier; the session lists the actual runtime model">
    Tier {tier ?? '—'}
  </span>;
}
