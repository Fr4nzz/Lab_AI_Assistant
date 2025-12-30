# Codebase Audit Report

> **Date:** 2025-12-30
> **Status:** Ready for Review

## Summary

This audit identifies unused/legacy code, deprecated files, and cleanup opportunities in the Lab_AI_Assistant codebase.

---

## 1. CRITICAL: Legacy Frontend (SAFE TO DELETE)

### `frontend/` Directory - **ENTIRE FOLDER CAN BE DELETED**

The `frontend/` directory contains the **OLD Next.js frontend** that has been completely replaced by `frontend-nuxt/`.

**Evidence:**
- `start-dev.bat` only references `frontend-nuxt/` (lines 103-113, 139)
- No active code references the old frontend
- `frontend/` uses Next.js + React, while active frontend uses Nuxt + Vue

**Files to delete (entire directory):**
```
frontend/
├── components.json
├── drizzle.config.ts
├── middleware.ts
├── next.config.ts
├── package-lock.json
├── package.json
├── tsconfig.json
├── postcss.config.mjs
├── eslint.config.mjs
├── tailwind.config.ts
├── public/
└── src/
    ├── app/
    │   ├── api/
    │   │   ├── auth/[...nextauth]/route.ts
    │   │   ├── browser/tabs/detailed/route.ts
    │   │   ├── browser/tabs/route.ts
    │   │   ├── chat/audio/route.ts
    │   │   ├── chat/route.ts
    │   │   ├── chat/title/route.ts
    │   │   ├── db/chats/[chatId]/messages/route.ts
    │   │   ├── db/chats/[chatId]/route.ts
    │   │   ├── db/chats/route.ts
    │   │   ├── exams/route.ts
    │   │   ├── files/[filename]/route.ts
    │   │   └── tools/execute/route.ts
    │   ├── manifest.ts
    │   └── robots.ts
    ├── auth.ts
    ├── hooks/use-media-query.ts
    └── lib/
        ├── db/drizzle.ts
        ├── db/index.ts
        ├── db/schema.ts
        ├── models.ts
        └── utils.ts
```

**Disk space saved:** ~50MB+ (including node_modules if present)

---

## 2. Historical Documentation Files (SAFE TO DELETE)

These markdown files document completed migrations and are no longer needed:

| File | Reason to Delete |
|------|------------------|
| `MIGRATION_PLAN.md` | Migration to Nuxt completed |
| `MIGRATION_CODING_PLAN.md` | References old `frontend/` directory exclusively |
| `AI_SDK_ISSUES_RESEARCH.md` | Research completed, issues resolved |
| `CODING_PLAN_IMAGE_ROTATION_TOOL.md` | Marked "Status: IMPLEMENTED" |
| `docs/06-clean-implementation-plan.md` | Historical implementation plan |
| `docs/tool-display-fix-plan.md` | Tool display fix implemented |
| `docs/TELEGRAM_BOT_PLAN.md` | Telegram bot completed |
| `docs/TELEGRAM_BOT_FIX_PLAN.md` | Fix completed |
| `docs/TELEGRAM_BOT_SETUP.md` | Keep if useful for reference |

**Recommendation:** Move useful docs to `docs/archive/` or delete entirely.

---

## 3. Data File in Root (SHOULD BE MOVED OR DELETED)

| File | Issue | Action |
|------|-------|--------|
| `tarifas-2025-12-25-05-56-18.csv` | Raw input data in repo root | Move to `backend/config/` or delete (output already in `backend/config/lista_de_examenes.csv`) |

---

## 4. Backend Endpoints Analysis

### Potentially Unused Endpoints

These backend endpoints exist but may not be called by the current frontend:

| Endpoint | Function | Status |
|----------|----------|--------|
| `GET /api/history/{thread_id}` | `get_history()` | **UNUSED** - No frontend references |
| `POST /api/tools/execute` | `execute_tool()` | **UNUSED** - Only referenced in old `frontend/` |
| `POST /api/chat/stream` | `chat_stream()` | **UNUSED** - Frontend uses `/api/chat/aisdk` |
| `POST /v1/chat/completions` | `openai_compatible_chat()` | **KEEP** - May be used by external tools |

