import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  MapPin,
  Radio,
  Watch,
  Search,
  Activity,
  Server,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
} from 'lucide-react';
import {
  listZones,
  listAnchors,
  listDevices,
  getFleetHealth,
  getServerHealth,
  seedVenue,
} from '../api/endpoints';
import { PageHeader, LoadingSpinner } from '../components/common/UIFeedback';
import { Modal } from '../components/common/Modal';
import { getErrorMessage } from '../api/client';
import toast from 'react-hot-toast';

export const OverviewPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [seedModalOpen, setSeedModalOpen] = useState(false);
  const [seedJson, setSeedJson] = useState(
    JSON.stringify(
      {
        zones: [
          {
            id: 1,
            name: 'Zone 1 - Main Concourse',
            centroid_x: 10.0,
            centroid_y: 10.0,
            metadata: { shape: 'square', side_m: 20.0 },
            adjacent_to: [2],
          },
          {
            id: 2,
            name: 'Zone 2 - West Corridor',
            centroid_x: 30.0,
            centroid_y: 10.0,
            metadata: { shape: 'corridor' },
            adjacent_to: [1],
          },
        ],
        anchors: [
          {
            anchor_id: 'ANCHOR-LAPTOP-01',
            base_url: 'http://localhost:5001',
            zone_id: 1,
            x: 10.0,
            y: 10.0,
            floor: 0,
            enabled: true,
            metadata: {},
          },
        ],
        devices: [
          {
            device_id: 'KINBEACON-PHONE1',
            display_name: 'Child Wristband 01',
            guardian_ref: 'Guardian-Alice',
            status: 'ACTIVE',
            metadata: {},
          },
        ],
      },
      null,
      2
    )
  );

  const { data: zones, isLoading: zonesLoading } = useQuery({
    queryKey: ['zones'],
    queryFn: listZones,
  });

  const { data: anchors, isLoading: anchorsLoading } = useQuery({
    queryKey: ['anchors'],
    queryFn: listAnchors,
  });

  const { data: devices, isLoading: devicesLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: listDevices,
  });

  const { data: fleetHealth, isLoading: fleetLoading } = useQuery({
    queryKey: ['fleet-health'],
    queryFn: getFleetHealth,
    refetchInterval: 10000,
  });

  const { data: serverHealth } = useQuery({
    queryKey: ['server-health'],
    queryFn: getServerHealth,
  });

  const seedMutation = useMutation({
    mutationFn: seedVenue,
    onSuccess: (res) => {
      toast.success(
        `Seeded: ${res.zones_created} zones, ${res.anchors_created} anchors (${res.verified_anchors} verified), ${res.devices_created} devices!`
      );
      queryClient.invalidateQueries({ queryKey: ['zones'] });
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      queryClient.invalidateQueries({ queryKey: ['fleet-health'] });
      setSeedModalOpen(false);
    },
    onError: (err) => {
      toast.error(`Seed failed: ${getErrorMessage(err)}`);
    },
  });

  const handleSeedSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = JSON.parse(seedJson);
      seedMutation.mutate(payload);
    } catch {
      toast.error('Invalid JSON format');
    }
  };

  const isLoading = zonesLoading || anchorsLoading || devicesLoading || fleetLoading;

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Overview"
        description="Real-time monitoring of zones, BLE anchors, registered wearables, and fleet connectivity."
      >
        <button
          onClick={() => setSeedModalOpen(true)}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm transition-colors"
        >
          <UploadCloud className="w-4 h-4 text-slate-500" />
          <span>Seed Venue</span>
        </button>
        <Link
          to="/search"
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors"
        >
          <Search className="w-4 h-4" />
          <span>Locate Device</span>
        </Link>
      </PageHeader>

      {isLoading ? (
        <LoadingSpinner message="Loading overview metrics..." />
      ) : (
        <>
          {/* Stat Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Link
              to="/zones"
              className="p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm hover:shadow transition-shadow block"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Venue Zones
                </span>
                <span className="p-2 rounded-lg bg-sky-50 text-sky-600">
                  <MapPin className="w-5 h-5" />
                </span>
              </div>
              <div className="mt-2 text-3xl font-bold text-slate-900">
                {zones?.length ?? 0}
              </div>
              <p className="mt-1 text-xs text-slate-500">Configured venue zones</p>
            </Link>

            <Link
              to="/anchors"
              className="p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm hover:shadow transition-shadow block"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Anchors
                </span>
                <span className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
                  <Radio className="w-5 h-5" />
                </span>
              </div>
              <div className="mt-2 text-3xl font-bold text-slate-900">
                {anchors?.length ?? 0}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {fleetHealth?.up ?? 0} online / active
              </p>
            </Link>

            <Link
              to="/devices"
              className="p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm hover:shadow transition-shadow block"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Tracked Wearables
                </span>
                <span className="p-2 rounded-lg bg-amber-50 text-amber-600">
                  <Watch className="w-5 h-5" />
                </span>
              </div>
              <div className="mt-2 text-3xl font-bold text-slate-900">
                {devices?.length ?? 0}
              </div>
              <p className="mt-1 text-xs text-slate-500">Registered BLE beacons</p>
            </Link>

            <Link
              to="/fleet"
              className="p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm hover:shadow transition-shadow block"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Fleet Status
                </span>
                <span className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
                  <Activity className="w-5 h-5" />
                </span>
              </div>
              <div className="mt-2 text-3xl font-bold text-emerald-600">
                {fleetHealth?.up ?? 0} / {fleetHealth?.total_anchors ?? 0}
              </div>
              <p className="mt-1 text-xs text-slate-500">Anchors UP & responsive</p>
            </Link>
          </div>

          {/* Fleet Health & System Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Fleet Status Card */}
            <div className="lg:col-span-2 p-6 rounded-xl bg-white border border-slate-200/80 shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-600" />
                  Anchor Fleet Health State
                </h2>
                <Link
                  to="/fleet"
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  View full fleet &rarr;
                </Link>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-100 text-center">
                  <div className="flex items-center justify-center gap-1.5 text-emerald-700 text-xs font-semibold mb-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>UP</span>
                  </div>
                  <div className="text-2xl font-bold text-emerald-800">
                    {fleetHealth?.up ?? 0}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-amber-50/70 border border-amber-100 text-center">
                  <div className="flex items-center justify-center gap-1.5 text-amber-700 text-xs font-semibold mb-1">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>DEGRADED</span>
                  </div>
                  <div className="text-2xl font-bold text-amber-800">
                    {fleetHealth?.degraded ?? 0}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-rose-50/70 border border-rose-100 text-center">
                  <div className="flex items-center justify-center gap-1.5 text-rose-700 text-xs font-semibold mb-1">
                    <XCircle className="w-3.5 h-3.5" />
                    <span>DOWN</span>
                  </div>
                  <div className="text-2xl font-bold text-rose-800">
                    {fleetHealth?.down ?? 0}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80 text-center">
                  <div className="flex items-center justify-center gap-1.5 text-slate-600 text-xs font-semibold mb-1">
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span>UNKNOWN</span>
                  </div>
                  <div className="text-2xl font-bold text-slate-700">
                    {fleetHealth?.unknown ?? 0}
                  </div>
                </div>
              </div>

              {fleetHealth && fleetHealth.anchors.length > 0 ? (
                <div className="mt-4 border border-slate-100 rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                      <tr>
                        <th className="px-3 py-2">Anchor ID</th>
                        <th className="px-3 py-2">Assigned Zone</th>
                        <th className="px-3 py-2">Health</th>
                        <th className="px-3 py-2">Verified</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      {fleetHealth.anchors.slice(0, 5).map((a) => (
                        <tr key={a.anchor_id} className="hover:bg-slate-50/50">
                          <td className="px-3 py-2 font-semibold text-slate-800">
                            {a.anchor_id}
                          </td>
                          <td className="px-3 py-2 font-sans text-slate-600">
                            {a.zone_id ? `Zone #${a.zone_id}` : 'Unassigned'}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                                a.health_state === 'UP'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : a.health_state === 'DEGRADED'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-rose-100 text-rose-800'
                              }`}
                            >
                              {a.health_state}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-sans">
                            {a.verified ? (
                              <span className="text-emerald-600 font-medium">✓ Verified</span>
                            ) : (
                              <span className="text-slate-400">✗ Unverified</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-slate-400 text-center py-4">
                  No anchors registered yet. Click &quot;Seed Venue&quot; or navigate to Anchors to register.
                </p>
              )}
            </div>

            {/* Central Server System Info */}
            <div className="p-6 rounded-xl bg-white border border-slate-200/80 shadow-sm space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <Server className="w-4 h-4 text-indigo-600" />
                <h2 className="text-base font-semibold text-slate-900">Server Info</h2>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-400 font-medium block">Application Name</span>
                  <span className="text-slate-800 font-semibold text-sm">
                    {serverHealth?.app || 'KinBeacon Central Server'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Status</span>
                  <span className="inline-flex items-center gap-1.5 text-emerald-700 font-semibold mt-0.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    Operational
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">API Version</span>
                  <span className="text-slate-700 font-mono">
                    {serverHealth?.version || '1.0.0'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Algorithm</span>
                  <span className="text-slate-700">
                    Pure Zone Engine (Recency Decay + Confidence D×F×E×C×K)
                  </span>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100">
                <Link
                  to="/search"
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold rounded-lg text-xs transition-colors"
                >
                  <Search className="w-4 h-4" />
                  <span>Start Device Search Demo &rarr;</span>
                </Link>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Seed Venue Modal */}
      <Modal
        isOpen={seedModalOpen}
        onClose={() => setSeedModalOpen(false)}
        title="Seed Venue Configuration"
        maxWidth="max-w-2xl"
      >
        <form onSubmit={handleSeedSubmit} className="space-y-4">
          <p className="text-xs text-slate-500">
            Bulk-initialize venue zones, anchors, and registered wearable devices in a single call via <code>POST /api/v1/admin/seed</code>.
          </p>
          <div>
            <textarea
              rows={12}
              value={seedJson}
              onChange={(e) => setSeedJson(e.target.value)}
              className="w-full p-3 font-mono text-xs border border-slate-300 rounded-lg bg-slate-900 text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setSeedModalOpen(false)}
              className="px-3 py-2 text-sm text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={seedMutation.isPending}
              className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 shadow-sm"
            >
              {seedMutation.isPending ? 'Seeding Venue...' : 'Execute Seed'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
