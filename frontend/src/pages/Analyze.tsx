import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/lib/api';
import { AlertCircle, Loader, CheckCircle, FileText } from 'lucide-react';

interface Claim {
  id: string;
  text: string;
  claim_type: string;
  importance: number;
  verifiable: boolean;
}

interface Analysis {
  id: string;
  status: string;
  claims: Claim[];
  error_message?: string;
}

type InputMode = 'text' | 'claim';

export default function AnalyzePage() {
  const { user } = useAuth();
  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [inputText, setInputText] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">TruthLens</h1>
          <p className="text-slate-300">AI-Powered Fact-Checking & Claim Verification</p>
        </div>

        {/* Input Section */}
        <div className="bg-white rounded-lg shadow-xl p-6 mb-6">
          {/* Mode Selection */}
          <div className="mb-6 flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="mode"
                value="text"
                checked={inputMode === 'text'}
                onChange={() => setInputMode('text')}
                className="w-4 h-4"
              />
              <span className="text-slate-700 font-medium">Analyze Text</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="mode"
                value="claim"
                checked={inputMode === 'claim'}
                onChange={() => setInputMode('claim')}
                className="w-4 h-4"
              />
              <span className="text-slate-700 font-medium">Analyze Claim</span>
            </label>
          </div>

          {/* Input Area */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              {inputMode === 'text' ? 'Enter text to analyze' : 'Enter a claim to verify'}
            </label>
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isAnalyzing}
              placeholder={
                inputMode === 'text'
                  ? 'Paste news article, social media post, or any text...'
                  : 'Enter a specific claim to analyze...'
              }
              className="w-full h-48 p-4 border border-slate-300 rounded-lg font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100"
            />
          </div>

          {/* Character Count */}
          <div className="mb-6 flex justify-between items-center text-sm">
            <span className={characterCount < minCharacters ? 'text-red-600' : 'text-slate-600'}>
              {characterCount} / {maxCharacters} characters
            </span>
            <span className="text-slate-500">
              Minimum: {minCharacters} characters
            </span>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="text-red-700">{error}</div>
            </div>
          )}

          {/* Analyze Button */}
          <button
            onClick={handleAnalyze}
            disabled={!isValidInput || isAnalyzing}
            className={`w-full py-3 px-4 rounded-lg font-semibold text-white transition-colors ${
              !isValidInput || isAnalyzing
                ? 'bg-slate-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
            }`}
          >
            {isAnalyzing ? (
              <span className="flex items-center justify-center gap-2">
                <Loader className="w-5 h-5 animate-spin" />
                Analyzing...
              </span>
            ) : (
              'Analyze'
            )}
          </button>
        </div>

        {/* Results Section */}
        {analysis && (
          <div className="bg-white rounded-lg shadow-xl p-6">
            {analysis.status === 'FAILED' ? (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
                <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-red-800 mb-1">Analysis Failed</h3>
                  <p className="text-red-700">{analysis.error_message || 'An error occurred during analysis'}</p>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-6">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                  <h2 className="text-2xl font-bold text-slate-900">Claims Detected</h2>
                </div>

                {analysis.claims.length === 0 ? (
                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-slate-600">
                    No factual claims were detected in the input text.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {analysis.claims.map((claim, index) => (
                      <div
                        key={claim.id}
                        className="p-4 border border-slate-200 rounded-lg hover:border-blue-300 transition-colors"
                      >
                        <div className="flex items-start gap-4">
                          <div className="flex-shrink-0">
                            <FileText className="w-5 h-5 text-slate-400 mt-1" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-slate-900 mb-3 leading-relaxed">{claim.text}</p>

                            <div className="flex flex-wrap gap-3">
                              {/* Claim Type Badge */}
                              <div className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
                                {getClaimTypeLabel(claim.claim_type)}
                              </div>

                              {/* Importance Badge */}
                              <div
                                className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${getImportanceColor(
                                  claim.importance
                                )}`}
                              >
                                Importance: {(claim.importance * 100).toFixed(0)}%
                              </div>

                              {/* Verifiable Badge */}
                              <div
                                className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${
                                  claim.verifiable
                                    ? 'bg-green-100 text-green-700'
                                    : 'bg-gray-100 text-gray-700'
                                }`}
                              >
                                {claim.verifiable ? '✓ Verifiable' : '⊘ Opinion/Not Verifiable'}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Note about Phase 3 */}
                <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-700">
                    <strong>Note:</strong> Phase 3 focuses on claim extraction and classification. Fact verification,
                    evidence linking, and verdicts will be available in Phase 4 and Phase 5.
                  </p>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
