import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Radio,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  RefreshCw,
  Zap,
} from 'lucide-react';
import { getFleetHealth, verifyAnchor } from '../api/endpoints';
import { PageHeader, LoadingSpinner, ErrorBanner } from '../components/common/UIFeedback';
import { StatusBadge } from '../components/common/StatusBadge';
import { getErrorMessage } from '../api/client';
import toast from 'react-hot-toast';

export const FleetHealthPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [autoRefresh, setAutoRefresh] = useState(true);

  const {
    data: fleet,
    isLoading,
    error,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['fleet-health'],
    queryFn: getFleetHealth,
    refetchInterval: autoRefresh ? 15000 : false,
  });

  const verifyMutation = useMutation({
    mutationFn: verifyAnchor,
    onSuccess: (res) => {
      toast.success(
        `Anchor ${res.anchor_id} probe complete: ${res.verified ? 'Verified' : 'Failed'}`
      );
      queryClient.invalidateQueries({ queryKey: ['fleet-health'] });
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
    },
    onError: (err) => {
      toast.error(`Verification failed: ${getErrorMessage(err)}`);
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fleet Connectivity & Health"
        description="Live polling status of distributed anchors, circuit breakers, and background prober heartbeats."
      >
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer bg-white px-3 py-2 border border-slate-300 rounded-lg shadow-sm">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 text-indigo-600 rounded"
            />
            <span>Auto-Poll (15s)</span>
          </label>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Poll Fleet</span>
          </button>
        </div>
      </PageHeader>

      {error && <ErrorBanner message={getErrorMessage(error)} />}

      {isLoading ? (
        <LoadingSpinner message="Querying anchor fleet status..." />
      ) : fleet ? (
        <>
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-5 rounded-xl bg-white border border-emerald-200/80 shadow-sm">
              <div className="flex items-center justify-between text-xs font-semibold text-emerald-700 uppercase">
                <span>Healthy (UP)</span>
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              </div>
              <div className="mt-2 text-3xl font-bold text-emerald-800">{fleet.up}</div>
              <p className="mt-1 text-xs text-slate-500">Responding to health probes</p>
            </div>

            <div className="p-5 rounded-xl bg-white border border-amber-200/80 shadow-sm">
              <div className="flex items-center justify-between text-xs font-semibold text-amber-700 uppercase">
                <span>Degraded</span>
                <AlertTriangle className="w-5 h-5 text-amber-600" />
              </div>
              <div className="mt-2 text-3xl font-bold text-amber-800">{fleet.degraded}</div>
              <p className="mt-1 text-xs text-slate-500">Consecutive failures / circuit tripped</p>
            </div>

            <div className="p-5 rounded-xl bg-white border border-rose-200/80 shadow-sm">
              <div className="flex items-center justify-between text-xs font-semibold text-rose-700 uppercase">
                <span>Offline (DOWN)</span>
                <XCircle className="w-5 h-5 text-rose-600" />
              </div>
              <div className="mt-2 text-3xl font-bold text-rose-800">{fleet.down}</div>
              <p className="mt-1 text-xs text-slate-500">Connection refused / timeout</p>
            </div>

            <div className="p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase">
                <span>Unknown</span>
                <HelpCircle className="w-5 h-5 text-slate-400" />
              </div>
              <div className="mt-2 text-3xl font-bold text-slate-700">{fleet.unknown}</div>
              <p className="mt-1 text-xs text-slate-500">Awaiting first prober tick</p>
            </div>
          </div>

          {/* Circuit Breaker & Prober Information Panel */}
          <div className="p-4 rounded-xl bg-indigo-50/60 border border-indigo-100 text-xs text-indigo-900 flex items-start gap-3">
            <Zap className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold block text-sm">Resilience & Circuit Breaker Architecture:</span>
              <p className="mt-0.5 text-indigo-800">
                The central server background worker probes every enabled anchor every 15 seconds. If an anchor encounters{' '}
                <strong>3 consecutive failures</strong>, its circuit breaker trips: the anchor is marked{' '}
                <code>DEGRADED</code> and skipped for a 30-second cooldown window. Search fan-outs continue uninterrupted with surviving anchors.
              </p>
            </div>
          </div>

          {/* Anchor Fleet Health Detail Table */}
          <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <Radio className="w-4 h-4 text-indigo-600" />
                <span>Anchor Fleet Live Telemetry ({fleet.total_anchors} Total)</span>
              </h3>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Anchor ID</th>
                    <th className="px-4 py-3">Assigned Zone</th>
                    <th className="px-4 py-3">Health State</th>
                    <th className="px-4 py-3">In Fan-Out (Active)</th>
                    <th className="px-4 py-3">Failures</th>
                    <th className="px-4 py-3">Verified</th>
                    <th className="px-4 py-3">Last Success</th>
                    <th className="px-4 py-3">Last Failure</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {fleet.anchors.length > 0 ? (
                    fleet.anchors.map((a) => (
                      <tr key={a.anchor_id} className="hover:bg-slate-50/50">
                        <td className="px-4 py-3 font-mono font-bold text-slate-900">
                          {a.anchor_id}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-700">
                          {a.zone_id ? `Zone #${a.zone_id}` : <span className="text-slate-400 italic">None</span>}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={a.health_state} />
                        </td>
                        <td className="px-4 py-3">
                          {a.is_active ? (
                            <span className="text-xs font-semibold text-emerald-600">✓ Active</span>
                          ) : (
                            <span className="text-xs font-semibold text-rose-600">✗ Tripped</span>
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">
                          <span
                            className={
                              a.consecutive_failures > 0 ? 'text-rose-600 font-bold' : 'text-slate-500'
                            }
                          >
                            {a.consecutive_failures}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {a.verified ? (
                            <span className="text-xs text-emerald-600 font-medium">✓ Yes</span>
                          ) : (
                            <span className="text-xs text-amber-600 font-medium">✗ No</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-slate-500">
                          {a.last_success_at
                            ? new Date(a.last_success_at).toLocaleTimeString()
                            : '-'}
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-slate-500">
                          {a.last_failure_at
                            ? new Date(a.last_failure_at).toLocaleTimeString()
                            : '-'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => verifyMutation.mutate(a.anchor_id)}
                            disabled={verifyMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded transition-colors"
                          >
                            <RefreshCw
                              className={`w-3 h-3 ${verifyMutation.isPending ? 'animate-spin' : ''}`}
                            />
                            <span>Probe</span>
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={9} className="px-4 py-8 text-center text-slate-400 text-xs">
                        No anchors configured in the fleet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};
