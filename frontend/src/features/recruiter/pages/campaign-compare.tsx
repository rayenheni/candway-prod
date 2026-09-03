import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import {
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  Users,
  Award,
  Mail,
  TrendingUp,
  FileSpreadsheet,
  Plus,
  X,
  Building2,
  Calendar,
} from 'lucide-react';
import { campaignsService } from '@/services/campaigns.service';
import { useLanguage } from '@/contexts/language-context';

export default function CampaignComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useLanguage();
  const idsParam = searchParams.get('ids') || '';

  const [selectedIds, setSelectedIds] = useState<number[]>(() => {
    return idsParam
      .split(',')
      .map((x) => parseInt(x.trim(), 10))
      .filter((n) => !isNaN(n) && n > 0);
  });

  const [availableCampaigns, setAvailableCampaigns] = useState<any[]>([]);
  const [analyticsData, setAnalyticsData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load available campaigns list for picker
  useEffect(() => {
    campaignsService
      .list({ per_page: 50 })
      .then((res: any) => {
        const items = Array.isArray(res) ? res : res?.items || [];
        setAvailableCampaigns(items);
        // If no IDs in URL, default to first 2 available campaigns
        if (selectedIds.length === 0 && items.length > 0) {
          const defaultIds = items.slice(0, 3).map((c: any) => c.id);
          setSelectedIds(defaultIds);
        }
      })
      .catch((err) => console.error('Failed to load campaigns list', err));
  }, []);

  // Sync selectedIds with URL
  useEffect(() => {
    if (selectedIds.length > 0) {
      setSearchParams({ ids: selectedIds.join(',') });
    }
  }, [selectedIds]);

  // Fetch comparison analytics whenever selectedIds changes
  useEffect(() => {
    if (selectedIds.length === 0) {
      setAnalyticsData([]);
      return;
    }
    setLoading(true);
    setError(null);
    campaignsService
      .compare(selectedIds)
      .then((data) => {
        setAnalyticsData(data || []);
      })
      .catch((err) => {
        console.error('Comparison fetch error', err);
        setError(t('camp.compare.loadError'));
      })
      .finally(() => setLoading(false));
  }, [selectedIds]);

  const toggleCampaign = (id: number) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((i) => i !== id));
    } else {
      if (selectedIds.length >= 5) {
        alert(t('camp.compare.maxFive'));
        return;
      }
      setSelectedIds([...selectedIds, id]);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6 md:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <button
          onClick={() => navigate('/campaigns')}
          className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> {t('camp.compare.backToCampaigns')}
        </button>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <BarChart3 className="w-8 h-8 text-indigo-400" />
              {t('camp.compare.title')}
            </h1>
            <p className="text-slate-400 mt-1">
              {t('camp.compare.subtitle')}
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto space-y-8">
        {/* Campaign Picker Bar */}
        <div className="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 backdrop-blur-sm">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
            {t('camp.compare.selectedLabel').replace('{count}', String(selectedIds.length))}
          </label>
          <div className="flex flex-wrap items-center gap-2">
            {availableCampaigns.map((c) => {
              const isSelected = selectedIds.includes(c.id);
              return (
                <button
                  key={c.id}
                  onClick={() => toggleCampaign(c.id)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition flex items-center gap-2 border ${
                    isSelected
                      ? 'bg-indigo-600/90 text-white border-indigo-500 shadow-sm shadow-indigo-500/20'
                      : 'bg-slate-900/60 text-slate-300 border-slate-700 hover:border-slate-500 hover:text-white'
                  }`}
                >
                  {isSelected ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Plus className="w-4 h-4 text-slate-400" />}
                  <span>{c.title}</span>
                </button>
              );
            })}
          </div>
        </div>

        {loading && (
          <div className="text-center py-16 bg-slate-800/40 rounded-xl border border-slate-800">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-500 border-t-transparent mb-3"></div>
            <p className="text-slate-400 text-sm">{t('camp.compare.loading')}</p>
          </div>
        )}

        {error && (
          <div className="bg-rose-900/30 border border-rose-700/50 text-rose-200 p-4 rounded-xl text-sm">
            {error}
          </div>
        )}

        {!loading && analyticsData.length === 0 && selectedIds.length > 0 && (
          <div className="text-center py-16 bg-slate-800/40 rounded-xl border border-slate-800 text-slate-400">
            {t('camp.compare.noData')}
          </div>
        )}

        {!loading && analyticsData.length > 0 && (
          <>
            {/* Side by Side Comparison Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {analyticsData.map((item) => {
                const total = item.total_candidates || 0;
                const avgScore = item.avg_cv_score ? Math.round(item.avg_cv_score) : 0;
                const qualCount = item.qualified_count || 0;
                const qualRate = total > 0 ? Math.round((qualCount / total) * 100) : 0;

                return (
                  <div
                    key={item.campaign_id}
                    className="bg-slate-800/90 border border-slate-700/70 rounded-2xl p-6 shadow-xl space-y-6 flex flex-col justify-between"
                  >
                    <div>
                      {/* Title & Header */}
                      <div className="flex items-start justify-between gap-2 mb-4">
                        <div>
                          <h3 className="font-bold text-lg text-white line-clamp-1">{item.campaign_name}</h3>
                          <p className="text-xs text-slate-400 mt-0.5">ID: #{item.campaign_id}</p>
                        </div>
                        <button
                          onClick={() => navigate(`/campaigns/${item.campaign_id}`)}
                          className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 px-2.5 py-1 rounded-lg border border-indigo-500/30 transition"
                        >
                          {t('camp.compare.open')}
                        </button>
                      </div>

                      {/* Score Highlight Badge */}
                      <div className="grid grid-cols-2 gap-3 mb-6">
                        <div className="bg-slate-900/80 rounded-xl p-3.5 border border-slate-700/50">
                          <span className="text-xs font-semibold text-slate-400 block mb-1">{t('camp.compare.avgCvScore')}</span>
                          <span className="text-2xl font-extrabold text-indigo-400">{avgScore}%</span>
                        </div>
                        <div className="bg-slate-900/80 rounded-xl p-3.5 border border-slate-700/50">
                          <span className="text-xs font-semibold text-slate-400 block mb-1">{t('camp.compare.qualifiedRate')}</span>
                          <span className="text-2xl font-extrabold text-emerald-400">{qualRate}%</span>
                        </div>
                      </div>

                      {/* Metrics List */}
                      <div className="space-y-3 text-sm">
                        <div className="flex justify-between items-center py-1.5 border-b border-slate-700/40">
                          <span className="text-slate-400 flex items-center gap-2">
                            <Users className="w-4 h-4 text-slate-500" /> {t('camp.compare.totalCandidates')}
                          </span>
                          <span className="font-semibold text-slate-200">{total}</span>
                        </div>

                        <div className="flex justify-between items-center py-1.5 border-b border-slate-700/40">
                          <span className="text-slate-400 flex items-center gap-2">
                            <Award className="w-4 h-4 text-emerald-500" /> {t('camp.compare.qualified70')}
                          </span>
                          <span className="font-semibold text-emerald-400">{qualCount} {t('campaign.candidates')}</span>
                        </div>

                        <div className="flex justify-between items-center py-1.5 border-b border-slate-700/40">
                          <span className="text-slate-400 flex items-center gap-2">
                            <Mail className="w-4 h-4 text-sky-500" /> {t('camp.compare.emailOpenRate')}
                          </span>
                          <span className="font-semibold text-slate-200">{item.open_rate}%</span>
                        </div>

                        <div className="flex justify-between items-center py-1.5 border-b border-slate-700/40">
                          <span className="text-slate-400 flex items-center gap-2">
                            <TrendingUp className="w-4 h-4 text-purple-500" /> {t('camp.compare.responseRate')}
                          </span>
                          <span className="font-semibold text-purple-300">
                            {item.response_rate !== null && item.response_rate !== undefined
                              ? `${item.response_rate}%`
                              : t('camp.compare.na')}
                          </span>
                        </div>
                      </div>

                      {/* Pipeline Stage Mini Breakdown */}
                      <div className="mt-6">
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block mb-2">
                          {t('camp.compare.pipelineBreakdown')}
                        </span>
                        <div className="grid grid-cols-4 gap-1.5 text-center text-xs">
                          <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                            <span className="block text-slate-400 font-medium">{t('apps.legend.invited')}</span>
                            <span className="font-bold text-amber-400 mt-0.5 block">
                              {item.pipeline?.invited || 0}
                            </span>
                          </div>
                          <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                            <span className="block text-slate-400 font-medium">{t('apps.interview')}</span>
                            <span className="font-bold text-sky-400 mt-0.5 block">
                              {item.pipeline?.interviewing || 0}
                            </span>
                          </div>
                          <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                            <span className="block text-slate-400 font-medium">{t('camp.compare.pipelineOffer')}</span>
                            <span className="font-bold text-indigo-400 mt-0.5 block">
                              {item.pipeline?.offer || 0}
                            </span>
                          </div>
                          <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                            <span className="block text-slate-400 font-medium">{t('camp.compare.pipelineHired')}</span>
                            <span className="font-bold text-emerald-400 mt-0.5 block">
                              {item.pipeline?.hired || 0}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
