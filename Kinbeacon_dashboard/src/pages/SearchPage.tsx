import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Search,
  MapPin,
  Radio,
  Clock,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  Layers,
} from 'lucide-react';
import { executeSearch, listDevices } from '../api/endpoints';
import { PageHeader, LoadingSpinner } from '../components/common/UIFeedback';
import { StatusBadge } from '../components/common/StatusBadge';
import { SearchResponse } from '../api/types';
import { getErrorMessage } from '../api/client';
import toast from 'react-hot-toast';
import { LastMileDemo } from '../components/common/LastMileDemo';

export const SearchPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialDeviceId = searchParams.get('device_id') || '';

  const [deviceId, setDeviceId] = useState(initialDeviceId);
  const [maxAge, setMaxAge] = useState<string>('');
  const [requestedBy, setRequestedBy] = useState('Staff-Dashboard');
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const { data: registeredDevices } = useQuery({
    queryKey: ['devices'],
    queryFn: listDevices,
  });

  const searchMutation = useMutation({
    mutationFn: executeSearch,
    onSuccess: (data) => {
      setSearchResult(data);
      setSearchError(null);
      if (data.flags?.includes('NOT_SEEN')) {
        toast('Device not heard within analysis window', { icon: 'ℹ️' });
      } else if (data.zone) {
        toast.success(`Located in ${data.zone.name}!`);
      }
    },
    onError: (err: any) => {
      setSearchResult(null);
      const msg = getErrorMessage(err);
      setSearchError(msg);
      toast.error(msg);
    },
  });

  const handleSearch = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!deviceId.trim()) {
      toast.error('Please enter a device ID');
      return;
    }
    setSearchParams({ device_id: deviceId.trim() });
    searchMutation.mutate({
      device_id: deviceId.trim(),
      max_age_s: maxAge ? parseFloat(maxAge) : undefined,
      requested_by: requestedBy.trim() || undefined,
    });
  };

  useEffect(() => {
    if (initialDeviceId && !searchResult && !searchMutation.isPending) {
      setDeviceId(initialDeviceId);
      searchMutation.mutate({
        device_id: initialDeviceId,
        requested_by: requestedBy,
      });
    }
  }, [initialDeviceId]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Device Location Detection"
        description="Query the anchor fleet concurrently, aggregate Bluetooth RSSI logs, and estimate zone position."
      />

      <LastMileDemo />

      {/* Search Bar & Options */}
      <div className="p-6 rounded-xl bg-white border border-slate-200/80 shadow-sm">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="flex-1 relative">
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Target Device ID *
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  value={deviceId}
                  onChange={(e) => setDeviceId(e.target.value)}
                  placeholder="e.g. KINBEACON-PHONE1 or kb-phone1"
                  className="w-full pl-10 pr-4 py-2.5 text-sm font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              </div>
            </div>

            <div className="w-full md:w-44">
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Max Age (sec, opt)
              </label>
              <input
                type="number"
                value={maxAge}
                onChange={(e) => setMaxAge(e.target.value)}
                placeholder="Default: 600"
                className="w-full px-3 py-2.5 text-sm font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="w-full md:w-48">
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Requested By
              </label>
              <input
                type="text"
                value={requestedBy}
                onChange={(e) => setRequestedBy(e.target.value)}
                className="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-end">
              <button
                type="submit"
                disabled={searchMutation.isPending}
                className="w-full md:w-auto px-6 py-2.5 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 shadow-sm flex items-center justify-center gap-2 transition-colors"
              >
                <Search className="w-4 h-4" />
                <span>{searchMutation.isPending ? 'Searching Fleet...' : 'Locate Device'}</span>
              </button>
            </div>
          </div>

          {/* Quick suggestions from registered devices */}
          {registeredDevices && registeredDevices.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-xs">
              <span className="text-slate-400 font-medium">Quick Select:</span>
              {registeredDevices.map((d) => (
                <button
                  type="button"
                  key={d.device_id}
                  onClick={() => {
                    setDeviceId(d.device_id);
                    setSearchParams({ device_id: d.device_id });
                    searchMutation.mutate({
                      device_id: d.device_id,
                      requested_by: requestedBy,
                    });
                  }}
                  className={`px-2 py-0.5 rounded font-mono border transition-colors ${
                    deviceId === d.device_id
                      ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-bold'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {d.device_id}
                </button>
              ))}
            </div>
          )}
        </form>
      </div>

      {/* Loading Indicator */}
      {searchMutation.isPending && (
        <LoadingSpinner message="Polling distributed Bluetooth anchors across venue..." />
      )}

      {/* Error state */}
      {searchError && (
        <div className="p-6 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>Search Unsuccessful</span>
          </div>
          <p className="text-sm">{searchError}</p>
          {searchError.includes('not found') && (
            <p className="text-xs text-rose-700 mt-2">
              Tip: The device must be registered in the central server registry first.{' '}
              <Link to="/devices" className="underline font-semibold">
                Go to Devices page to register &rarr;
              </Link>
            </p>
          )}
        </div>
      )}

      {/* Search Results Display */}
      {searchResult && (
        <div className="space-y-6">
          {/* Main Resolution Card */}
          <div className="p-6 rounded-xl bg-white border border-slate-200/80 shadow-sm space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-100 gap-4">
              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                  Search ID: <span className="font-mono text-slate-600">{searchResult.search_id}</span>
                </span>
                <div className="text-xl font-bold text-slate-900 mt-0.5 flex items-center gap-2">
                  <span>Target:</span>
                  <span className="font-mono text-indigo-600">{searchResult.device_id}</span>
                  <StatusBadge status={searchResult.status} />
                </div>
              </div>
            </div>

            {/* Flags Alert Row */}
            {searchResult.flags && searchResult.flags.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg bg-amber-50/70 border border-amber-200 text-xs text-amber-900">
                <span className="font-semibold flex items-center gap-1">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  Algorithm Flags:
                </span>
                {searchResult.flags.map((flag) => (
                  <span
                    key={flag}
                    className="px-2 py-0.5 rounded font-mono font-bold bg-amber-100 text-amber-800 border border-amber-300"
                  >
                    {flag}
                  </span>
                ))}
                {searchResult.flags.includes('STALE') && (
                  <span className="text-amber-700">
                    &bull; Last detection &gt; 30s ago. Search scope automatically expanded to adjacent zones.
                  </span>
                )}
                {searchResult.flags.includes('SINGLE_ANCHOR') && (
                  <span className="text-amber-700">
                    &bull; Only 1 anchor heard beacon; maximum confidence capped at 0.75.
                  </span>
                )}
                {searchResult.flags.includes('CONFLICT') && (
                  <span className="text-amber-700">
                    &bull; Simultaneous non-adjacent candidate conflict detected; confidence penalized by 0.6x.
                  </span>
                )}
              </div>
            )}

            {/* Primary Resolution Highlight */}
            {searchResult.zone ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 p-5 rounded-xl bg-gradient-to-br from-indigo-50/50 to-slate-50 border border-indigo-100">
                <div>
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                    Detected Zone
                  </span>
                  <div className="text-2xl font-black text-slate-900 mt-1 flex items-center gap-2">
                    <MapPin className="w-6 h-6 text-indigo-600 shrink-0" />
                    <span>{searchResult.zone.name}</span>
                  </div>
                  <span className="text-xs font-mono text-slate-500 mt-0.5 block">
                    Zone ID: #{searchResult.zone.id}
                  </span>
                </div>

                <div>
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                    Estimated Coordinates
                  </span>
                  <div className="text-xl font-bold font-mono text-slate-800 mt-1">
                    {searchResult.estimated_position ? (
                      <>
                        X: {searchResult.estimated_position.x.toFixed(1)}m, Y:{' '}
                        {searchResult.estimated_position.y.toFixed(1)}m
                      </>
                    ) : (
                      'N/A'
                    )}
                  </div>
                  <span className="text-xs text-slate-500 mt-0.5 block">
                    Floor: {searchResult.estimated_position?.floor ?? 0}
                  </span>
                </div>

                <div>
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                    Last Seen / Sighting Age
                  </span>
                  <div className="text-xl font-bold font-mono text-slate-800 mt-1 flex items-center gap-1.5">
                    <Clock className="w-5 h-5 text-slate-500" />
                    <span>{searchResult.age_s !== null ? `${searchResult.age_s.toFixed(1)}s ago` : 'Never'}</span>
                  </div>
                  <span className="text-xs text-slate-500 mt-0.5 block font-mono">
                    {searchResult.last_seen_at
                      ? new Date(searchResult.last_seen_at).toLocaleTimeString()
                      : 'No timestamp'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center rounded-xl bg-slate-50 border border-slate-200">
                <HelpCircle className="w-10 h-10 text-slate-400 mx-auto mb-2" />
                <h3 className="text-base font-bold text-slate-800">Device Not Heard</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                  None of the active anchors recorded BLE advertisements for device &quot;
                  {searchResult.device_id}&quot; within the rolling retention window.
                </p>
              </div>
            )}

            {/* Fleet Fan-Out Status Bar */}
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 text-xs">
              <div className="font-semibold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Radio className="w-4 h-4 text-indigo-600" />
                <span>Anchor Fleet Fan-Out Summary</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-slate-800">
                <div>
                  <span className="text-slate-400 block text-[11px] font-sans">Targeted:</span>
                  <span className="text-base font-bold">{searchResult.anchors.targeted}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px] font-sans">Responded:</span>
                  <span className="text-base font-bold text-emerald-600">
                    {searchResult.anchors.responded}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px] font-sans">Timed Out:</span>
                  <span className="text-base font-bold text-amber-600">
                    {searchResult.anchors.timed_out}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px] font-sans">Failed:</span>
                  <span className="text-base font-bold text-rose-600">
                    {searchResult.anchors.failed}
                  </span>
                </div>
              </div>
              {searchResult.anchors.unreachable.length > 0 && (
                <div className="mt-2 text-rose-600 text-[11px]">
                  Unreachable anchors: {searchResult.anchors.unreachable.join(', ')}
                </div>
              )}
            </div>
          </div>

          {/* Candidate Zones & Anchor Evidence Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Candidate Zones Ranking */}
            <div className="p-6 rounded-xl bg-white border border-slate-200/80 shadow-sm space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <Layers className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Candidate Zones Ranking
                </h3>
              </div>

              {searchResult.candidates && searchResult.candidates.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="px-3 py-2">Rank</th>
                        <th className="px-3 py-2">Zone Name</th>
                        <th className="px-3 py-2">Score</th>
                        <th className="px-3 py-2">Probability</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {searchResult.candidates.map((c, idx) => (
                        <tr
                          key={c.zone_id ?? idx}
                          className={idx === 0 ? 'bg-indigo-50/50 font-semibold' : ''}
                        >
                          <td className="px-3 py-2 font-mono">#{idx + 1}</td>
                          <td className="px-3 py-2 text-slate-900">
                            {c.zone_name || `Zone #${c.zone_id}`}
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-700">{c.score.toFixed(3)}</td>
                          <td className="px-3 py-2 font-mono text-indigo-700">
                            {(c.probability * 100).toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">No candidate zones resolved.</p>
              )}
            </div>

            {/* Anchor Evidence Breakdown */}
            <div className="p-6 rounded-xl bg-white border border-slate-200/80 shadow-sm space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <Radio className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Signal Evidence (Anchor Sightings)
                </h3>
              </div>

              {searchResult.evidence && searchResult.evidence.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="px-3 py-2">Anchor ID</th>
                        <th className="px-3 py-2">Smoothed RSSI</th>
                        <th className="px-3 py-2">Samples</th>
                        <th className="px-3 py-2">Age</th>
                        <th className="px-3 py-2">Score</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      {searchResult.evidence.map((ev) => (
                        <tr key={ev.anchor_id} className="hover:bg-slate-50/50">
                          <td className="px-3 py-2 font-semibold text-slate-800">
                            {ev.anchor_id}
                          </td>
                          <td className="px-3 py-2 font-bold text-slate-900">
                            {ev.smoothed_rssi} dBm
                          </td>
                          <td className="px-3 py-2 text-slate-600">{ev.samples_count}</td>
                          <td className="px-3 py-2 text-slate-600">{ev.age_s}s</td>
                          <td className="px-3 py-2 text-indigo-700 font-bold">
                            {ev.anchor_score.toFixed(3)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">No anchor sightings available.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
