<script setup lang="ts">
import { theme as antdTheme } from 'ant-design-vue';

/**
 * 全局 antd 主题：把 design token 注入到 antd 组件，
 * 保证 Button / Input / Modal 等也走 indigo 紫蓝品牌色 + 圆角 10。
 *
 * token 字段命名遵循 ant-design-vue 4.x 主题 API
 * https://www.antdv.com/docs/vue/customize-theme
 */
const themeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    colorPrimary: '#5B6CFF',
    colorSuccess: '#10B981',
    colorWarning: '#F59E0B',
    colorError: '#EF4444',
    colorInfo: '#3B82F6',
    colorTextBase: '#111827',
    colorBgBase: '#FFFFFF',
    colorBgLayout: '#FAFBFC',
    colorBorder: '#E5E7EB',
    colorBorderSecondary: '#F3F4F6',
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
      itemSelectedBg: '#EEF0FF',
      itemSelectedColor: '#5B6CFF',
    },
  },
};
</script>
<template>
  <a-config-provider :theme="themeConfig">
    <router-view />
  </a-config-provider>
</template>
