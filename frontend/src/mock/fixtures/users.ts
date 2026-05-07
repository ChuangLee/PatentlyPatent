import type { User } from '@/types';

export const DEMO_USERS: User[] = [
  { id: 'u1', name: '张工程师', role: 'employee', department: '研发-AI 平台部' },
  { id: 'u2', name: '王管理员', role: 'admin',    department: 'IP 总部' },
];

export const DEFAULT_EMPLOYEE = DEMO_USERS[0];
export const DEFAULT_ADMIN = DEMO_USERS[1];
