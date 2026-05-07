import { describe, it, expectTypeOf } from 'vitest';
import type {
  Role, ProjectStatus, Domain, Patentability, ClaimTier, XYNTag,
  User, Project, ChatMessage, MiningSummary, SearchReport, PriorArtHit,
  Disclosure, ChatStreamEvent,
} from '@/types';

describe('types', () => {
  it('Role 是 employee | admin', () => {
    expectTypeOf<Role>().toEqualTypeOf<'employee' | 'admin'>();
  });

  it('ProjectStatus 4 状态', () => {
    expectTypeOf<ProjectStatus>().toEqualTypeOf<
      'drafting' | 'researching' | 'reporting' | 'completed'
    >();
  });

  it('Project 必字段齐全', () => {
    const p: Project = {
      id: 'p1', title: 't', domain: 'ai', description: 'd',
      status: 'drafting', ownerId: 'u1',
      createdAt: '2026-05-07T00:00:00Z',
      updatedAt: '2026-05-07T00:00:00Z',
    };
    expectTypeOf(p).toMatchTypeOf<Project>();
  });

  it('ChatStreamEvent 4 种 discriminated union', () => {
    const e1: ChatStreamEvent = { type: 'thinking' };
    const e2: ChatStreamEvent = { type: 'delta', chunk: 'a' };
    const e3: ChatStreamEvent = { type: 'fields', captured: ['x'] };
    const e4: ChatStreamEvent = { type: 'done' };
    expectTypeOf([e1, e2, e3, e4]).toMatchTypeOf<ChatStreamEvent[]>();
  });
});
