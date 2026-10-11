import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Search, Clock3 } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="tl-page">
      <nav className="tl-nav">
        <div className="tl-container flex min-h-16 flex-wrap items-center justify-between gap-4 py-3">
          <Link to="/dashboard" className="tl-brand" aria-label="TruthLens dashboard">
            Truth<span className="tl-brand-accent">Lens</span>
          </Link>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <Link
                to="/analyze"
                className="tl-button tl-button-primary"
              >
                <Search className="w-4 h-4" />
                New Analysis
              </Link>
              <Link
                to="/history"
                className="tl-button tl-button-secondary"
              >
                <Clock3 className="w-4 h-4" />
                History
              </Link>
              <div className="hidden border-l border-[var(--border)] pl-3 text-sm leading-tight text-[var(--text-muted)] sm:block">
                <p className="font-medium text-[var(--foreground)]">{user?.name}</p>
                <p className="mt-1 text-xs">{user?.email}</p>
              </div>
              <button
                onClick={logout}
                className="tl-button tl-button-secondary"
              >
                Logout
              </button>
          </div>
        </div>
      </nav>

      <main className="tl-container py-12 sm:py-16">
        <header className="max-w-2xl">
          <p className="tl-eyebrow mb-3">Fact-checking workspace</p>
          <h1 className="tl-heading">A clearer view of what the evidence says.</h1>
          <p className="mt-4 max-w-xl text-base text-[var(--text-muted)]">
            Review a new claim or return to an earlier analysis, with sources and limitations kept in view.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link
              to="/analyze"
              className="tl-button tl-button-primary"
            >
              <Search className="h-4 w-4" />
              Start an analysis
            </Link>
            <Link to="/history" className="tl-button tl-button-secondary">
              <Clock3 className="h-4 w-4" />
              Browse history
            </Link>
          </div>
        </header>
      </main>
    </div>
  );
};
