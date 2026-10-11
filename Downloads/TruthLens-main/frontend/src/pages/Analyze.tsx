import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiClient } from '@/lib/api';
import { AlertCircle, Loader, CheckCircle, FileText, ArrowLeft, Terminal, ExternalLink, Globe, HelpCircle } from 'lucide-react';

interface EvidenceSource {
  id: string;
  claim_id: string;
  title: string;
  url: string;
  snippet?: string;
  domain?: string;
  published_date?: string;
  evidence_assessment?: string | null;
  assessment_explanation?: string | null;
  created_at?: string;
}

interface Claim {
  id: string;
  text: string;
  claim_type: string;
  importance: number;
  verifiable: boolean;
  evidence_status: string;
  evidence_note?: string;
  sources: EvidenceSource[];
  verdict?: string | null;
  verdict_explanation?: string | null;
  verdict_limitations?: string | null;
}

interface Analysis {
  id: string;
  status: string;
  claims: Claim[];
  error_message?: string;
  original_input?: string;
}

type InputMode = 'text' | 'claim';

const getVerdictPresentation = (verdict?: string | null, evidenceStatus?: string, sourceCount = 0) => {
  if (verdict === 'INSUFFICIENT_EVIDENCE' || evidenceStatus === 'INSUFFICIENT_EVIDENCE' || sourceCount === 0) {
    return {
      label: 'Insufficient evidence',
      className: 'border-amber-200 bg-amber-50 text-amber-900',
    };
  }

  const presentations: Record<string, { label: string; className: string }> = {
    LIKELY_TRUE: { label: 'Likely true', className: 'border-emerald-200 bg-emerald-50 text-emerald-900' },
    PARTIALLY_TRUE: { label: 'Partially true', className: 'border-amber-200 bg-amber-50 text-amber-900' },
    UNVERIFIED: { label: 'Unverified', className: 'border-slate-200 bg-slate-100 text-slate-800' },
    LIKELY_FALSE: { label: 'Likely false', className: 'border-rose-200 bg-rose-50 text-rose-900' },
  };

  return presentations[verdict ?? ''] ?? {
    label: 'Verdict unavailable',
    className: 'border-slate-200 bg-slate-100 text-slate-700',
  };
};

const getAssessmentPresentation = (assessment?: string | null) => {
  const presentations: Record<string, { label: string; className: string }> = {
    SUPPORTS: { label: 'Supports claim', className: 'bg-emerald-100 text-emerald-800' },
    CONTRADICTS: { label: 'Contradicts claim', className: 'bg-rose-100 text-rose-800' },
    MIXED: { label: 'Mixed evidence', className: 'bg-amber-100 text-amber-800' },
    IRRELEVANT: { label: 'Not relevant to claim', className: 'bg-slate-200 text-slate-700' },
  };

  return presentations[assessment ?? ''] ?? {
    label: 'Assessment unavailable',
    className: 'bg-slate-100 text-slate-600',
  };
};

