# PatentlyPatent · Frontend Prototype

mid-fi 交互原型（MSW 全 mock 拦截 + 双角色完整闭环）。

## 开发

```bash
pnpm install
pnpm dev          # http://127.0.0.1:5173/patent/
pnpm test         # 单测
pnpm build        # 构建到 dist/
pnpm preview      # 预览构建产物
```

## 部署到 blind.pub/patent

1. 一次性把 `nginx/patent.conf.snippet` 内容追加到 `/etc/nginx/conf.d/3xui.conf` 的 `server_name blind.pub` 块内
2. `sudo nginx -t && sudo nginx -s reload`
3. 后续每次 `pnpm deploy` 自动 build + rsync + reload

## 角色

- **员工**：登录后报门 → AI 引导对话 → 检索报告 → 起草交底书 → 提交存档
- **管理员**：登录后看分布饼图 + 全量项目表；点项目进员工页变只读模式

## Demo Data

3 个真实可读 case（密码学/信息安全/AI），刷新页面会重置（数据驻留浏览器内存与 sessionStorage）。

## 切真后端

把 `src/api/client.ts` 的 `baseURL` 改成真实后端地址，关掉 MSW（`main.ts` 的 `enableMocking()`），业务代码不动。
