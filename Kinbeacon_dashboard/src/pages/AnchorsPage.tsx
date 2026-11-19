import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Radio, CheckCircle, RefreshCw, Trash2, Edit2, ShieldAlert } from 'lucide-react';
import {
  listAnchors,
  createAnchor,
  updateAnchor,
  deleteAnchor,
  verifyAnchor,
  listZones,
} from '../api/endpoints';
import { PageHeader, LoadingSpinner, EmptyState, ErrorBanner } from '../components/common/UIFeedback';
import { Modal, ConfirmDialog } from '../components/common/Modal';
import { StatusBadge } from '../components/common/StatusBadge';
import { Anchor, AnchorVerificationResult } from '../api/types';
import { getErrorMessage } from '../api/client';
import toast from 'react-hot-toast';

export const AnchorsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [editingAnchor, setEditingAnchor] = useState<Anchor | null>(null);
  const [deletingAnchorId, setDeletingAnchorId] = useState<string | null>(null);
  const [verificationResult, setVerificationResult] = useState<AnchorVerificationResult | null>(null);

  // Form states
  const [anchorId, setAnchorId] = useState('');
  const [baseUrl, setBaseUrl] = useState('http://localhost:5001');
  const [zoneId, setZoneId] = useState<string>('');
  const [coordX, setCoordX] = useState('0.0');
  const [coordY, setCoordY] = useState('0.0');
  const [floor, setFloor] = useState('0');
  const [enabled, setEnabled] = useState(true);
  const [autoVerify, setAutoVerify] = useState(true);

  const { data: anchors, isLoading, error } = useQuery({
    queryKey: ['anchors'],
    queryFn: listAnchors,
  });

  const { data: zones } = useQuery({
    queryKey: ['zones'],
    queryFn: listZones,
  });

  // Create Mutation
  const createMutation = useMutation({
    mutationFn: (data: { verify: boolean }) =>
      createAnchor(
        {
          anchor_id: anchorId.trim(),
          base_url: baseUrl.trim(),
          zone_id: zoneId ? parseInt(zoneId, 10) : null,
          x: parseFloat(coordX) || 0.0,
          y: parseFloat(coordY) || 0.0,
          floor: parseInt(floor, 10) || 0,
          enabled,
        },
        data.verify
      ),
    onSuccess: (newAnchor) => {
      toast.success(`Anchor ${newAnchor.anchor_id} registered! (Verified: ${newAnchor.verified ? 'Yes' : 'No'})`);
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
      queryClient.invalidateQueries({ queryKey: ['fleet-health'] });
      setRegisterModalOpen(false);
      resetForm();
    },
    onError: (err) => {
      toast.error(`Registration failed: ${getErrorMessage(err)}`);
    },
  });

  // Update Mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, verify }: { id: string; verify: boolean }) =>
      updateAnchor(
        id,
        {
          base_url: baseUrl.trim(),
          zone_id: zoneId ? parseInt(zoneId, 10) : null,
          x: parseFloat(coordX) || 0.0,
          y: parseFloat(coordY) || 0.0,
          floor: parseInt(floor, 10) || 0,
          enabled,
        },
        verify
      ),
    onSuccess: (updated) => {
      toast.success(`Anchor ${updated.anchor_id} updated!`);
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
      queryClient.invalidateQueries({ queryKey: ['fleet-health'] });
      setEditingAnchor(null);
    },
    onError: (err) => {
      toast.error(`Update failed: ${getErrorMessage(err)}`);
    },
  });

  // Verify Mutation
  const verifyMutation = useMutation({
    mutationFn: (id: string) => verifyAnchor(id),
    onSuccess: (result) => {
      setVerificationResult(result);
      if (result.verified) {
        toast.success(`Anchor verified! Scanner: ${result.ble_scanner || 'running'}`);
      } else {
        toast.error(`Verification failed: ${result.message}`);
      }
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
      queryClient.invalidateQueries({ queryKey: ['fleet-health'] });
    },
    onError: (err) => {
      toast.error(`Verification error: ${getErrorMessage(err)}`);
    },
  });

  // Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAnchor(id),
    onSuccess: () => {
      toast.success('Anchor removed');
      queryClient.invalidateQueries({ queryKey: ['anchors'] });
      queryClient.invalidateQueries({ queryKey: ['fleet-health'] });
      setDeletingAnchorId(null);
    },
    onError: (err) => {
      toast.error(`Delete failed: ${getErrorMessage(err)}`);
    },
  });

  const resetForm = () => {
    setAnchorId('');
    setBaseUrl('http://localhost:5001');
    setZoneId(zones && zones.length > 0 ? zones[0].id.toString() : '');
    setCoordX('0.0');
    setCoordY('0.0');
    setFloor('0');
    setEnabled(true);
    setAutoVerify(true);
  };

  const openEdit = (a: Anchor) => {
    setAnchorId(a.anchor_id);
    setBaseUrl(a.base_url);
    setZoneId(a.zone_id ? a.zone_id.toString() : '');
    setCoordX(a.x.toString());
    setCoordY(a.y.toString());
    setFloor(a.floor.toString());
    setEnabled(a.enabled);
    setAutoVerify(true);
    setEditingAnchor(a);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Anchor Fleet Management"
        description="Register and verify Bluetooth LE scanner anchors distributed across venue zones."
      >
        <button
          onClick={() => {
            resetForm();
            setRegisterModalOpen(true);
          }}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Register Anchor</span>
        </button>
      </PageHeader>

      {error && <ErrorBanner message={getErrorMessage(error)} />}

      {isLoading ? (
        <LoadingSpinner message="Loading anchor fleet..." />
      ) : !anchors || anchors.length === 0 ? (
        <EmptyState
          title="No Anchors Registered"
          description="Register Bluetooth anchors to listen for wearable advertisement beacons in each zone."
          actionText="Register First Anchor"
          onAction={() => {
            resetForm();
            setRegisterModalOpen(true);
          }}
        />
      ) : (
        <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Anchor ID</th>
                  <th className="px-4 py-3">Base URL (LAN)</th>
                  <th className="px-4 py-3">Zone</th>
                  <th className="px-4 py-3">Position</th>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3">Verification</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {anchors.map((a) => {
                  const zone = zones?.find((z) => z.id === a.zone_id);
                  return (
                    <tr key={a.anchor_id} className="hover:bg-slate-50/50">
                      <td className="px-4 py-3 font-mono font-semibold text-slate-900 flex items-center gap-2">
                        <Radio className="w-4 h-4 text-indigo-600 shrink-0" />
                        <span>{a.anchor_id}</span>
                        {!a.enabled && (
                          <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.2 rounded font-sans">
                            Disabled
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-600">
                        {a.base_url}
                      </td>
                      <td className="px-4 py-3">
                        {zone ? (
                          <span className="text-xs font-medium text-slate-800">
                            #{zone.id} {zone.name}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Unassigned</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-600">
                        ({a.x}m, {a.y}m, F{a.floor})
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={a.health_state} />
                        {a.consecutive_failures > 0 && (
                          <span className="ml-1 text-[11px] text-rose-600 font-mono">
                            ({a.consecutive_failures} fail)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {a.verified ? (
                          <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                            <CheckCircle className="w-3.5 h-3.5" />
                            Verified
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-amber-700 font-medium">
                            <ShieldAlert className="w-3.5 h-3.5" />
                            Unverified
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-2">
                          <button
                            onClick={() => verifyMutation.mutate(a.anchor_id)}
                            disabled={verifyMutation.isPending}
                            title="Test HTTP connectivity & identity against anchor /api/v1/status"
                            className="p-1 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded"
                          >
                            <RefreshCw
                              className={`w-4 h-4 ${
                                verifyMutation.isPending ? 'animate-spin' : ''
                              }`}
                            />
                          </button>
                          <button
                            onClick={() => openEdit(a)}
                            title="Edit anchor"
                            className="p-1 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setDeletingAnchorId(a.anchor_id)}
                            title="Delete anchor"
                            className="p-1 text-slate-600 hover:text-rose-600 hover:bg-rose-50 rounded"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Register/Edit Anchor Modal */}
      <Modal
        isOpen={registerModalOpen || !!editingAnchor}
        onClose={() => {
          setRegisterModalOpen(false);
          setEditingAnchor(null);
        }}
        title={editingAnchor ? `Edit Anchor: ${editingAnchor.anchor_id}` : 'Register New BLE Anchor'}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (editingAnchor) {
              updateMutation.mutate({ id: editingAnchor.anchor_id, verify: autoVerify });
            } else {
              createMutation.mutate({ verify: autoVerify });
            }
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Anchor ID *
            </label>
            <input
              type="text"
              required
              disabled={!!editingAnchor}
              value={anchorId}
              onChange={(e) => setAnchorId(e.target.value)}
              placeholder="e.g. ANCHOR-LAPTOP-01"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Must match the exact <code>--anchor-id</code> argument used by the Anchor app.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Base URL (HTTP LAN Address) *
            </label>
            <input
              type="text"
              required
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="e.g. http://192.168.1.50:5001 or http://localhost:5001"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Assigned Zone
            </label>
            <select
              value={zoneId}
              onChange={(e) => setZoneId(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">(Unassigned)</option>
              {zones?.map((z) => (
                <option key={z.id} value={z.id}>
                  #{z.id} {z.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Coord X (m)
              </label>
              <input
                type="number"
                step="0.1"
                value={coordX}
                onChange={(e) => setCoordX(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Coord Y (m)
              </label>
              <input
                type="number"
                step="0.1"
                value={coordY}
                onChange={(e) => setCoordY(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Floor
              </label>
              <input
                type="number"
                value={floor}
                onChange={(e) => setFloor(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono"
              />
            </div>
          </div>

          <div className="space-y-2 pt-1 border-t border-slate-100">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded"
              />
              <span className="text-sm text-slate-700 font-medium">Enabled in Search Fan-out</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={autoVerify}
                onChange={(e) => setAutoVerify(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded"
              />
              <span className="text-sm text-slate-700 font-medium">
                Verify via <code>/api/v1/status</code> on save
              </span>
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                setRegisterModalOpen(false);
                setEditingAnchor(null);
              }}
              className="px-3 py-2 text-sm text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
              className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save Anchor'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Verification Result Modal */}
      {verificationResult && (
        <Modal
          isOpen={!!verificationResult}
          onClose={() => setVerificationResult(null)}
          title={`Verification: ${verificationResult.anchor_id}`}
        >
          <div className="space-y-3 text-sm">
            <div
              className={`p-4 rounded-lg border ${
                verificationResult.verified
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : 'bg-rose-50 border-rose-200 text-rose-900'
              }`}
            >
              <div className="font-bold flex items-center gap-2">
                {verificationResult.verified ? (
                  <>
                    <CheckCircle className="w-5 h-5 text-emerald-600" />
                    <span>Anchor Verified Successfully</span>
                  </>
                ) : (
                  <>
                    <ShieldAlert className="w-5 h-5 text-rose-600" />
                    <span>Verification Failed</span>
                  </>
                )}
              </div>
              <p className="text-xs mt-1">{verificationResult.message}</p>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Reported Anchor ID:</span>
                <span className="font-mono font-semibold">
                  {verificationResult.reported_anchor_id || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">BLE Scanner State:</span>
                <span className="font-mono font-semibold">
                  {verificationResult.ble_scanner || 'unknown'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">HTTP Status:</span>
                <span className="font-mono font-semibold">
                  {verificationResult.status_code || 'N/A'}
                </span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setVerificationResult(null)}
                className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
              >
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={!!deletingAnchorId}
        title="Remove Anchor"
        message={`Are you sure you want to remove anchor "${deletingAnchorId}"? It will no longer receive search fan-outs.`}
        confirmText="Remove Anchor"
        isDestructive={true}
        onConfirm={() => deletingAnchorId && deleteMutation.mutate(deletingAnchorId)}
        onCancel={() => setDeletingAnchorId(null)}
      />
    </div>
  );
};
