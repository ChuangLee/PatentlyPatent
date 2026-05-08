<script setup lang="ts">
import { computed, watch, onMounted } from 'vue';
import { theme as antdTheme } from 'ant-design-vue';
import { useUIStore } from '@/stores/ui';

const ui = useUIStore();

/**
 * 暗色模式同步：在 <html> 设置 data-theme，让 tokens.css 的
 * :root[data-theme='dark'] 覆盖块生效。
 */
function applyTheme(t: 'light' | 'dark') {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', t);
}

onMounted(() => applyTheme(ui.theme));
watch(() => ui.theme, (t) => applyTheme(t));

/**
 * 全局 antd 主题：把 design token 注入到 antd 组件，
 * 保证 Button / Input / Modal 等也走 indigo 紫蓝品牌色 + 圆角 10。
 *
 * token 字段命名遵循 ant-design-vue 4.x 主题 API
 * https://www.antdv.com/docs/vue/customize-theme
 */
const themeConfig = computed(() => ({
  algorithm:
    ui.theme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
  token: {
    colorPrimary: '#5B6CFF',
    colorSuccess: '#10B981',
    colorWarning: '#F59E0B',
    colorError: '#EF4444',
    colorInfo: '#3B82F6',
    colorTextBase: ui.theme === 'dark' ? '#F1F5F9' : '#111827',
    colorBgBase: ui.theme === 'dark' ? '#1E293B' : '#FFFFFF',
    colorBgLayout: ui.theme === 'dark' ? '#0F172A' : '#FAFBFC',
    colorBorder: ui.theme === 'dark' ? '#334155' : '#E5E7EB',
    colorBorderSecondary: ui.theme === 'dark' ? '#1E293B' : '#F3F4F6',
    borderRadius: 10,
    borderRadiusLG: 14,
    borderRadiusSM: 6,
    fontFamily:
      "Inter, 'PingFang SC', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif",
    fontSize: 14,
    controlHeight: 36,
    boxShadow:
      '0 4px 6px -1px rgba(17, 24, 39, 0.06), 0 2px 4px -2px rgba(17, 24, 39, 0.04)',
    boxShadowSecondary:
      '0 10px 15px -3px rgba(17, 24, 39, 0.08), 0 4px 6px -4px rgba(17, 24, 39, 0.04)',
    motionDurationMid: '200ms',
  },
  components: {
    Button: {
      controlHeight: 36,
      fontWeight: 500,
      primaryShadow: '0 1px 2px rgba(91, 108, 255, 0.12)',
    },
    Card: {
      borderRadiusLG: 14,
    },
    Modal: {
      borderRadiusLG: 14,
    },
    Input: {
      controlHeight: 36,
    },
    Menu: {
      itemBorderRadius: 8,
      itemSelectedBg: ui.theme === 'dark' ? '#312E81' : '#EEF0FF',
      itemSelectedColor: '#5B6CFF',
    },
  },
}));
</script>
<template>
  <a-config-provider :theme="themeConfig">
    <router-view />
  </a-config-provider>
</template>
