# 校验生成的 SQL 是否符合安全规则并在失败时触发修正

## Parent

PRD：`team-spec/active/2026-06-19-semantic-matching-pipeline/prd/prd.md`（5.3 安全校验，issue D）

## What to build

实现 SQL 安全校验器：对生成的 SQL 做三重检查——黑名单（`INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|EXEC|INTO OUTFILE|LOAD|SLEEP|BENCHMARK|@@version`）、白名单（`LIMIT ≤ 1000`，禁止 `SELECT *`）、语法校验（`sqlparse` 解析）。校验失败 → 返回失败原因 + 触发 LLM 重生成一次 → 再次校验 → 仍失败 → 阻断查询（不执行），告知用户原因。额外做单步约束：拦截 `FROM` 子句中含多个表别名的 SQL（V1 不支持多表 JOIN）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given SQL 含 `DROP TABLE`，When 校验，Then 返回 `{passed: False, reason: "blacklist: DROP"}`。
- [ ] Given SQL 不含 `LIMIT` 或 `LIMIT > 1000`，When 校验，Then 返回失败原因（白名单违规）。
- [ ] Given SQL 含 `SELECT *`，When 校验，Then 返回失败（禁止 `SELECT *`）。
- [ ] Given SQL 语法错误（`sqlparse` 无法解析），When 校验，Then 返回失败。
- [ ] Given 校验失败，When 触发修正，Then LLM 重生成一次 SQL（以失败原因+原 SQL 为上下文）；再次校验 → 仍失败→最终阻断。
- [ ] Given SQL 的 FROM 子句含多个表别名，When 校验，Then 拦截为「单步约束」、返回原因（V1 不支持多表 JOIN）。
- [ ] Given 校验通过，When 返回，Then `{passed: True}`。

## Blocked by

- None - can start immediately（接收任意 SQL 字符串即可测试）

## Notes

- 黑/白名单检查用正则匹配（大小写不敏感）。
- `sqlparse` 需加入 `pyproject.toml` 依赖。
- 测试用静态 SQL 字符串即可验证全流程（不需要 LLM 参与时 mock LLM 重生成步骤）。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:59:48Z
- GitHub Number: 33
- GitHub URL: https://github.com/yanheng799/chat-db/issues/33
