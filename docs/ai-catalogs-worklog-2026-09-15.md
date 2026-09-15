# AI Catalog 일반화 작업 정리 (2026-09-15)

Codex 전용이던 AI Catalog를 **종류(kind)별 quota 정책 + 실행 adapter** 구조로 나누고, Jules를 정기 세션용으로 붙인 작업의 기록이다.
정식 계약 문서는 [AI Catalog Gateway](ai-catalogs.md)이고, 이 문서는 "무엇이 왜 바뀌었고 무엇이 남았는지"를 따라가기 위한 정리본이다.

> 모든 변경은 **아직 커밋되지 않았다.** 이 세션 이전부터 있던 미커밋 변경과 섞여 있으니 [커밋 전 참고](#커밋-전-참고)를 먼저 볼 것.

## 한눈에 보기

| 항목 | 이전 | 지금 |
| --- | --- | --- |
| quota 규칙 | `AICatalogService` 안에 Codex 규칙이 하드코딩 | kind별 `QuotaPolicy` (Codex: `CodexWindowPolicy`, Jules: `DailyQuotaPolicy`) |
| 실행(발송/관찰) | `lifecycle.py`에 GitHub 멘션 코드가 직접 들어 있음 | `ExecutionAdapter` (Codex: `CodexGithubMentionAdapter`) |
| 입장 거절 | `ProjectError(409)` raise → 거절 중 상태 전이 롤백 | `Admission` 값 반환 → 커밋 후 409 |
| 설정 저장 | Codex 전용 컬럼 (`short_refresh_*` 등) | `ai_catalogs.policy_config` JSON, kind 정책이 검증 |
| 일간 한도 | 없음 | 발송 기록 `ai_catalog_dispatches`로 집계 |
| Jules | 없음 | 스케줄 task `jules.session` / `jules.sync_sessions`, 세션 추적 `ai_catalog_sessions` |
| PR 파이프라인에서 Jules | - | 의도적으로 501 (Jules API가 기존 PR branch에 push 불가) |

## 배경

- Codex는 "첫 작업 기준 usage window + 한도 초과 답글로만 알 수 있음" 모델이다.
- Jules는 "동시 실행 수 + 24시간 롤링 일간 작업 수" 모델이다. 공식 문서 기준 Pro는 하루 100건, 동시 15건이다. 출처: <https://jules.google/docs/usage-limits/>
- 두 모델이 너무 달라서, quota 판단(정책)과 실행 방식(adapter)을 서로 독립된 두 축으로 나눴다.
- Jules API(v1alpha)는 기존 PR branch에 push할 방법이 없다. 그래서 Jules는 PR 파이프라인이 아니라 **정기 리포트·위생점검 세션**용으로 쓰기로 결정했다. 결과 처리는 최소한(세션 추적만)으로 둔다.
- 운영에서 돌아가는 것이 없어서 하위 호환은 고려하지 않았다. 옛 컬럼과 API는 삭제했다.

## 최종 구조

```text
                          ┌──────────────── AICatalogService (gateway) ────────────────┐
PipelineRun delivery ───► │ 1. 공통 검사: enabled / DISABLED·UNKNOWN / 만료 안 된 hold  │
  key "delivery:<id>"     │ 2. policy.admit()      ← kind별 QuotaPolicy                 │
                          │ 3. 동시 실행 수 검사   ← active_dispatch_count (run + 세션) │
Jules session ──────────► │ 4. 통과 시 ledger 기록 (ai_catalog_dispatches, key당 1회)   │
  key "session:<id>"      │ → Admission(rejection | None) 반환                          │
                          └────────────────────────────────────────────────────────────┘
                                   │ 정책 registry (kind)          │ adapter registry (adapter)
                                   ▼                               ▼
                    codex → CodexWindowPolicy          codex-github-mention → CodexGithubMentionAdapter
                    jules → DailyQuotaPolicy           jules-api → 501 (PR 파이프라인 미지원)
```

## 변경 내용

### 1. Quota 정책 분리 — `modules/hub/app/features/ai_catalogs/policies/`

| 파일 | 내용 |
| --- | --- |
| `base.py` | `QuotaPolicy` Protocol: `effective_concurrency`, `validate_config`, `admit`, `on_delivered`, `on_quota_signal`, `on_hold_cleared`. 공용 `utc()`, `hold_state()` |
| `codex_window.py` | 기존 Codex 규칙을 그대로 옮김 (short/long cycle, usage window, recovery probe). 설정은 `CodexWindowConfig`(`policy_config`)에서 읽음 |
| `daily_quota.py` | Jules용. `daily_task_limit`, `window`(`rolling` 기본 / `calendar`), `timezone`. ledger로 창 안의 건수를 세어 한도 도달 시 hold 기록 |
| `registry.py` | kind → 정책. `find_quota_policy`(없으면 None), `quota_policy_for`(없으면 409) |

`AICatalogService`(`services.py`)에는 게이트웨이 공통 로직만 남겼다. 잠금, 공통 거절, 동시 실행 수 검사, ledger 기록, 수동 hold와 해제, 활성화, 설정, connector 지정이다.

### 2. 실행 adapter 분리 — `modules/hub/app/features/project_management/pipeline_runs/adapters/`

| 파일 | 내용 |
| --- | --- |
| `base.py` | `ExecutionAdapter` Protocol: `deliver()`, `collect_replies()`, `silent_timeout`, `silent_block_reason` |
| `codex_github_mention.py` | 기존 `lifecycle.py`의 멘션 게시, marker 재조정, Codex 답글 파싱을 옮김 |
| `registry.py` | catalog의 `adapter` → 구현. `jules-api`는 **입장 판단 전에** 501로 거절하므로 quota를 소모하지 않음 |

`lifecycle.py`는 adapter가 돌려준 결과(`DeliveryReceipt`, `AgentReply`)를 DB에 기록하고 상태를 바꾸는 역할만 한다.

### 3. 파이프라인 dispatch 흐름 (`dispatch_implementation`)

```text
lease 확인 → project 변경 확인(변경 시 BLOCKED)
→ adapter resolve (jules-api면 501)
→ active attempt 조회 → delivery 확정 (없으면 생성, 이미 게시됐으면 새 delivery)
→ request_dispatch(catalog, run, "delivery:<delivery id>")
     ├ 거절: session.commit() 후 409   ← 정책이 기록한 hold/probe 전환 유지
     └ 통과: ledger 기록, attempt DISPATCHING
→ (트랜잭션 밖) guard → adapter.deliver()
→ delivery 기록, IMPLEMENTING, record_dispatch_delivered()
```

### 4. 발송 기록(ledger) — `ai_catalog_dispatches`

- 입장 판단을 통과한 작업 단위마다 한 줄씩 남긴다. `dispatch_key`는 unique다.
  - 파이프라인: `delivery:<execution_delivery id>`
  - Jules: `session:<ai_catalog_session id>`
- 같은 key로 재시도하면 새로 쓰지 않고 첫 기록을 유지한다. 정책도 자기 key는 한도 계산에서 뺀다.
- 30일이 지난 기록은 같은 catalog에 새 기록을 쓸 때 함께 삭제한다.
- Codex 정책은 ledger를 읽지 않는다. 기존 delivery는 채워 넣지 않았다.

### 5. Jules 정기 세션 — `modules/hub/app/features/execution/tasks/domains/jules/`

| 파일 | 내용 |
| --- | --- |
| `client.py` | Jules REST v1alpha 클라이언트 (`X-Goog-Api-Key`). `create_session`, `get_session`, `find_session_by_title`(최근 3페이지×100건) |
| `service.py` | `JulesSessionService.start()` / `sync()` |
| `task.py` | `jules.session`(payload: `JulesSessionPayload`), `jules.sync_sessions`(payload: `JulesSyncPayload`) |

`start()` 흐름:

```text
catalog가 jules인지, connector(jules, enabled)가 있는지 확인 → API 키 복호화
→ 기존 미완료 세션 동기화 (끝난 세션이 동시 실행 자리 반납)
→ request_dispatch(catalog, run 없음, "session:<id>")
     ├ 거절: commit 후 409 (일간 한도면 hold가 저장됨)
     └ 통과: ai_catalog_sessions에 state=dispatching 행 생성
→ POST /v1alpha/sessions  (title = "<제목> [hub-session:<id>]")
     ├ 성공: name/state/url/PR url 저장
     ├ 429: 세션 failed + record_quota_event → rolling이면 24시간 hold
     ├ 그 외 4xx: 세션 failed
     └ 5xx/네트워크: dispatching 유지 → 다음 실행에서 제목으로 찾아 이어받음, 1시간 넘게 못 찾으면 failed
```

- 세션 상태 값은 Jules 상태를 소문자로 저장한다(`queued`, `in_progress`, `completed`, `failed` 등). `completed`, `failed`만 종료로 보고, 나머지는 동시 실행 자리를 차지한다.
- payload: `catalog_key`(기본 `personal-jules`), `repository`(`owner/repo`), `starting_branch`(기본 `main`), `title`, `prompt`, `auto_create_pr`(기본 false)

### 6. 설정 · API · UI

**DB (`ai_catalogs`)**
- 추가: `policy_config`(JSON), `connector_id`(FK `connectors`)
- 삭제: `short_refresh_enabled`, `short_refresh_cycle_minutes`, `long_refresh_cycle_minutes`, `probe_window_minutes`. 모두 `policy_config`로 옮김
- 유지: Codex 런타임 상태 `probe_started_at`, `short_refresh_failure_count`, `last_refreshed_at`, `usage_window_started_at`와 공용 `refresh_jitter_minutes`

**API (`/api/v1/ai-catalogs`)**

| 메서드 | 경로 | 비고 |
| --- | --- | --- |
| GET | `` | 목록. 정책 없는 kind는 `effective_concurrency=0` |
| PUT/DELETE | `/{key}/availability` | 수동 hold 설정/해제 (변경 없음) |
| PUT | `/{key}/enabled` | 변경 없음 |
| PUT | `/{key}/policy-config` | **신규.** kind 정책이 검증·정규화. Codex는 refresh 설정, Jules는 일간 한도 |
| PUT | `/{key}/connector` | **신규.** Jules catalog에 jules connector 지정. Codex는 422 |
| ~~PUT~~ | ~~`/{key}/refresh-policy`~~ | **삭제.** `policy-config`로 대체 |

응답 필드 변경:
- `active_run_count`는 `active_dispatch_count`로 바뀌었다. 파이프라인 run과 세션을 합산한다.
- Codex 설정 필드는 응답에서 빠지고 `policy_config` 안으로 들어갔다.

**Connector provider**: `github`에 `jules`(API 키는 `token`)와 `linear`를 추가했다. `linear`는 UI에만 있던 옵션이라 백엔드에 맞춰 넣은 것이고, 쓰는 기능은 없다.

**UI (Settings → AI Catalogs)**
- Codex 카드에는 "Refresh policy"가 있다. 저장하면 `policy_config`로 들어간다.
- Jules 카드에는 "Quota policy"(일간 한도, 윈도우, timezone)와 "Connector"가 있다. 카드에는 일간 한도와 connector 요약이 표시된다.
- calendar 윈도우의 timezone은 저장하기 전에 브라우저에서 검증한다.
- Settings → Connectors에는 Jules(API Key) provider가 추가됐다.

### 7. 기타 정리

- **quota 이벤트 기록:** `record_quota_event(session, catalog_id, observed_at)`는 이제 run이 아니라 catalog id를 받는다. run의 `quota_block_count`는 lifecycle에서 올린다.
- **kind 정리:** 쓰이지 않던 `openai-api` kind를 삭제했다.
- **문구 정리:** 파이프라인의 Codex 전용 사용자 문구를 일반화했다. 예: "Delivery exceeded its time budget", "CI failed after two fix requests", "The agent may still be working ...".
- **API 제한:** refresh 정책 API가 Codex에만 적용되던 제한은 API 삭제로 함께 사라졌다. 설정은 `policy-config`로 통일됐다.

## 동작이 달라진 점 (주의)

1. **probe 전환 저장:** Codex hold가 끝났는데 동시 실행이 꽉 차서 거절되면, 예전에는 `probe` 전환이 롤백됐다. 이제는 저장된다.
2. **delivery 생성 순서:** delivery를 입장 판단 **전에** 만든다. 그래서 거절돼도 계획된 delivery 행이 커밋되고, 다음 tick에서 재사용된다.
3. **게시 직전 확인:** `require_dispatchable`은 enabled라도 상태가 `disabled`/`unknown`이면 거절한다.
4. **파이프라인 에러 문구:** 일부가 바뀌었다(위 7번).
5. **API 필드:** 이름 변경과 삭제가 있다(위 6번).

## DB migration

`20260915_080000_b8c9d0e1f2a3_add_catalog_dispatch_ledger.py`(`a7b8c9d0e1f2` 다음)

1. `policy_config`, `connector_id` 추가
2. Codex 행의 refresh 컬럼 값을 `policy_config`로 복사한 뒤 컬럼 삭제
3. `ai_catalog_dispatches`, `ai_catalog_sessions` 테이블 생성
4. `personal-jules` catalog 시드: 동시 15건, 하루 100건 rolling, connector 없음

downgrade가 하는 일:
- 세션, ledger 테이블과 Jules catalog 행을 삭제
- Codex 컬럼을 기본값으로 복원 (`policy_config`에 있던 값은 되돌리지 않음)

## 검증 결과 (2026-09-15, 로컬)

| 항목 | 결과 |
| --- | --- |
| 백엔드 SQLite `run-tests.sh sqlite .` | 428 passed |
| 백엔드 PostgreSQL `run-tests.sh postgres .` (testcontainers) | 428 passed |
| pyright / ruff (변경 모듈) | 0 errors / passed |
| migration 전체 체인, 실제 PostgreSQL 16 | upgrade → downgrade → upgrade 성공, 시드·데이터 이전 확인 |
| `alembic check` | 기존부터 있던 comment 차이 2건만 검출: `pipeline_runs.pull_snapshot`, `schedule_configs.next_run_at` |
| UI vitest | 7 passed (신규 `AICatalogsView.test.ts` 5개) |
| UI svelte-check / build / lint | 0 errors / 성공 / 통과 |

**실제 Jules API 호출과 실제 Codex canary는 하지 않았다.** Jules는 `httpx.MockTransport`로 만든 가짜 서버로만 검증했다.

## Jules 사용 방법

1. **Settings → Connectors**에서 provider `Jules (API Key)`로 connector를 만든다. token에 Jules API 키를 넣는다. 키는 Jules 웹 앱 Settings에서 발급하며 최대 3개까지다.
2. **Settings → AI Catalogs**의 `Personal Jules` 카드에서 **Connector** 버튼으로 방금 만든 connector를 지정한다.
3. 필요하면 **Quota policy**를 조정한다. 기본값은 하루 100건 rolling이다.
4. 스케줄 설정에 `jules.session` task를 원하는 주기로 등록한다.

   ```json
   {
     "catalog_key": "personal-jules",
     "repository": "owner/repo",
     "starting_branch": "main",
     "title": "Weekly hygiene report",
     "prompt": "…",
     "auto_create_pr": false
   }
   ```

5. `jules.sync_sessions`(`{"catalog_key": "personal-jules"}`)를 짧은 주기로 등록한다(예: 10~15분). 세션이 끝난 뒤 동시 실행 자리가 풀리는 시점이 이 주기에 달려 있다.

## 남은 작업 · 알려진 제약

### 확인이 필요한 외부 사실

- [ ] **Jules 429의 의미.** 한도 초과 에러 형식이 문서에 없다. 지금은 429를 받으면 **24시간 hold**를 건다. 동시 실행 한도 때문에 난 429여도 똑같이 걸리므로, 그런 경우 UI의 "Clear hold"로 풀어야 한다. 실제 응답을 확인한 뒤 구분 로직을 넣을 것.
- [ ] **Jules "task" 1건의 정의.** 세션 생성만 세는지, `sendMessage`나 PR 댓글 반복도 세는지 확인되지 않았다.
- [ ] **동시 한도에 닿았을 때 Jules의 동작.** `QUEUED`로 대기시키는지 거절하는지 모른다.
- [ ] **완료 판정.** 결과(`outputs`) 없이 `COMPLETED`가 되는 사례가 제3자 보고로 있다. 지금은 그대로 완료로 처리한다.
- [ ] **실제 Jules API로 canary 1회 실행.** API가 alpha라 필드명이 바뀔 수 있다.

### 코드 후속 작업

- [ ] Jules 세션 목록·결과 UI. 이번에는 "추적만"으로 범위를 정해 제외했다.
- [ ] 세션 재조정 범위. 최근 300건 제목만 검색하므로, 그보다 오래된 미확인 세션은 1시간 뒤 failed 처리된다.
- [ ] `AWAITING_PLAN_APPROVAL`, `AWAITING_USER_FEEDBACK` 상태의 세션이 동시 실행 자리를 계속 차지한다. 자동 처리가 없다.
- [ ] Codex 런타임 상태 컬럼 4개가 아직 공용 `ai_catalogs` 테이블에 있다.
- [ ] `ExecutionDelivery.comment_id`는 이름이 GitHub 전용이다. adapter 결과의 `external_id`가 여기에 저장된다.
- [ ] `held_run_count`는 파이프라인 run만 센다. 세션은 포함되지 않는다.
- [ ] UI의 kind 분기(`codex`/`jules`)가 하드코딩돼 있다. kind가 늘면 폼 구조를 다시 봐야 한다.
- [ ] ledger 30일 정리는 새 기록을 쓸 때만 돈다. 새 작업이 없는 catalog에는 오래된 행이 남는다.
- [ ] `alembic check`에 나오는 기존 comment 차이 2건 정리(이번 작업과 무관).
- [ ] Jules를 PR 파이프라인에 붙이는 안(현재 501). 필요해지면 다음 둘 중 하나를 검토한다.
  - hub가 `changeSet.gitPatch`를 받아 PR branch에 직접 적용
  - Jules가 만든 자식 PR을 추적
- [ ] 문서에 남아 있는 옵션: 대상 PR마다 catalog를 고르는 기능이 없다. 파이프라인 run은 항상 `personal-codex`를 쓴다.

### 개발 환경 메모

- UI 도구는 `.nvmrc`의 **Node 24.18.0**이 필요하다. 로컬 nvm에 설치했다. 버전이 없으면 `just gen-ui-api`가 `nvm use` 단계에서 exit 3으로 조용히 실패한다.
- `just test-pg`는 Docker 데몬이 실행 중이어야 한다(testcontainers).

## 커밋 전 참고

이번 세션을 시작할 때 이미 아래 파일에 **미커밋 변경**이 있었다. 내용은 이 세션에서 만든 것이 아니므로 따로 확인해야 한다.

```text
justfile
modules/hub-ui/src/lib/features/project-management/pipeline-runs/PipelineRunsView.svelte
modules/hub/app/features/execution/tasks/domains/pipeline/task.py
modules/hub/app/features/project_management/pipeline_runs/{models,repos}.py
modules/hub/app/features/project_management/pipeline_runs/usecases/lifecycle.py   (이번 작업도 크게 수정)
modules/hub/tests/e2e/test_projects/test_pipeline_runs_api.py                       (이번 작업도 수정)
modules/hub/tests/unit/test_tasks/test_dispatch_task.py
scripts/sync-codex-quota.py
modules/hub/migrations/versions/20260915_070000_a7b8c9d0e1f2_add_pipeline_run_github_binding.py  (신규)
modules/hub/tests/unit/test_ai_catalogs/test_sync_codex_quota.py                    (신규)
```

이번 작업에서 새로 만들거나 수정한 파일:

```text
# 신규
modules/hub/app/features/ai_catalogs/policies/{__init__,base,codex_window,daily_quota,registry}.py
modules/hub/app/features/project_management/pipeline_runs/adapters/{__init__,base,codex_github_mention,registry}.py
modules/hub/app/features/execution/tasks/domains/jules/{__init__,client,service,task}.py
modules/hub/migrations/versions/20260915_080000_b8c9d0e1f2a3_add_catalog_dispatch_ledger.py
modules/hub/tests/unit/test_ai_catalogs/test_daily_quota_policy.py
modules/hub/tests/e2e/test_ai_catalogs/test_jules_sessions.py
modules/hub-ui/src/lib/features/configuration/ai-catalogs/AICatalogsView.test.ts
docs/ai-catalogs-worklog-2026-09-15.md

# 수정
modules/hub/app/features/ai_catalogs/{models,repos,schemas,services}.py, api/v1.py
modules/hub/app/features/configuration/connectors/schemas.py
modules/hub/app/features/execution/tasks/domains/__init__.py
modules/hub/app/features/project_management/pipeline_runs/{dispatch,models}.py, usecases/lifecycle.py
modules/hub/tests/unit/test_ai_catalogs/test_refresh_policy.py
modules/hub/tests/unit/test_pipeline_runs/test_lifecycle.py
modules/hub/tests/e2e/test_ai_catalogs/test_ai_catalogs_api.py
modules/hub/tests/e2e/test_projects/test_pipeline_runs_api.py
modules/hub-ui/src/lib/api/schema.d.ts (생성물)
modules/hub-ui/src/lib/features/configuration/ai-catalogs/{AICatalogsView.svelte,ai-catalogs.svelte.ts}
modules/hub-ui/src/lib/features/configuration/connectors/ConnectorsView.svelte
docs/{README,ai-catalogs,delivery-status,development}.md
```