export default function AnalyzePage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [inputText, setInputText] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [isLoadingSavedAnalysis, setIsLoadingSavedAnalysis] = useState(false);

  useEffect(() => {
    if (!analysisId) return;

    let isCurrent = true;
    setIsLoadingSavedAnalysis(true);
    setError(null);
    setAnalysis(null);

    apiClient.get<Analysis>(`/api/analysis/${analysisId}`)
      .then(({ data }) => {
        if (isCurrent) setAnalysis(data);
      })
      .catch((requestError: any) => {
        if (isCurrent) {
          setError(requestError.response?.data?.detail || 'Unable to reopen this saved analysis.');
        }
      })
      .finally(() => {
        if (isCurrent) setIsLoadingSavedAnalysis(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [analysisId]);

  const characterCount = inputText.length;
  const maxCharacters = 50000;
  const minCharacters = 10;
  const isValidInput = characterCount >= minCharacters && characterCount <= maxCharacters;

  const handleAnalyze = async () => {
    if (!isValidInput) {
      setError(`Input must be between ${minCharacters} and ${maxCharacters} characters`);
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    setAnalysis(null);

    try {
      const endpoint = inputMode === 'text' ? '/api/analysis/text' : '/api/analysis/claim';
      const response = await apiClient.post(endpoint, {
        input_text: inputText,
        input_type: inputMode === 'text' ? 'TEXT' : 'CLAIM',
      });

      if (response.status === 200) {
        setAnalysis(response.data);
        if (response.data.status === 'FAILED') {
          setError(response.data.error_message || 'Analysis failed');
        }
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to analyze input';
      setError(errorMsg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getClaimTypeLabel = (type: string): string => {
    return type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
  };

  const getImportanceColor = (importance: number): string => {
    if (importance >= 0.7) return 'text-red-600 bg-red-50';
    if (importance >= 0.4) return 'text-yellow-600 bg-yellow-50';
    return 'text-blue-600 bg-blue-50';
  };

  const isOllamaError = error?.toLowerCase().includes('ollama');

  return (
    <div className="tl-page">
      <nav className="tl-nav">
        <div className="tl-container flex min-h-16 items-center justify-between gap-4 py-3">
          <Link to="/dashboard" className="tl-brand" aria-label="TruthLens dashboard">
            Truth<span className="tl-brand-accent">Lens</span>
          </Link>
          <div className="flex gap-2">
            <Link to="/history" className="tl-button tl-button-secondary">
              <FileText className="h-4 w-4" />
              <span className="hidden sm:inline">History</span>
            </Link>
            <Link to="/dashboard" className="tl-button tl-button-secondary">
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Dashboard</span>
            </Link>
          </div>
        </div>
      </nav>
      <main className="tl-container max-w-4xl py-8 sm:py-12">
        {/* Header */}
        <div className="mb-7 max-w-2xl">
          <p className="tl-eyebrow mb-2">Evidence review</p>
          <h1 className="tl-heading">Analyze a claim or a passage</h1>
          <p className="mt-3 text-sm text-[var(--text-muted)]">Claims are assessed against retrieved sources. Verdicts are indicators, not guarantees.</p>
        </div>

        {isLoadingSavedAnalysis && (
          <div className="tl-panel mb-5 flex items-center gap-2 p-4 text-sm text-[var(--text-muted)]" role="status">
            <Loader className="h-4 w-4 animate-spin text-[var(--teal)]" />
            Reopening saved analysis...
          </div>
        )}

        {/* Input Section */}
        {!analysisId && <div className="tl-panel mb-6 p-4 sm:p-6">
          {/* Mode Selection */}
          <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="Analysis mode">
            <label className={`flex min-h-10 cursor-pointer items-center gap-2 rounded border px-3 py-2 text-sm font-medium transition-colors ${inputMode === 'text' ? 'border-[var(--teal)] bg-[var(--teal-soft)] text-[var(--teal-dark)]' : 'border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)] hover:bg-[var(--surface-muted)]'}`}>
              <input
                type="radio"
                name="mode"
                value="text"
                checked={inputMode === 'text'}
                onChange={() => setInputMode('text')}
                className="h-4 w-4 accent-[var(--teal)]"
              />
              <span className="text-slate-800 font-medium">Analyze Text (Multi-claim)</span>
            </label>
            <label className={`flex min-h-10 cursor-pointer items-center gap-2 rounded border px-3 py-2 text-sm font-medium transition-colors ${inputMode === 'claim' ? 'border-[var(--teal)] bg-[var(--teal-soft)] text-[var(--teal-dark)]' : 'border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)] hover:bg-[var(--surface-muted)]'}`}>
              <input
                type="radio"
                name="mode"
                value="claim"
                checked={inputMode === 'claim'}
                onChange={() => setInputMode('claim')}
                className="h-4 w-4 accent-[var(--teal)]"
              />
              <span className="text-slate-800 font-medium">Analyze Single Claim</span>
            </label>
          </div>

          {/* Input Area */}
          <div className="mb-4">
            <label className="mb-2 block text-sm font-semibold text-[var(--foreground)]">
              {inputMode === 'text' ? 'Enter text to extract claims & retrieve evidence' : 'Enter a specific factual claim'}
            </label>
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isAnalyzing}
              placeholder={
                inputMode === 'text'
                  ? 'Paste news article, press release, statement, or text to extract factual claims from...'
                  : 'Enter a single factual claim to verify (e.g., "The global average temperature in 2023 was the highest on record")...'
              }
              className="tl-field min-h-40 resize-y px-4 py-3 text-sm leading-relaxed disabled:bg-[var(--surface-muted)] sm:min-h-48"
            />
          </div>

          {/* Character Count */}
          <div className="mb-5 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className={characterCount > 0 && characterCount < minCharacters ? 'font-medium text-[var(--danger)]' : 'text-[var(--text-muted)]'}>
              {characterCount} / {maxCharacters} characters
            </span>
            <span className="text-[var(--text-muted)]">
              Minimum: {minCharacters} characters
            </span>
          </div>

          {/* Error Message with Ollama Startup Helper */}
          {error && (
            <div className="tl-alert-error mb-5 p-4">
              <div className="flex gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0" />
                <div className="flex-1">
                  <h4 className="mb-1 font-semibold">Analysis notice</h4>
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">{error}</div>
                </div>
              </div>

              {isOllamaError && (
                  <div className="mt-4 border-t border-[#e8c5bf] pt-3">
                  <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
                    <Terminal className="w-4 h-4" />
                    How to start Ollama locally:
                  </div>
                  <div className="space-y-1 rounded bg-[#f3eeea] p-3 font-mono text-xs text-[var(--foreground)]">
                    <p>Start the Ollama service:</p>
                    <p className="font-bold text-[var(--teal-dark)]">ollama serve</p>
                    <p className="pt-1">Download the configured model if needed:</p>
                    <p className="font-bold text-[var(--teal-dark)]">ollama pull llama3:8b</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Analyze Button */}
          <button
            onClick={handleAnalyze}
            disabled={!isValidInput || isAnalyzing}
            className="tl-button tl-button-primary w-full"
          >
            {isAnalyzing ? (
              <span className="flex items-center justify-center gap-2">
                <Loader className="h-5 w-5 animate-spin" />
                Extracting claims & retrieving evidence...
              </span>
            ) : (
              inputMode === 'text' ? 'Extract Claims & Retrieve Evidence' : 'Analyze Claim & Retrieve Evidence'
            )}
          </button>
        </div>}

        {/* Results Section */}
        {analysis && (
          <div className="tl-panel p-4 sm:p-6">
            {analysis.status === 'FAILED' ? (
              <div className="tl-alert-error flex gap-3 p-4">
                <AlertCircle className="h-6 w-6 flex-shrink-0" />
                <div>
                  <h3 className="mb-1 font-semibold">Analysis failed</h3>
                  <p>{analysis.error_message || 'An error occurred during analysis'}</p>
                </div>
              </div>
            ) : (
              <>
                <div className="mb-5 flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-[var(--teal)]" />
                  <h2 className="font-serif text-xl font-semibold text-[var(--foreground)]">Claims and sources <span className="font-sans text-sm font-normal text-[var(--text-muted)]">({analysis.claims.length})</span></h2>
                </div>

                <div className="tl-alert-note mb-5 flex items-start gap-2.5 p-3 text-sm">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <p>AI assessments can be wrong. Search snippets may be incomplete or lack the context of the full source.</p>
                </div>

                {analysis.claims.length === 0 ? (
                  <div className="rounded border border-[var(--border)] bg-[var(--surface-muted)] p-4 text-sm text-[var(--text-muted)]">
                    No factual claims were detected in the input text.
                  </div>
                ) : (
                  <div className="space-y-5">
                    {analysis.claims.map((claim) => {
                      const sources = claim.sources ?? [];
                      const verdict = getVerdictPresentation(claim.verdict, claim.evidence_status, sources.length);

                      return (
                      <div
                        key={claim.id}
                        className="rounded border border-[var(--border)] bg-[#fbfaf6] p-4 sm:p-5"
                      >
                        <div className="flex items-start gap-4">
                          <div className="flex-shrink-0">
                            <FileText className="mt-1 h-5 w-5 text-[var(--teal)]" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="mb-3 font-serif text-lg font-semibold leading-relaxed text-[var(--foreground)]">{claim.text}</p>

                            <div className={`mb-4 rounded-sm border-l-[3px] p-3 ${verdict.className}`}>
                              <div className="mb-1 text-xs font-bold uppercase tracking-wide">Verdict: {verdict.label}</div>
                              <p className="text-sm leading-relaxed">
                                {claim.verdict_explanation ||
                                  (verdict.label === 'Insufficient evidence'
                                    ? claim.evidence_note || 'The retrieved material does not provide enough relevant information to assess this claim.'
                                    : 'No explanation was provided for this verdict.')}
                              </p>
                              {claim.verdict_limitations && (
                                <p className="mt-2 text-xs leading-relaxed opacity-80">{claim.verdict_limitations}</p>
                              )}
                            </div>

                            {/* Claim Classification Badges */}
                            <div className="flex flex-wrap gap-2.5 mb-4">
                              <span className="inline-flex items-center rounded border border-[var(--border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--foreground)]">
                                {getClaimTypeLabel(claim.claim_type)}
                              </span>

                              <span
                                className={`inline-flex items-center rounded border border-[var(--border)] px-2.5 py-1 text-xs font-semibold ${getImportanceColor(
                                  claim.importance
                                )}`}
                              >
                                Importance: {(claim.importance * 100).toFixed(0)}%
                              </span>

                              <span
                                  className={`inline-flex items-center rounded border border-[var(--border)] px-2.5 py-1 text-xs font-semibold ${
                                  claim.verifiable
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : 'bg-gray-100 text-gray-700'
                                }`}
                              >
                                {claim.verifiable ? '✓ Verifiable' : '⊘ Opinion / Not Verifiable'}
                              </span>
                            </div>

                            {/* Retrieved Evidence Section */}
                            <div className="mt-4 border-t border-[var(--border)] pt-4">
                              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                                <h4 className="flex items-center gap-1.5 text-sm font-semibold text-[var(--foreground)]">
                                  <Globe className="h-4 w-4 text-[var(--teal)]" />
                                  Retrieved Evidence ({sources.length} source{sources.length !== 1 ? 's' : ''})
                                </h4>
                                {claim.evidence_status === 'EVIDENCE_RETRIEVED' ? (
                                  <span className="rounded border border-[var(--border)] bg-[var(--teal-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--teal-dark)]">
                                    Sources Retrieved
                                  </span>
                                ) : (
                                  <span className="rounded border border-[#e5dcc0] bg-[var(--warning-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--warning)]">
                                    No Sources Found
                                  </span>
                                )}
                              </div>

                              {sources.length > 0 ? (
                                  <div className="space-y-2.5">
                                  {sources.map((source) => {
                                    const assessment = getAssessmentPresentation(source.evidence_assessment);

                                    return (
                                    <div
                                      key={source.id}
                                      className="rounded border border-[var(--border)] bg-[var(--surface)] p-3"
                                    >
                                      <div className="mb-2">
                                        <span className={`inline-flex rounded px-2 py-1 text-[11px] font-semibold ${assessment.className}`}>
                                          {assessment.label}
                                        </span>
                                      </div>
                                      <div className="flex items-start justify-between gap-2">
                                        <a
                                          href={source.url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="flex min-w-0 items-center gap-1.5 text-sm font-semibold text-[var(--teal-dark)] hover:underline"
                                        >
                                          <span className="break-words">{source.title || source.url}</span>
                                          <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
                                        </a>
                                        {source.domain && (
                                          <span className="shrink-0 rounded bg-[var(--surface-muted)] px-2 py-0.5 font-mono text-[11px] text-[var(--text-muted)]">
                                            {source.domain}
                                          </span>
                                        )}
                                      </div>
                                      {source.snippet && (
                                        <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-[var(--text-muted)]">
                                          "{source.snippet}"
                                        </p>
                                      )}
                                      {source.assessment_explanation && (
                                        <p className="mt-2 text-xs text-[var(--text-muted)]">Assessment: {source.assessment_explanation}</p>
                                      )}
                                      <div className="mt-2 break-all text-[11px] text-[var(--text-muted)]">
                                        Source: {source.url}
                                      </div>
                                    </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <div className="tl-alert-note space-y-1 rounded-sm p-3.5 text-sm">
                                  <div className="font-semibold flex items-center gap-1.5">
                                    <HelpCircle className="h-4 w-4" />
                                    Insufficient Evidence Available
                                  </div>
                                  <p className="text-amber-800">
                                    {claim.evidence_note || 'No relevant external sources were found for this claim.'}
                                  </p>
                                  <p className="pt-1 text-xs italic opacity-80">
                                    Note: TruthLens never hallucinates or substitutes fake sources when web search is unavailable or returns no results.
                                  </p>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
