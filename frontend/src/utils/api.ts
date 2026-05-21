import axios from "axios";
import type { ServerListResponse, CollectResponse } from "../types/server";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    console.log(`🚀 [API] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    console.error("❌ [API Error]", error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// 获取所有服务器状态
export async function fetchServers(): Promise<ServerListResponse> {
  return api.get("/api/servers");
}

// 手动触发采集
export async function triggerCollect(): Promise<CollectResponse> {
  return api.post("/api/collect", { force: true });
}

// 获取历史记录
export async function fetchHistory(params?: {
  ip?: string;
  start_time?: string;
  end_time?: string;
  interval?: string;
}) {
  return api.get("/api/history", { params });
}

export default api;
