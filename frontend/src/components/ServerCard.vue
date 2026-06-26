<script setup lang="ts">
import { computed } from "vue";
import type { ServerStatus } from "../types/server";
import { Cpu, MemoryStick, HardDrive, Clock, AlertTriangle, Network, Activity, ServerCog } from "lucide-vue-next";

interface Props {
  server: ServerStatus;
}

const props = defineProps<Props>();

const statusColor = computed(() => {
  const colors = {
    normal: "border-l-emerald-500 bg-emerald-950/20",
    warning: "border-l-amber-500 bg-amber-950/20",
    critical: "border-l-red-500 bg-red-950/20",
    offline: "border-l-slate-500 bg-slate-800/40",
  };
  return colors[props.server.overall_status] || colors.normal;
});

const statusBadge = computed(() => {
  const badges = {
    normal: { text: "正常", class: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" },
    warning: { text: "警告", class: "bg-amber-500/20 text-amber-400 border-amber-500/30" },
    critical: { text: "严重", class: "bg-red-500/20 text-red-400 border-red-500/30" },
    offline: { text: "离线", class: "bg-slate-500/20 text-slate-300 border-slate-500/30" },
  };
  return badges[props.server.overall_status] || badges.normal;
});

const ok = computed(() => props.server.collection_status === "success");

function thrColor(pct: number): string {
  if (!ok.value) return "text-slate-400";
  if (pct >= 90) return "text-red-400";
  if (pct >= 80) return "text-amber-400";
  return "text-emerald-400";
}

const cpuColor = computed(() => thrColor(props.server.cpu_usage));
const memColor = computed(() => thrColor(props.server.memory.usage_percent));

const m = computed(() => props.server.metrics || ({} as any));

const swapPct = computed(() => {
  const t = m.value.swap_total_mb || 0;
  return t > 0 ? ((m.value.swap_used_mb || 0) / t) * 100 : 0;
});
const swapText = computed(() => {
  const t = m.value.swap_total_mb || 0;
  if (t <= 0) return "无 Swap";
  const u = m.value.swap_used_mb || 0;
  return `${swapPct.value.toFixed(0)}% · ${(u / 1024).toFixed(1)}/${(t / 1024).toFixed(1)}G`;
});
const loadText = computed(() => {
  const v = m.value;
  if (!v || (!v.load1 && !v.load5 && !v.load15)) return "-";
  return `${(v.load1 || 0).toFixed(2)} ${(v.load5 || 0).toFixed(2)} ${(v.load15 || 0).toFixed(2)}`;
});
const coreText = computed(() => {
  const c = props.server.cpu_cores || 0;
  return c > 0 ? `${c} 核` : "-";
});
const extraInfo = computed(() => {
  const v = m.value;
  const parts: string[] = [];
  if (v && v.tcp_conns) parts.push(`TCP ${v.tcp_conns}`);
  if (v && v.procs_total) parts.push(`进程 ${v.procs_total}`);
  return parts.join(" · ") || "-";
});

function fmtBytes(b: number): string {
  if (!b) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB", "PB"];
  let i = 0;
  let n = b;
  while (n >= 1024 && i < u.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(i < 2 ? 0 : 1)} ${u[i]}`;
}
const netRx = computed(() => fmtBytes(m.value.net_rx_bytes || 0));
const netTx = computed(() => fmtBytes(m.value.net_tx_bytes || 0));

const hostnameDisplay = computed(
  () => props.server.real_hostname || props.server.hostname || props.server.ip
);
const osLine = computed(() => {
  const parts = [props.server.os_version];
  if (props.server.kernel) parts.push(props.server.kernel);
  return parts.filter(Boolean).join(" · ") || "-";
});

const memorySizeText = computed(() => {
  const sizeGb = props.server.hardware?.memory_size_gb || props.server.memory.total_gb || 0;
  if (!sizeGb) return "-";
  return Number.isInteger(sizeGb) ? `${sizeGb} GB` : `${sizeGb.toFixed(1)} GB`;
});
const storageDevices = computed(() => props.server.hardware?.storage_devices || []);
const gpuDevices = computed(() => props.server.hardware?.gpu_devices || []);

function formatSizeGb(sizeGb: number): string {
  if (!sizeGb) return "-";
  return Number.isInteger(sizeGb) ? `${sizeGb} GB` : `${sizeGb.toFixed(1)} GB`;
}

// 全部磁盘：系统盘 + 数据盘（带 余/共 详情）
const diskLines = computed(() => {
  const lines: { label: string; text: string; pct: number }[] = [];
  const sys = props.server.system_disk_text;
  if (sys && sys !== "获取失败") lines.push({ label: "/", text: sys, pct: diskPct(sys) });
  const data = props.server.data_disk_text;
  if (data && data !== "无数据盘" && data !== "获取失败") {
    for (const raw of data.split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      const idx = line.indexOf(":");
      const label = idx > 0 ? line.slice(0, idx) : line.slice(0, line.indexOf(" "));
      lines.push({ label, text: line.replace(label + ":", "").trim() || line, pct: diskPct(line) });
    }
  }
  return lines;
});

function diskPct(line: string): number {
  const match = line.match(/(\d+(?:\.\d+)?)\s*%/);
  return match ? parseFloat(match[1]) : 0;
}
function diskColor(pct: number): string {
  if (pct >= 95) return "text-red-400";
  if (pct >= 85) return "text-amber-400";
  return "text-gray-300";
}
</script>

<template>
  <div
    :class="[
      'relative rounded-lg border-l-4 p-4 transition-all duration-300 hover:scale-[1.02] hover:shadow-xl flex flex-col',
      statusColor,
    ]"
  >
    <!-- 状态徽章 -->
    <div class="absolute top-3 right-3 flex gap-1.5">
      <span
        v-if="server.group_name"
        class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-600/30 text-slate-300 border border-slate-500/30"
      >
        {{ server.group_name }}
      </span>
      <span :class="['px-2 py-0.5 rounded-full text-xs font-medium border', statusBadge.class]">
        {{ statusBadge.text }}
      </span>
    </div>

    <!-- 标题 -->
    <div class="mb-3 pr-24">
      <h3 class="text-base font-bold text-white font-mono leading-tight">{{ server.ip }}</h3>
      <p class="text-xs text-cyan-300/80 mt-0.5 font-mono truncate">{{ hostnameDisplay }}</p>
      <p class="text-[11px] text-gray-500 mt-0.5 truncate">{{ osLine }}</p>
    </div>

    <!-- 核心指标 4 列 -->
    <div class="grid grid-cols-4 gap-2 mb-3">
      <div class="text-center">
        <p class="text-[10px] text-gray-500">CPU</p>
        <p :class="['text-sm font-mono font-bold', cpuColor]">{{ ok ? server.cpu_usage.toFixed(1) + '%' : '-' }}</p>
      </div>
      <div class="text-center">
        <p class="text-[10px] text-gray-500">内存</p>
        <p :class="['text-sm font-mono font-bold', memColor]">{{ ok ? server.memory.usage_percent.toFixed(1) + '%' : '-' }}</p>
      </div>
      <div class="text-center">
        <p class="text-[10px] text-gray-500">Swap</p>
        <p :class="['text-xs font-mono font-bold', thrColor(swapPct)]">{{ swapText.split(' · ')[0] }}</p>
      </div>
      <div class="text-center">
        <p class="text-[10px] text-gray-500">负载</p>
        <p class="text-xs font-mono font-bold text-gray-300">{{ loadText.split(' ')[0] }}</p>
      </div>
    </div>

    <!-- 详情行 -->
    <div class="space-y-1 text-[11px] text-gray-400 mb-3">
      <div class="flex justify-between gap-2">
        <span class="flex items-center gap-1"><MemoryStick :size="12" />内存</span>
        <span class="text-gray-300 font-mono truncate">{{ server.memory_text || '-' }}</span>
      </div>
      <div class="flex justify-between gap-2">
        <span class="flex items-center gap-1"><Activity :size="12" />Swap</span>
        <span class="text-gray-300 font-mono truncate">{{ swapText }}</span>
      </div>
      <div class="flex justify-between gap-2">
        <span class="flex items-center gap-1"><Cpu :size="12" />负载(1/5/15)</span>
        <span class="text-gray-300 font-mono truncate">{{ loadText }} · {{ coreText }}</span>
      </div>
      <div class="flex justify-between gap-2">
        <span class="flex items-center gap-1"><Clock :size="12" />运行</span>
        <span class="text-gray-300 font-mono truncate">{{ server.uptime || '-' }} · {{ extraInfo }}</span>
      </div>
    </div>

    <!-- 磁盘（全部，带余/共） -->
    <div v-if="diskLines.length > 0" class="mb-3 pt-2 border-t border-gray-700/50">
      <p class="text-[10px] text-gray-500 mb-1 flex items-center gap-1"><HardDrive :size="11" />磁盘</p>
      <div v-for="(d, i) in diskLines.slice(0, 6)" :key="i" class="flex justify-between text-[11px] mb-0.5">
        <span class="text-gray-500 font-mono truncate max-w-[40%]">{{ d.label }}</span>
        <span :class="['font-mono truncate', diskColor(d.pct)]">{{ d.text }}</span>
      </div>
    </div>

    <!-- 网络 -->
    <div v-if="ok && (m.net_rx_bytes || m.net_tx_bytes)" class="mb-3 pt-2 border-t border-gray-700/50">
      <p class="text-[10px] text-gray-500 mb-1 flex items-center gap-1"><Network :size="11" />网卡累计</p>
      <div class="flex justify-between text-[11px]">
        <span class="text-emerald-400 font-mono">↓ {{ netRx }}</span>
        <span class="text-sky-400 font-mono">↑ {{ netTx }}</span>
      </div>
    </div>

    <!-- 硬件 -->
    <div class="mt-auto pt-2 border-t border-gray-700/50 space-y-1 text-[11px]">
      <div class="flex justify-between gap-2">
        <span class="text-gray-500 flex items-center gap-1"><ServerCog :size="11" />内存/硬盘/显卡</span>
      </div>
      <div class="text-gray-400 pl-1 space-y-0.5">
        <p><span class="text-gray-500">内存</span> {{ memorySizeText }}</p>
        <template v-if="storageDevices.length > 0">
          <p v-for="(d, i) in storageDevices.slice(0, 3)" :key="`s${i}`">
            <span class="text-gray-500">盘</span> {{ d.model || d.name }} · {{ formatSizeGb(d.size_gb) }}
          </p>
        </template>
        <template v-if="gpuDevices.length > 0">
          <p v-for="(g, i) in gpuDevices.slice(0, 2)" :key="`g${i}`">
            <span class="text-gray-500">卡</span> {{ g.name }}<span v-if="g.driver"> · {{ g.driver }}</span><span v-if="g.memory_text"> · {{ g.memory_text }}</span>
          </p>
        </template>
      </div>
    </div>

    <!-- 采集未完成 -->
    <div v-if="!ok" class="mt-3 rounded-md border border-slate-600/50 bg-slate-900/40 p-2">
      <div class="flex items-center gap-2 text-slate-300">
        <AlertTriangle :size="14" />
        <span class="text-xs font-medium">采集未完成</span>
      </div>
      <p class="mt-1 text-[11px] leading-5 text-slate-400 break-all">{{ server.collection_error || '当前未获取到最新数据' }}</p>
    </div>

    <!-- 最后更新 -->
    <div class="absolute bottom-2 right-3 text-[10px] text-gray-600">
      {{ server.last_update ? new Date(server.last_update).toLocaleTimeString() : '-' }}
    </div>
  </div>
</template>
