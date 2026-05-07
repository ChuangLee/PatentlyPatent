<script setup lang="ts">
import type { ClaimTier, Disclosure } from '@/types';

const props = defineProps<{
  claims: Disclosure['claims'];
  modelValue: ClaimTier;
}>();
const emit = defineEmits<{ (e: 'update:modelValue', t: ClaimTier): void }>();

const TIER_META: Record<ClaimTier, { label: string; size: string }> = {
  broad:  { label: '强档（特征 7±2）', size: '5±1' },
  medium: { label: '中档（特征 9±2）', size: '7±2' },
  narrow: { label: '弱档（特征 11±2）', size: '9±2' },
};
</script>

<template>
  <a-card title="独权概括度" size="small">
    <a-radio-group :value="modelValue" @update:value="(v: ClaimTier) => emit('update:modelValue', v)" button-style="solid">
      <a-radio-button v-for="t in (['broad','medium','narrow'] as ClaimTier[])" :key="t" :value="t">
        {{ TIER_META[t].label }}
      </a-radio-button>
    </a-radio-group>
    <a-alert v-if="claims.find(c => c.tier === modelValue)?.risk" type="warning" show-icon
             :message="claims.find(c => c.tier === modelValue)?.risk" style="margin-top:12px" />
  </a-card>
</template>
