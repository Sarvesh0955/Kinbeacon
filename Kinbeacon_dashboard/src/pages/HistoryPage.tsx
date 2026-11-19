import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { History, MapPin, Eye, Layers } from 'lucide-react';
import { getDeviceSearches, getSearch, listDevices } from '../api/endpoints';
import { PageHeader, LoadingSpinner, EmptyState, ErrorBanner } from '../components/common/UIFeedback';
import { Modal } from '../components/common/Modal';
import { StatusBadge } from '../components/common/StatusBadge';
import { getErrorMessage } from '../api/client';
import toast from 'react-hot-toast';

export const HistoryPage: React.FC = () => {
  const [selectedDeviceId, setSelectedDeviceId] = useState('');
  const [activeSearchId, setActiveSearchId] = useState<string | null>(null);

  const { data: devices } = useQuery({
    queryKey: ['devices'],
    queryFn: listDevices,
  });

  const {
    data: searchList,
    isLoading: historyLoading,
    error: historyError,
    refetch,
  } = useQuery({
    queryKey: ['device-searches', selectedDeviceId],
    queryFn: () => getDeviceSearches(selectedDeviceId, 25),
    enabled: !!selectedDeviceId.trim(),
  });

  const { data: detailData, isLoading: detailLoading } = useQuery({
    queryKey: ['search-detail', activeSearchId],
    queryFn: () => (activeSearchId ? getSearch(activeSearchId) : null),
    enabled: !!activeSearchId,
  });

  const handleLookup = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDeviceId.trim()) {
      toast.error('Enter a device ID to view history');
      return;
    }
    refetch();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Search Request History"
        description="Inspect past device localization audits, timestamps, and zone estimates from the SQLite ledger."
      />

      {/* Device Selector */}
      <div className="p-6 rounded-xl bg-white border border-slate-200/80 shadow-sm space-y-3">
        <form onSubmit={handleLookup} className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={selectedDeviceId}
              onChange={(e) => setSelectedDeviceId(e.target.value)}
              placeholder="Enter device ID (e.g. KINBEACON-PHONE1)"
              className="w-full px-4 py-2.5 text-sm font-mono border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2.5 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors flex items-center justify-center gap-2"
          >
            <History className="w-4 h-4" />
            <span>Load History</span>
          </button>
        </form>

        {devices && devices.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1 text-xs">
            <span className="text-slate-400 font-medium">Select Device:</span>
            {devices.map((d) => (
              <button
                type="button"
                key={d.device_id}
                onClick={() => setSelectedDeviceId(d.device_id)}
                className={`px-2 py-0.5 rounded font-mono border transition-colors ${
                  selectedDeviceId === d.device_id
                    ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-bold'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                {d.device_id}
              </button>
            ))}
          </div>
        )}
      </div>

      {historyError && <ErrorBanner message={getErrorMessage(historyError)} />}

      {/* History Table */}
      {historyLoading ? (
        <LoadingSpinner message="Fetching historical searches..." />
      ) : !selectedDeviceId ? (
        <div className="text-center py-12 px-4 border border-dashed border-slate-200 rounded-xl bg-white text-slate-500 text-sm">
          Select or enter a device ID above to review its search event log.
        </div>
      ) : !searchList || searchList.length === 0 ? (
        <EmptyState
          title="No Search History Found"
          description={`No past location searches found for device "${selectedDeviceId}".`}
        />
      ) : (
        <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Search UUID</th>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Detected Zone</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Flags</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {searchList.map((s) => (
                  <tr
                    key={s.search_id}
                    className="hover:bg-slate-50/60 cursor-pointer transition-colors"
                    onClick={() => setActiveSearchId(s.search_id)}
                  >
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-700">
                      {s.search_id.slice(0, 8)}...
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600 font-mono">
                      {new Date(s.started_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      {s.zone ? (
                        <span className="font-medium text-slate-900 flex items-center gap-1.5">
                          <MapPin className="w-3.5 h-3.5 text-indigo-600" />
                          {s.zone.name}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 italic">Not detected</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="px-4 py-3">
                      {s.flags && s.flags.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {s.flags.map((f) => (
                            <span
                              key={f}
                              className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200"
                            >
                              {f}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400 italic">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveSearchId(s.search_id);
                        }}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Search Detail Modal */}
      {activeSearchId && (
        <Modal
          isOpen={!!activeSearchId}
          onClose={() => setActiveSearchId(null)}
          title="Search Audit Details"
          maxWidth="max-w-xl"
        >
          {detailLoading ? (
            <LoadingSpinner message="Loading search records..." />
          ) : detailData ? (
            <div className="space-y-4 text-sm">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 font-mono text-xs space-y-1">
                <div>
                  <span className="text-slate-400">Search ID:</span> {detailData.search_id}
                </div>
                <div>
                  <span className="text-slate-400">Device ID:</span> {detailData.device_id}
                </div>
                <div>
                  <span className="text-slate-400">Started:</span>{' '}
                  {new Date(detailData.started_at).toLocaleString()}
                </div>
              </div>

              <div className="p-3 border border-slate-200 rounded-lg">
                <span className="text-xs text-slate-400 uppercase font-semibold block">
                  Resolved Zone
                </span>
                <div className="text-base font-bold text-slate-900 mt-1">
                  {detailData.zone ? detailData.zone.name : 'None (NOT_SEEN)'}
                </div>
              </div>

              {detailData.candidates && detailData.candidates.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold uppercase text-slate-600 mb-2 flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5 text-indigo-500" />
                    Zone Candidates
                  </h4>
                  <table className="w-full text-xs text-left border border-slate-100 rounded-lg overflow-hidden">
                    <thead className="bg-slate-50 font-semibold text-slate-500">
                      <tr>
                        <th className="px-3 py-1.5">Zone</th>
                        <th className="px-3 py-1.5">Score</th>
                        <th className="px-3 py-1.5">Probability</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      {detailData.candidates.map((c, i) => (
                        <tr key={i}>
                          <td className="px-3 py-1.5 font-sans">
                            {c.zone_name || `Zone #${c.zone_id}`}
                          </td>
                          <td className="px-3 py-1.5">{c.score}</td>
                          <td className="px-3 py-1.5">{(c.probability * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button
                  onClick={() => setActiveSearchId(null)}
                  className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
                >
                  Close
                </button>
              </div>
            </div>
          ) : null}
        </Modal>
      )}
    </div>
  );
};
