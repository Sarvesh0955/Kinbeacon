import { api } from './client';
import {
  ServerHealth,
  Zone,
  ZoneCreatePayload,
  Anchor,
  AnchorCreatePayload,
  AnchorUpdatePayload,
  AnchorVerificationResult,
  FleetHealthResponse,
  Device,
  DeviceCreatePayload,
  DeviceUpdatePayload,
  SearchRequestPayload,
  SearchResponse,
  VenueSeedPayload,
  VenueSeedResponse,
} from './types';

// Health Endpoints
export const getServerHealth = async (): Promise<ServerHealth> => {
  const { data } = await api.get<ServerHealth>('/health');
  return data;
};

export const getApiHealth = async (): Promise<ServerHealth> => {
  const { data } = await api.get<ServerHealth>('/api/v1/health');
  return data;
};

// Zones Endpoints
export const listZones = async (): Promise<Zone[]> => {
  const { data } = await api.get<Zone[]>('/api/v1/zones');
  return data;
};

export const getZone = async (zoneId: number): Promise<Zone> => {
  const { data } = await api.get<Zone>(`/api/v1/zones/${zoneId}`);
  return data;
};

export const createZone = async (payload: ZoneCreatePayload): Promise<Zone> => {
  const { data } = await api.post<Zone>('/api/v1/zones', payload);
  return data;
};

// Anchors Endpoints
export const listAnchors = async (): Promise<Anchor[]> => {
  const { data } = await api.get<Anchor[]>('/api/v1/anchors');
  return data;
};

export const getAnchor = async (anchorId: string): Promise<Anchor> => {
  const { data } = await api.get<Anchor>(`/api/v1/anchors/${anchorId}`);
  return data;
};

export const createAnchor = async (
  payload: AnchorCreatePayload,
  verify: boolean = true
): Promise<Anchor> => {
  const { data } = await api.post<Anchor>('/api/v1/anchors', payload, {
    params: { verify },
  });
  return data;
};

export const updateAnchor = async (
  anchorId: string,
  payload: AnchorUpdatePayload,
  verify: boolean = true
): Promise<Anchor> => {
  const { data } = await api.patch<Anchor>(`/api/v1/anchors/${anchorId}`, payload, {
    params: { verify },
  });
  return data;
};

export const verifyAnchor = async (
  anchorId: string
): Promise<AnchorVerificationResult> => {
  const { data } = await api.post<AnchorVerificationResult>(
    `/api/v1/anchors/${anchorId}/verify`
  );
  return data;
};

export const deleteAnchor = async (anchorId: string): Promise<void> => {
  await api.delete(`/api/v1/anchors/${anchorId}`);
};

export const getFleetHealth = async (): Promise<FleetHealthResponse> => {
  const { data } = await api.get<FleetHealthResponse>('/api/v1/anchors/status');
  return data;
};

// Devices Endpoints
export const listDevices = async (): Promise<Device[]> => {
  const { data } = await api.get<Device[]>('/api/v1/devices');
  return data;
};

export const getDevice = async (deviceId: string): Promise<Device> => {
  const { data } = await api.get<Device>(`/api/v1/devices/${deviceId}`);
  return data;
};

export const createDevice = async (payload: DeviceCreatePayload): Promise<Device> => {
  const { data } = await api.post<Device>('/api/v1/devices', payload);
  return data;
};

export const updateDevice = async (
  deviceId: string,
  payload: DeviceUpdatePayload
): Promise<Device> => {
  const { data } = await api.patch<Device>(`/api/v1/devices/${deviceId}`, payload);
  return data;
};

export const deleteDevice = async (deviceId: string): Promise<void> => {
  await api.delete(`/api/v1/devices/${deviceId}`);
};

// Searches Endpoints
export const executeSearch = async (
  payload: SearchRequestPayload
): Promise<SearchResponse> => {
  const { data } = await api.post<SearchResponse>('/api/v1/searches', payload);
  return data;
};

export const getSearch = async (searchId: string): Promise<SearchResponse> => {
  const { data } = await api.get<SearchResponse>(`/api/v1/searches/${searchId}`);
  return data;
};

export const getDeviceSearches = async (
  deviceId: string,
  limit: number = 10
): Promise<SearchResponse[]> => {
  const { data } = await api.get<SearchResponse[]>(
    `/api/v1/devices/${deviceId}/searches`,
    { params: { limit } }
  );
  return data;
};

// Admin Endpoints
export const seedVenue = async (
  payload: VenueSeedPayload
): Promise<VenueSeedResponse> => {
  const { data } = await api.post<VenueSeedResponse>('/api/v1/admin/seed', payload);
  return data;
};
