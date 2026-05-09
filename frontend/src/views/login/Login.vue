<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { apiClient } from '@/api/client';
import message from 'ant-design-vue/es/message';
import type { Role } from '@/types';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const casEnabled = ref(false);
const loading = ref<Role | null>(null);
const year = new Date().getFullYear();

// v0.28: 账密登录
const loginUsername = ref('');
const loginPassword = ref('');
const passwordLoading = ref(false);

async function loginByPassword() {
  if (passwordLoading.value) return;
  const u = loginUsername.value.trim();
  const p = loginPassword.value;
  if (!u || !p) {
    message.warning('请输入用户名和密码');
    return;
  }
  passwordLoading.value = true;
  try {
    const user = await auth.loginWithPassword(u, p);
    message.success(`欢迎回来，${user.name}`);
    router.push(user.role === 'admin' ? '/admin/dashboard' : '/employee/dashboard');
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '登录失败';
    message.error(msg);
  } finally {
    passwordLoading.value = false;
  }
}
// v0.26：仅在 dev 模式（`vite`/`vite dev`）下显示「dev 模式选角色」入口；
// 生产构建（`vite build`）时 import.meta.env.DEV === false，员工/管理员一键登录全部隐藏。
const isDev = import.meta.env.DEV === true;

async function loginAs(role: Role) {
  if (loading.value) return;
  loading.value = role;
  try {
    // v0.21：走 store 的 loginAs（内部调真 API /auth/login 拿 JWT，存 localStorage）
    const user = await auth.loginAs(role);
    message.success(`已登录为 ${user.name}`);
    router.push(role === 'admin' ? '/admin/dashboard' : '/employee/dashboard');
  } catch (e) {
    message.error('登录失败：' + (e as Error).message);
  } finally {
    loading.value = null;
  }
}

function loginViaCas() {
  auth.loginViaCas();
}

// v0.23：处理 CAS 回调（?token=...&user=... 或 ?cas_error=...）+ 探测 cas_enabled
onMounted(async () => {
  // 1. 错误回流
  const casError = (route.query.cas_error as string) || '';
  if (casError) {
    const map: Record<string, string> = {
      invalid_ticket: 'CAS 票据无效或已过期，请重新登录',
      server_unreachable: 'CAS 服务不可达，请稍后再试或改用员工/管理员登录',
    };
    message.error(map[casError] || `CAS 登录失败：${casError}`);
    router.replace({ path: '/login' });
  }

  // 2. token 回流
  const qs = new URLSearchParams(window.location.search);
  if (qs.get('token') && qs.get('user')) {
    const u = auth.consumeCasCallback(qs);
    if (u) {
      message.success(`CAS 登录成功，欢迎 ${u.name}`);
      router.replace(u.role === 'admin' ? '/admin/dashboard' : '/employee/dashboard');
      return;
    }
    message.error('CAS 回调解析失败');
    router.replace({ path: '/login' });
  }

  // 3. 探测后端是否启用 CAS（不阻塞 UI；失败默认 false）
  try {
    const r = await apiClient.get<{ cas_enabled?: boolean }>('/ping');
    casEnabled.value = !!r.data?.cas_enabled;
  } catch {
    casEnabled.value = false;
  }
});

const features = [
  { icon: '⚡', title: '一键全程', desc: '5 节挖掘端到端，从报门到交底书自动连贯' },
  { icon: '🔍', title: '真实数据', desc: '智慧芽实时检索 + AI agent 自驱拆解' },
  { icon: '🔒', title: '企业级', desc: 'CAS / JWT / 配额 / 监控，安全可审计' },
];
</script>

