// TypeScript interfaces mirroring KinBeacon backend schemas

export interface ServerHealth {
  status: string;
  app: string;
  version?: string;
  env?: string;
}

export interface Zone {
  id: number;
  name: string;
  centroid_x: number;
  centroid_y: number;
  metadata_json: Record<string, any>;
  created_at: string;
  adjacent_zone_ids: number[];
}

export interface ZoneCreatePayload {
  id?: number;
  name: string;
  centroid_x?: number;
  centroid_y?: number;
  metadata_json?: Record<string, any>;
  adjacent_to?: number[];
}

export interface Anchor {
  id: number;
  anchor_id: string;
  base_url: string;
  zone_id: number | null;
  x: number;
  y: number;
  floor: number;
  enabled: boolean;
  verified: boolean;
  verified_at: string | null;
  verify_note: string | null;
  health_state: 'UP' | 'DEGRADED' | 'DOWN' | 'UNKNOWN' | string;
  is_active: boolean;
  consecutive_failures: number;
  clock_offset_ms: number;
  metadata_json: Record<string, any>;
}

export interface AnchorCreatePayload {
  anchor_id: string;
  base_url: string;
  zone_id?: number | null;
  x?: number;
  y?: number;
  floor?: number;
  enabled?: boolean;
  metadata_json?: Record<string, any>;
}

export interface AnchorUpdatePayload {
  base_url?: string;
  zone_id?: number | null;
  x?: number;
  y?: number;
  floor?: number;
  enabled?: boolean;
  metadata_json?: Record<string, any>;
}

export interface AnchorVerificationResult {
  anchor_id: string;
  verified: boolean;
  status_code?: number;
  reported_anchor_id?: string;
  ble_scanner?: string;
  message: string;
}

export interface FleetAnchorSummary {
  anchor_id: string;
  zone_id: number | null;
  health_state: string;
  is_active: boolean;
  consecutive_failures: number;
  verified: boolean;
  last_success_at: string | null;
  last_failure_at: string | null;
}

export interface FleetHealthResponse {
  total_anchors: number;
  up: number;
  degraded: number;
  down: number;
  unknown: number;
  anchors: FleetAnchorSummary[];
}

export interface Device {
  id: number;
  device_id: string;
  display_name: string | null;
  guardian_ref: string | null;
  status: 'ACTIVE' | 'INACTIVE' | string;
  metadata_json: Record<string, any>;
  created_at: string;
}

export interface DeviceCreatePayload {
  device_id: string;
  display_name?: string | null;
  guardian_ref?: string | null;
  status?: string;
  metadata_json?: Record<string, any>;
}

export interface DeviceUpdatePayload {
  display_name?: string | null;
  guardian_ref?: string | null;
  status?: string;
  metadata_json?: Record<string, any>;
}

export interface ZoneCandidate {
  zone_id: number | null;
  zone_name: string | null;
  score: number;
  probability: number;
}

export interface AnchorEvidence {
  anchor_id: string;
  zone_id: number | null;
  samples_count: number;
  smoothed_rssi: number;
  latest_timestamp: string;
  age_s: number;
  anchor_score: number;
}

export interface AnchorsSummary {
  targeted: number;
  responded: number;
  timed_out: number;
  failed: number;
  unreachable: string[];
}

export interface EstimatedPosition {
  x: number;
  y: number;
  floor: number;
}

export interface ZoneRef {
  id: number;
  name: string;
}

export interface ZoneHistoryEntry extends ZoneRef {
  minute_start: string;
}

export interface SearchRequestPayload {
  device_id: string;
  max_age_s?: number;
  requested_by?: string;
}

export interface SearchResponse {
  search_id: string;
  device_id: string;
  status: 'COMPLETED' | 'PARTIAL' | 'FAILED' | string;
  zone: ZoneRef | null;
  zone_history?: ZoneHistoryEntry[];
  estimated_position: EstimatedPosition | null;
  confidence: number;
  confidence_label: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  last_seen_at: string | null;
  age_s: number | null;
  candidates: ZoneCandidate[];
  evidence: AnchorEvidence[];
  flags: string[];
  anchors: AnchorsSummary;
  started_at: string;
  completed_at: string | null;
}

export interface VenueSeedPayload {
  zones: Array<{
    id?: number;
    name: string;
    centroid?: { x: number; y: number };
    centroid_x?: number;
    centroid_y?: number;
    metadata?: Record<string, any>;
    adjacent_to?: number[];
  }>;
  anchors: Array<{
    anchor_id: string;
    base_url: string;
    zone_id?: number | null;
    x?: number;
    y?: number;
    floor?: number;
    enabled?: boolean;
    metadata?: Record<string, any>;
  }>;
  devices: Array<{
    device_id: string;
    display_name?: string;
    guardian_ref?: string;
    status?: string;
    metadata?: Record<string, any>;
  }>;
}

export interface VenueSeedResponse {
  zones_created: number;
  anchors_created: number;
  devices_created: number;
  adjacencies_created: number;
  verified_anchors: number;
}
