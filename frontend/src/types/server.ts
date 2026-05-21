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

export interface ServerStatus {
  id: number;
  ip: string;
  hostname: string;
  os_version: string;
  uptime: string;
  cpu_usage: number;
  memory: MemoryInfo;
  disks: DiskInfo[];
  last_update: string | null;
  overall_status: "normal" | "warning" | "critical";
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
}