<template>
  <div class="pp-login">
    <!-- 左：hero 区 (mobile 下变顶部 banner) -->
    <section class="pp-login__hero">
      <div class="pp-login__hero-inner">
        <div class="pp-login__brand">
          <span class="pp-login__logo">PP</span>
          <span class="pp-login__brand-text">PatentlyPatent</span>
        </div>

        <h1 class="pp-login__title">企业自助专利挖掘平台</h1>
        <p class="pp-login__slogan">
          AI agent &nbsp;·&nbsp; 智慧芽实时检索 &nbsp;·&nbsp; 5 节流水线一键贯通
        </p>

        <ul class="pp-login__features">
          <li v-for="f in features" :key="f.title" class="pp-login__feature">
            <span class="pp-login__feature-icon">{{ f.icon }}</span>
            <div>
              <div class="pp-login__feature-title">{{ f.title }}</div>
              <div class="pp-login__feature-desc">{{ f.desc }}</div>
            </div>
          </li>
        </ul>

        <div class="pp-login__copyright">
          © {{ year }} PatentlyPatent · blind.pub/patent
        </div>
      </div>

      <!-- 装饰性气泡 -->
      <span class="pp-login__blob pp-login__blob--1" />
      <span class="pp-login__blob pp-login__blob--2" />
    </section>

    <!-- 右：登录卡片 -->
    <section class="pp-login__panel">
      <div class="pp-login__card">
        <h2 class="pp-login__card-title">登录</h2>
        <p class="pp-login__card-sub">欢迎回来，选择一种方式继续</p>

        <a-button
          v-if="casEnabled"
          class="pp-login__cas"
          size="large"
          block
          data-testid="cas-login-btn"
          @click="loginViaCas"
        >
          🏢 &nbsp;使用企业 CAS 登录
        </a-button>

        <!-- v0.28: 账号密码登录（始终显示） -->
        <div v-if="casEnabled" class="pp-login__divider"><span>— 或账号登录 —</span></div>
        <form class="pp-login__pwd" @submit.prevent="loginByPassword">
          <a-input
            v-model:value="loginUsername"
            size="large"
            placeholder="用户名"
            autocomplete="username"
            :disabled="passwordLoading"
          >
            <template #prefix>👤</template>
          </a-input>
          <a-input-password
            v-model:value="loginPassword"
            size="large"
            placeholder="密码"
            autocomplete="current-password"
            :disabled="passwordLoading"
            @press-enter="loginByPassword"
          >
            <template #prefix>🔒</template>
          </a-input-password>
          <a-button
            type="primary"
            size="large"
            block
            html-type="submit"
            :loading="passwordLoading"
          >
            登录
          </a-button>
        </form>
        <p class="pp-login__demo-hint">
          测试账号：
          <code>user / user123</code>（员工） ·
          <code>admin / admin123</code>（管理员）
        </p>

        <!-- 仅 dev / staging 模式（vite dev）显示快速选角色入口 -->
        <template v-if="isDev">
          <div class="pp-login__divider">
            <span>{{ casEnabled ? '— 或 dev 模式选角色 —' : '— dev 模式选角色 —' }}</span>
          </div>

          <div class="pp-login__role-grid">
            <button
              type="button"
              class="pp-login__role pp-login__role--employee"
              :disabled="!!loading"
              @click="loginAs('employee')"
            >
              <span class="pp-login__role-icon">👤</span>
              <span class="pp-login__role-title">员工</span>
              <span class="pp-login__role-sub">报门 · 挖掘 · 交底书</span>
              <span v-if="loading === 'employee'" class="pp-login__role-loading">登录中…</span>
            </button>
            <button
              type="button"
              class="pp-login__role pp-login__role--admin"
              :disabled="!!loading"
              @click="loginAs('admin')"
            >
              <span class="pp-login__role-icon">📊</span>
              <span class="pp-login__role-title">管理员</span>
              <span class="pp-login__role-sub">全量项目 · Agent 监控</span>
              <span v-if="loading === 'admin'" class="pp-login__role-loading">登录中…</span>
            </button>
          </div>
        </template>

        <p class="pp-login__hint">
          <span v-if="isDev">演示数据驻留浏览器；刷新可重置。<br /></span>
          仓库：github.com/ChuangLee/PatentlyPatent
        </p>
        <div class="pp-login__version">v0.26 · 准备上线</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.pp-login {
  display: flex;
  min-height: 100vh;
  background: var(--pp-color-bg);
  font-family: var(--pp-font-sans);
}

