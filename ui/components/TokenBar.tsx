interface Tokens {
  input: number;
  output: number;
  cacheRead: number;
  cacheCreation: number;
}

export function TokenBar({ t }: { t: Tokens }) {
  const total = t.input + t.output + t.cacheRead + t.cacheCreation;
  if (total === 0)
    return <div className="cf-token-bar" aria-label="no token data" />;

  const pct = (n: number) => (n / total) * 100;
  return (
    <div
      className="cf-token-bar"
      role="img"
      aria-label={`Tokens: ${total} total`}
    >
      <div
        className="cf-token-bar__seg"
        style={{
          width: `${pct(t.input)}%`,
          background: "var(--cf-color-bucket-input)",
        }}
        title={`input: ${t.input.toLocaleString()}`}
      />
      <div
        className="cf-token-bar__seg"
        style={{
          width: `${pct(t.cacheRead)}%`,
          background: "var(--cf-color-bucket-cache-read)",
        }}
        title={`cache_read: ${t.cacheRead.toLocaleString()}`}
      />
      <div
        className="cf-token-bar__seg"
        style={{
          width: `${pct(t.cacheCreation)}%`,
          background: "var(--cf-color-bucket-cache-write)",
        }}
        title={`cache_write: ${t.cacheCreation.toLocaleString()}`}
      />
      <div
        className="cf-token-bar__seg"
        style={{
          width: `${pct(t.output)}%`,
          background: "var(--cf-color-bucket-output)",
        }}
        title={`output: ${t.output.toLocaleString()}`}
      />
    </div>
  );
}

export function TokenLegend() {
  return (
    <div className="cf-legend" aria-label="token bucket legend">
      <span className="cf-legend__item">
        <span
          className="cf-legend__swatch"
          style={{ background: "var(--cf-color-bucket-input)" }}
        />
        input
      </span>
      <span className="cf-legend__item">
        <span
          className="cf-legend__swatch"
          style={{ background: "var(--cf-color-bucket-cache-read)" }}
        />
        cache_read
      </span>
      <span className="cf-legend__item">
        <span
          className="cf-legend__swatch"
          style={{ background: "var(--cf-color-bucket-cache-write)" }}
        />
        cache_write
      </span>
      <span className="cf-legend__item">
        <span
          className="cf-legend__swatch"
          style={{ background: "var(--cf-color-bucket-output)" }}
        />
        output
      </span>
    </div>
  );
}
