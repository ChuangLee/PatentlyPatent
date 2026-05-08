<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
</script>

<template>
  <div class="pp-err">
    <div class="pp-err__bg" aria-hidden="true" />
    <div class="pp-err__inner">
      <div class="pp-err__code">404</div>
      <div class="pp-err__title">页面走丢了</div>
      <div class="pp-err__desc">
        你访问的页面可能已被移动、删除，或从未存在过。
      </div>
      <a-button
        type="primary"
        size="large"
        class="pp-err__btn"
        @click="router.push('/')"
      >
        ← 返回首页
      </a-button>
    </div>
  </div>
</template>

<style scoped>
.pp-err {
  position: relative;
  min-height: 100vh;
  width: 100%;
  background: var(--pp-color-bg);
  overflow: hidden;
}
.pp-err__bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 60% 40% at 50% 30%, rgba(91, 108, 255, 0.10), transparent 70%),
    radial-gradient(ellipse 40% 30% at 80% 70%, rgba(236, 72, 153, 0.08), transparent 70%),
    linear-gradient(0deg, transparent 0, transparent calc(100% - 1px), var(--pp-color-border-soft) 100%) 0 0 / 100% 48px,
    linear-gradient(90deg, transparent 0, transparent calc(100% - 1px), var(--pp-color-border-soft) 100%) 0 0 / 48px 100%;
  pointer-events: none;
  opacity: 0.6;
}
.pp-err__inner {
  position: relative;
  max-width: 560px;
  margin: 0 auto;
  padding: 25vh 24px 0;
  text-align: center;
}
.pp-err__code {
  font-size: 96px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -2px;
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 50%, #EC4899 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  margin-bottom: 16px;
}
.pp-err__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--pp-color-primary);
  margin-bottom: 12px;
}
.pp-err__desc {
  font-size: 14px;
  color: var(--pp-color-text-secondary);
  line-height: 1.7;
  margin-bottom: 28px;
}
.pp-err__btn {
  border-radius: var(--pp-radius-md);
  height: 40px;
  padding: 0 22px;
  font-weight: 500;
}
</style>
