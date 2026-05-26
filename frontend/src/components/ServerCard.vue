<script setup lang="ts">
import { computed } from "vue";
import type { ServerStatus } from "../types/server";
import { Activity, Cpu, HardDrive, Clock, AlertTriangle } from "lucide-vue-next";

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

const cpuColor = computed(() => {
  if (props.server.collection_status !== "success") return "text-slate-400";
  if (props.server.cpu_usage >= 90) return "text-red-400";
  if (props.server.cpu_usage >= 80) return "text-amber-400";
  return "text-emerald-400";
});

const memoryColor = computed(() => {
  if (props.server.collection_status !== "success") return "text-slate-400";
  if (props.server.memory.usage_percent >= 90) return "text-red-400";
  if (props.server.memory.usage_percent >= 80) return "text-amber-400";
  return "text-emerald-400";
});
</script>

<template>
  <div
    :class="[
      'relative rounded-lg border-l-4 p-5 transition-all duration-300 hover:scale-[1.02] hover:shadow-xl',
      statusColor,
    ]"
  >
    <!-- 状态徽章 -->
    <div class="absolute top-3 right-3">
      <span
        :class="[
          'px-2 py-0.5 rounded-full text-xs font-medium border',
          statusBadge.class,
        ]"
      >
        {{ statusBadge.text }}
      </span>
    </div>

    <!-- 服务器基本信息 -->
    <div class="mb-4">
      <h3 class="text-lg font-bold text-white font-mono">{{ server.ip }}</h3>
      <p class="text-sm text-gray-400 mt-1">{{ server.os_version }}</p>
    </div>

    <!-- 监控指标网格 -->
    <div class="grid grid-cols-2 gap-3">
      <!-- CPU 使用率 -->
      <div class="flex items-center space-x-2">
        <Cpu :size="16" :class="cpuColor" />
        <div>
          <p class="text-xs text-gray-500">CPU</p>
          <p :class="['text-sm font-mono font-bold', cpuColor]">
            {{ server.cpu_usage.toFixed(1) }}%
          </p>
        </div>
      </div>

      <!-- 内存使用率 -->
      <div class="flex items-center space-x-2">
        <HardDrive :size="16" :class="memoryColor" />
        <div>
          <p class="text-xs text-gray-500">内存</p>
          <p :class="['text-sm font-mono font-bold', memoryColor]">
            {{ server.memory.usage_percent.toFixed(1) }}%
          </p>
        </div>
      </div>

      <!-- 运行时间 -->
      <div class="flex items-center space-x-2 col-span-2">
        <Clock :size="16" class="text-blue-400" />
        <div>
          <p class="text-xs text-gray-500">运行时间</p>
          <p class="text-sm font-mono text-gray-300">{{ server.uptime || "-" }}</p>
        </div>
      </div>
    </div>

    <div v-if="server.collection_status !== 'success'" class="mt-3 rounded-md border border-slate-600/50 bg-slate-900/40 p-3">
      <div class="flex items-center space-x-2 text-slate-300">
        <AlertTriangle :size="16" />
        <span class="text-sm font-medium">采集未完成</span>
      </div>
      <p class="mt-2 text-xs leading-5 text-slate-400 break-all">
        {{ server.collection_error || "当前未获取到最新数据" }}
      </p>
    </div>

    <!-- 磁盘信息（简化显示） -->
    <div v-if="server.disks.length > 0" class="mt-3 pt-3 border-t border-gray-700/50">
      <div v-for="disk in server.disks.slice(0, 2)" :key="disk.mount_point" class="flex justify-between text-xs mb-1">
        <span class="text-gray-500">{{ disk.mount_point }}</span>
        <span :class="disk.status === 'critical' ? 'text-red-400' : disk.status === 'warning' ? 'text-amber-400' : 'text-gray-300'">
          {{ disk.usage_percent.toFixed(1) }}%
        </span>
      </div>
    </div>

    <!-- 最后更新时间 -->
    <div class="absolute bottom-3 right-3 text-xs text-gray-600">
      {{ server.last_update ? new Date(server.last_update).toLocaleTimeString() : '-' }}
    </div>
  </div>
</template>