/* ---------- 左：hero ---------- */
.pp-login__hero {
  flex: 0 0 60%;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 50%, #EC4899 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--pp-space-7);
}
.pp-login__hero-inner {
  position: relative;
  z-index: 2;
  max-width: 520px;
  width: 100%;
}
.pp-login__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: var(--pp-space-7);
}
.pp-login__logo {
  width: 40px;
  height: 40px;
  border-radius: var(--pp-radius-md);
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(10px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.pp-login__brand-text {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.4px;
}
.pp-login__title {
  font-size: clamp(28px, 3.4vw, 44px);
  line-height: 1.18;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 var(--pp-space-3);
}
.pp-login__slogan {
  font-size: 15px;
  font-weight: 400;
  opacity: 0.92;
  letter-spacing: 0.2px;
  margin: 0 0 var(--pp-space-7);
}
.pp-login__features {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--pp-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--pp-space-4);
}
.pp-login__feature {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.pp-login__feature-icon {
  flex: 0 0 36px;
  height: 36px;
  border-radius: var(--pp-radius-md);
  background: rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(10px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}
.pp-login__feature-title {
  font-weight: 600;
  font-size: 15px;
  letter-spacing: 0.2px;
  margin-bottom: 2px;
}
.pp-login__feature-desc {
  font-size: 13px;
  opacity: 0.82;
  line-height: 1.55;
}
.pp-login__copyright {
  position: absolute;
  bottom: var(--pp-space-6);
  left: var(--pp-space-7);
  right: var(--pp-space-7);
  font-size: 12px;
  opacity: 0.7;
  letter-spacing: 0.3px;
}
.pp-login__blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
  z-index: 1;
  pointer-events: none;
}
.pp-login__blob--1 {
  width: 480px;
  height: 480px;
  top: -160px;
  right: -120px;
  background: rgba(236, 72, 153, 0.55);
}
.pp-login__blob--2 {
  width: 380px;
  height: 380px;
  bottom: -120px;
  left: -100px;
  background: rgba(59, 130, 246, 0.55);
}

/* ---------- 右：登录卡片 ---------- */
.pp-login__panel {
  flex: 1 1 40%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--pp-space-6);
  background: var(--pp-color-bg);
}
.pp-login__card {
  width: 100%;
  max-width: 400px;
  background: var(--pp-color-surface);
  border-radius: var(--pp-radius-lg);
  box-shadow: var(--pp-shadow-xl);
  padding: var(--pp-space-7) var(--pp-space-6);
  border: 1px solid var(--pp-color-border-soft);
}
.pp-login__card-title {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--pp-color-text);
  margin: 0 0 6px;
}
.pp-login__card-sub {
  color: var(--pp-color-text-secondary);
  font-size: 14px;
  margin: 0 0 var(--pp-space-5);
}
.pp-login__cas {
  height: 44px;
  border-radius: var(--pp-radius-md);
  font-weight: 500;
  margin-bottom: var(--pp-space-4);
}
.pp-login__divider {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--pp-color-text-tertiary);
  font-size: 12px;
  margin: var(--pp-space-4) 0;
}
.pp-login__pwd {
  display: flex;
  flex-direction: column;
  gap: var(--pp-space-3);
  margin-top: var(--pp-space-2);
}
.pp-login__demo-hint {
  margin-top: var(--pp-space-3);
  padding: var(--pp-space-2) var(--pp-space-3);
  background: var(--pp-color-primary-soft);
  border-radius: var(--pp-radius-sm);
  font-size: 12px;
  color: var(--pp-color-text-secondary);
  line-height: 1.6;
  text-align: center;
}
.pp-login__demo-hint code {
  background: var(--pp-color-surface);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--pp-font-mono);
  font-size: 11.5px;
  color: var(--pp-color-primary);
}
.pp-login__divider::before,
.pp-login__divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--pp-color-border);
}
.pp-login__role-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--pp-space-3);
}
.pp-login__role {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: var(--pp-space-4);
  border-radius: var(--pp-radius-md);
  border: 1px solid var(--pp-color-border);
  background: var(--pp-color-surface);
  cursor: pointer;
  transition: var(--pp-transition);
  text-align: left;
  font-family: inherit;
}
.pp-login__role:hover:not(:disabled) {
  border-color: var(--pp-color-primary);
  box-shadow: var(--pp-shadow-md);
  transform: translateY(-1px);
}
.pp-login__role:disabled { cursor: not-allowed; opacity: 0.6; }
.pp-login__role--employee {
  background: linear-gradient(180deg, var(--pp-color-primary-soft) 0%, var(--pp-color-surface) 100%);
}
.pp-login__role--admin {
  background: linear-gradient(180deg, #FFF7ED 0%, var(--pp-color-surface) 100%);
}
.pp-login__role-icon {
  font-size: 22px;
  margin-bottom: 4px;
}
.pp-login__role-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--pp-color-text);
}
.pp-login__role-sub {
  font-size: 12px;
  color: var(--pp-color-text-secondary);
  letter-spacing: 0.2px;
}
.pp-login__role-loading {
  position: absolute;
  top: 8px;
  right: 10px;
  font-size: 11px;
  color: var(--pp-color-primary);
}
.pp-login__hint {
  margin: var(--pp-space-5) 0 0;
  font-size: 12px;
  color: var(--pp-color-text-tertiary);
  line-height: 1.6;
  text-align: center;
}
.pp-login__cas-hint {
  margin-top: var(--pp-space-4);
  padding: 10px 12px;
  border-radius: var(--pp-radius-md);
  background: var(--pp-color-bg-elevated);
  border: 1px dashed var(--pp-color-border);
  color: var(--pp-color-text-secondary);
  font-size: 12px;
  line-height: 1.55;
  text-align: center;
}
.pp-login__version {
  margin-top: var(--pp-space-3);
  text-align: center;
  font-size: 11px;
  color: var(--pp-color-text-tertiary);
  letter-spacing: 0.4px;
}

/* ---------- 响应式：< 900px 单栏堆叠 ---------- */
@media (max-width: 900px) {
  .pp-login {
    flex-direction: column;
  }
  .pp-login__hero {
    flex: 0 0 auto;
    padding: var(--pp-space-6) var(--pp-space-5);
    min-height: 280px;
  }
  .pp-login__copyright { display: none; }
  .pp-login__features { margin-bottom: var(--pp-space-4); }
  .pp-login__title { font-size: 26px; }
  .pp-login__panel {
    padding: var(--pp-space-4);
  }
}
@media (max-width: 480px) {
  .pp-login__role-grid { grid-template-columns: 1fr; }
}
</style>
