import React from 'react';

export default function App() {
  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 600 }}>SafeSpace Threat Detection</h1>
        <p style={{ color: 'var(--text-secondary)', margin: '0.25rem 0 0' }}>Local-First CCTV Surveillance & AI Verification</p>
      </header>
      <main>
        <div style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '1.25rem' }}>System Dashboard</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Contracts and service boundaries configured. Ready for active feeds.</p>
        </div>
      </main>
    </div>
  );
}
