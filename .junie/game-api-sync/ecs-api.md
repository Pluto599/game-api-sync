# ECS API 与环境变量

## 环境变量

在 Rider Terminal 或 shell 中配置：

- `API_SYNC_BASE` = `http://120.27.249.20`
- `API_SYNC_TOKEN` = （团队发放的只读 Token）

请求头：`Authorization: Bearer <API_SYNC_TOKEN>`

## 常用接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 无需 Token |
| GET | `/api/snapshot/modules` | 已有快照模块列表 |
| GET | `/api/snapshot?module=战斗` | 模块快照 JSON |
| POST | `/jobs/refresh-cache` | Body：`{"module":"战斗"}` 或 `{}` |
| POST | `/jobs/api-compare` | Body：`module`、`repo`、`files` |
| POST | `/jobs/api-doc-sync` | Body：`module`、`repo`、`summary`、`files_changed` |
| POST | `/jobs/api-review` | 同 compare，供 PR CI |
| GET | `/api/status` | 各模块缓存 revision |

PowerShell 终端可用 `Invoke-RestMethod`；其他环境用等价 HTTP 客户端。

## 权威飞书文档

- 接口文档：https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b
- 类型约束：https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde
