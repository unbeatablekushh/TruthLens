import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, AlertCircle, Clock3, Loader, Search } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface AnalysisHistoryItem {
  id: string;
  created_at: string;
  input_summary: string;
  status: string;
  verdict_summary?: string | null;
}

interface AnalysisHistoryResponse {
  analyses: AnalysisHistoryItem[];
  total_count: number;
  limit: number;
  offset: number;
}

const PAGE_SIZE = 20;

export const History = () => {
  const [history, setHistory] = useState<AnalysisHistoryResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;

    const loadHistory = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.get<AnalysisHistoryResponse>('/api/analysis', {
          params: { limit: PAGE_SIZE, offset },
        });
        if (isCurrent) setHistory(response.data);
      } catch (requestError: any) {
        if (isCurrent) {
          setError(requestError.response?.data?.detail || 'Unable to load analysis history.');
        }
      } finally {
        if (isCurrent) setIsLoading(false);
      }
    };

    void loadHistory();
    return () => {
      isCurrent = false;
    };
  }, [offset]);

  return (
    <main className="tl-page">
      <nav className="tl-nav">
        <div className="tl-container flex min-h-16 items-center justify-between gap-4 py-3">
          <Link to="/dashboard" className="tl-brand" aria-label="TruthLens dashboard">
            Truth<span className="tl-brand-accent">Lens</span>
          </Link>
          <Link to="/analyze" className="tl-button tl-button-primary">
            <Search className="h-4 w-4" />
            New analysis
          </Link>
        </div>
      </nav>
      <div className="tl-container max-w-4xl py-10 sm:py-14">
        <div className="mb-7 flex items-end justify-between gap-4">
          <div>
            <p className="tl-eyebrow mb-2">Your workspace</p>
            <h1 className="tl-heading">Analysis history</h1>
            <p className="mt-2 text-sm text-[var(--text-muted)]">Saved analyses, newest first.</p>
          </div>
          <Link
            to="/dashboard"
            className="tl-button tl-button-secondary shrink-0"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Dashboard</span>
          </Link>
        </div>

        {isLoading && (
          <div className="tl-panel flex items-center gap-3 p-5 text-[var(--text-muted)]" role="status">
            <Loader className="h-5 w-5 animate-spin text-[var(--teal)]" />
            Loading saved analyses...
          </div>
        )}

        {!isLoading && error && (
          <div role="alert" className="tl-alert-error flex items-start gap-3 p-4">
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {!isLoading && !error && history?.total_count === 0 && (
          <div className="tl-panel px-5 py-12 text-center sm:py-16">
            <Clock3 className="mx-auto mb-4 h-7 w-7 text-[var(--teal)]" />
            <h2 className="font-serif text-2xl font-semibold text-[var(--foreground)]">No saved analyses yet</h2>
            <p className="mx-auto mb-6 mt-2 max-w-sm text-sm text-[var(--text-muted)]">When you analyze a claim, its results and sources will be available here.</p>
            <Link to="/analyze" className="tl-button tl-button-primary">
              <Search className="h-4 w-4" />
              Start an analysis
            </Link>
          </div>
        )}

        {!isLoading && !error && history && history.total_count > 0 && (
          <>
            <p className="mb-3 text-sm text-[var(--text-muted)]">
              {history.total_count} saved {history.total_count === 1 ? 'analysis' : 'analyses'}
            </p>
            <div className="tl-panel divide-y divide-[var(--border)] overflow-hidden">
              {history.analyses.map((item) => (
                <Link
                  key={item.id}
                  to={`/analysis/${item.id}`}
                  className="block px-4 py-4 transition-colors hover:bg-[var(--teal-soft)] focus-visible:relative sm:px-5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="max-w-3xl font-medium leading-relaxed text-[var(--foreground)]">{item.input_summary || 'Analysis without a text summary'}</p>
                    <span className="rounded border border-[var(--border)] bg-[var(--surface-muted)] px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">{item.status}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-muted)]">
                    <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time>
                    {item.verdict_summary && <span className="text-[var(--teal-dark)]">Verdict summary: {item.verdict_summary}</span>}
                  </div>
                </Link>
              ))}
            </div>
            <div className="mt-4 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0 || isLoading}
                className="tl-button tl-button-secondary"
              >
                Previous
              </button>
              <span className="text-sm text-[var(--text-muted)]">
                {offset + 1}–{Math.min(offset + history.analyses.length, history.total_count)} of {history.total_count}
              </span>
              <button
                type="button"
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= history.total_count || isLoading}
                className="tl-button tl-button-secondary"
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </main>
  );
};
