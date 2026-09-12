export default function Nav() {
  return (
    <nav
      className="sticky top-0 z-20"
      style={{
        height: 62,
        background: "var(--surface-card)",
        borderBottom: "1px solid var(--border-hairline)",
      }}
    >
      <div
        className="mx-auto flex h-full items-center justify-between px-6 lg:px-16"
        style={{ maxWidth: "var(--page-max-width)" }}
      >
        <div className="flex items-baseline gap-2.5">
          <span
            style={{
              fontSize: 18,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              color: "var(--text-heading)",
            }}
          >
            Trackside
          </span>
          <span className="mono" style={{ fontSize: 10, color: "var(--text-label)" }}>
            v1.0
          </span>
        </div>

        <div className="flex items-center gap-2.5">
          <a href="#method" className="btn-pill hidden sm:inline-block">
            Method
          </a>
          <a
            href="https://github.com/direenvy/trackside"
            target="_blank"
            rel="noreferrer"
            className="btn-secondary"
            style={{ padding: "8px 16px" }}
          >
            Source and data
          </a>
        </div>
      </div>
    </nav>
  );
}
