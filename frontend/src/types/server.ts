export interface DiskInfo {
  mount_point: string;
  size_gb: number;
  used_gb: number;
  usage_percent: number;
  status: "normal" | "warning" | "critical";
}

export interface MemoryInfo {
  total_gb: number;
  used_gb: number;
  usage_percent: number;
  status: "normal" | "warning" | "critical";
}

export interface StorageDeviceInfo {
  name: string;
  model: string;
  size_gb: number;
}

export interface GpuInfo {
  name: string;
  vendor: string;
  memory_mb: number;
  memory_text: string;
  driver: string;
}

export interface HardwareInfo {
  memory_size_gb: number;
  storage_devices: StorageDeviceInfo[];
  gpu_devices: GpuInfo[];
}

export interface MetricsInfo {
  swap_total_mb: number;
  swap_used_mb: number;
  load1: number;
  load5: number;
  load15: number;
  procs_total: number;
  tcp_conns: number;
  net_rx_bytes: number;
  net_tx_bytes: number;
}

export interface ServerStatus {
  id: number;
  ip: string;
  hostname: string;
  os_type: string;
  group_name: string;
  os_version: string;
  uptime: string;
  cpu_usage: number;
  cpu_text: string;
  memory: MemoryInfo;
  memory_text: string;
  disks: DiskInfo[];
  system_disk_text: string;
  data_disk_text: string;
  cpu_cores: number;
  kernel: string;
  real_hostname: string;
  metrics: MetricsInfo;
  hardware: HardwareInfo;
  last_update: string | null;
  overall_status: "normal" | "warning" | "critical" | "offline";
  collection_status: "success" | "failed" | "unreachable" | "missing";
  collection_error: string;
}

export interface ServerListResponse {
  code: number;
  data: ServerStatus[];
  meta: {
    total: number;
    online: number;
    alert_count: number;
  };
}

export interface CollectRequest {
  group?: string;
  force?: boolean;
}

export interface CollectResponse {
  code: number;
  message: string;
  task_id: string;
  estimated_time: string;
  total_count: number;
  success_count: number;
  failed_count: number;
}