**Recommendation:** Remove unused endpoints after verification, or mark as deprecated.

---

## 5. Cloudflare Bat Files Analysis

All cloudflare bat files are documented and potentially useful:

| File | Purpose | Keep? |
|------|---------|-------|
| `start-dev.bat` | Main launcher | **KEEP** |
| `start-telegram-bot.bat` | Standalone telegram bot | **KEEP** |
| `cloudflare-quick-tunnel.bat` | Quick tunnel (no domain needed) | **KEEP** |
| `cloudflare-quick-tunnel-notify.bat` | Tunnel + WhatsApp notification | **KEEP** |
| `cloudflare-quick-tunnel-notify.py` | Python helper for notifications | **KEEP** |
| `cloudflare-tunnel-setup.bat` | Persistent tunnel setup | **KEEP** |
| `cloudflare-tunnel-run.bat` | Run persistent tunnel | **KEEP** |
| `cloudflare-tunnel-service.bat` | Install as Windows service | **KEEP** |

---

## 6. Backend Code Quality

### Files actively used:
- `backend/server.py` - Main FastAPI server
- `backend/models.py` - LLM models with API key rotation
- `backend/browser_manager.py` - Playwright browser control
- `backend/extractors.py` - Page data extraction
- `backend/config.py` - Configuration
- `backend/prompts.py` - AI prompts
- `backend/stream_adapter.py` - Stream utilities
- `backend/graph/` - LangGraph agent implementation
- `backend/scripts/process_tarifas.py` - Data processing utility

**No unused Python files identified.**

---

## 7. Frontend-Nuxt Code Quality

All components and composables are actively used:

| Type | Files | Status |
|------|-------|--------|
| Components | 19 files | All referenced |
| Composables | 11 files | All referenced |
| Pages | 3 files | All routes active |
| Server API | 14 files | All endpoints used |

**No unused Vue/TypeScript files identified.**

---

## 8. Recommended Cleanup Actions

### Priority 1: Delete Legacy Frontend
```bash
rm -rf frontend/
```
**Impact:** Removes ~50MB+ of dead code

### Priority 2: Clean Historical Docs
```bash
rm MIGRATION_PLAN.md
rm MIGRATION_CODING_PLAN.md
rm AI_SDK_ISSUES_RESEARCH.md
rm CODING_PLAN_IMAGE_ROTATION_TOOL.md
rm docs/06-clean-implementation-plan.md
rm docs/tool-display-fix-plan.md
rm docs/TELEGRAM_BOT_PLAN.md
rm docs/TELEGRAM_BOT_FIX_PLAN.md
```

### Priority 3: Move or Delete Data File
```bash
# Option A: Move to proper location
mv tarifas-2025-12-25-05-56-18.csv backend/config/

# Option B: Delete (output already exists)
rm tarifas-2025-12-25-05-56-18.csv
```

### Priority 4: Clean Backend Unused Endpoints (Optional)

In `backend/server.py`, consider removing or deprecating:
- `get_history()` (line 644)
- `execute_tool()` (line 722)
- `chat_stream()` (line 589)

---

## 9. Files to Keep

### Essential Files
- `.env.example` - Environment template
- `.gitignore` - Git configuration
- `README.md` - Project documentation
- `CLOUDFLARE_TUNNEL_SETUP.md` - Tunnel setup guide
- `docs/REMOTE_ACCESS_SETUP.md` - Remote access guide

### Backend
- All `backend/` files are actively used

### Frontend-Nuxt
- All `frontend-nuxt/` source files are actively used

### Telegram Bot
- All `telegram_bot/` files are actively used

---

## 10. Summary Table

| Category | Items to Delete | Disk Space |
|----------|-----------------|------------|
| Legacy Frontend | `frontend/` directory | ~50MB+ |
| Historical Docs | 8 markdown files | ~100KB |
| Data Files | 1 CSV file | ~33KB |
| **Total** | **~50MB+** | |

---

## Next Steps

1. Review this audit with the team
2. Backup any files you want to preserve
3. Execute cleanup commands in Priority order
4. Commit changes with message: "Clean up legacy code and documentation"
5. Update `.gitignore` to exclude `frontend/` permanently

