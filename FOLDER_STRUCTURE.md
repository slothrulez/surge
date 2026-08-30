# FOLDER_STRUCTURE.md — Complete Project Layout

**This shows exactly how to organize all files locally.**

---

## Complete Folder Structure

```
payment-recovery-system/                    ← Your main project folder
│
├─ .env                                     ← Your Razorpay credentials (DO NOT COMMIT)
├─ .env.example                             ← Template for .env (COMMIT THIS)
├─ .gitignore                               ← Git ignore rules
│
├─ README.md                                ← Project overview (PUBLIC)
├─ SPEC.md                                  ← Specification (PUBLIC, no blueprint)
├─ RULES.md                                 ← Development rules (PUBLIC)
├─ AGENT.md                                 ← Instructions for AI (PUBLIC)
├─ INSTRUCTION.md                           ← Build instructions (PUBLIC)
├─ SAFETY_RULES.md                          ← Critical constraints (PUBLIC)
├─ AI_GUIDELINES.md                         ← AI decision guide (PUBLIC)
├─ MASTER_TASK_CHECKLIST.md                 ← All 203 tasks (UPDATEABLE)
│
├─ main.py                                  ← FastAPI application
├─ config.py                                ← Configuration & enums
├─ models.py                                ← Pydantic models
├─ requirements.txt                         ← Python dependencies
├─ Dockerfile                               ← Container image
├─ docker-compose.yml                       ← Local dev environment
│
├─ migrations/
│   └─ 001_initial_schema.sql              ← Database schema (10 tables)
│
├─ docs/                                    ← Documentation
│   ├─ BLUEPRINT.md                        ← Full spec (INTERNAL, DO NOT COMMIT)
│   ├─ PHASE_0_1_SUMMARY.md                ← Phase 0-1 completion
│   └─ MASTER_TASK_LIST.md                 ← Task decomposition (INTERNAL)
│
├─ src/                                     ← Source code (created in Phase 2+)
│   ├─ database/                           ← Phase 2
│   │   ├─ __init__.py
│   │   ├─ models.py                       ← SQLAlchemy ORM
│   │   └─ queries.py                      ← CRUD functions
│   │
│   ├─ detection/                          ← Phase 3+
│   │   ├─ __init__.py
│   │   └─ webhook.py                      ← Webhook receiver
│   │
│   ├─ diagnosis/                          ← Phase 4+
│   │   ├─ __init__.py
│   │   └─ engine.py                       ← Error classification
│   │
│   └─ ... (more phases)
│
├─ tests/                                   ← Test suite (Phase 12+)
│   ├─ __init__.py
│   ├─ test_database.py                    ← Database tests
│   ├─ test_webhook.py                     ← Webhook tests
│   ├─ conftest.py                         ← Pytest fixtures
│   └─ ... (more tests)
│
└─ .github/                                 ← GitHub config (optional)
    └─ workflows/
        └─ tests.yml                        ← CI/CD pipeline
```

---

## File Categories

### 🔴 Critical for Setup (MUST HAVE)

These files are REQUIRED for the project to run:

```
payment-recovery-system/
├─ main.py                  ← Application
├─ config.py                ← Configuration
├─ models.py                ← Data structures
├─ requirements.txt         ← Dependencies
├─ Dockerfile               ← Container build
├─ docker-compose.yml       ← Local dev environment
├─ .env.example             ← Credentials template
├─ .env                     ← Your credentials (create from .env.example)
└─ migrations/
   └─ 001_initial_schema.sql  ← Database schema
```

**Total: 9 files**

### 📘 Governance Files (COMMIT TO GIT)

These files guide development and can be public:

```
payment-recovery-system/
├─ README.md                ← Project overview
├─ SPEC.md                  ← What to build (from blueprint, no internals)
├─ RULES.md                 ← How to build
├─ AGENT.md                 ← AI instructions
├─ INSTRUCTION.md           ← Step-by-step guides
├─ SAFETY_RULES.md          ← Critical constraints
├─ AI_GUIDELINES.md         ← AI decision-making
└─ MASTER_TASK_CHECKLIST.md ← Progress tracking (UPDATE AFTER EACH TASK)
```

**Total: 8 files**

### 🔒 Internal Only (DO NOT COMMIT)

These files contain your internal reasoning:

```
.env                        ← Your secrets
docs/BLUEPRINT.md          ← Your internal spec
docs/MASTER_TASK_LIST.md   ← Your internal task decomposition
```

### 📁 Auto-Generated (Phases 2+)

These directories are created as you build:

```
src/                        ← Phase 2+
tests/                      ← Phase 12+
.github/workflows/          ← Optional CI/CD
```

---

## Files You're Creating Right Now

### From Phase 0-1 Output

Copy these 10 files from your uploaded files:

| File | Source | Destination |
|------|--------|-------------|
| `main.py` | Uploaded | `payment-recovery-system/main.py` |
| `config.py` | Uploaded | `payment-recovery-system/config.py` |
| `models.py` | Uploaded | `payment-recovery-system/models.py` |
| `requirements.txt` | Uploaded | `payment-recovery-system/requirements.txt` |
| `Dockerfile` | Uploaded | `payment-recovery-system/Dockerfile` |
| `docker-compose.yml` | Uploaded | `payment-recovery-system/docker-compose.yml` |
| `env.example` | Uploaded | `payment-recovery-system/.env.example` |
| `001_initial_schema.sql` | Uploaded | `payment-recovery-system/migrations/001_initial_schema.sql` |
| `PHASE_0_1_SUMMARY.md` | Uploaded | `payment-recovery-system/docs/PHASE_0_1_SUMMARY.md` |
| `BLUEPRINT.md` (internal) | Uploaded | `payment-recovery-system/docs/BLUEPRINT.md` |

**Total: 10 files from Phase 0-1 output**

### Governance Files (I'm Creating)

I've created these 8 public-safe governance files:

| File | Purpose | Visibility |
|------|---------|------------|
| `README.md` | Project overview | PUBLIC (commit) |
| `SPEC.md` | Specification | PUBLIC (commit) |
| `RULES.md` | Development rules | PUBLIC (commit) |
| `AGENT.md` | AI instructions | PUBLIC (commit) |
| `INSTRUCTION.md` | Build instructions | PUBLIC (commit) |
| `SAFETY_RULES.md` | Critical constraints | PUBLIC (commit) |
| `AI_GUIDELINES.md` | AI decision guide | PUBLIC (commit) |
| `MASTER_TASK_CHECKLIST.md` | Progress tracking | PUBLIC (commit) |

**Total: 8 new governance files**

---

## Complete File Count

```
Phase 0-1 Output:           10 files
├─ .py files:              3 (main, config, models)
├─ Config files:           4 (requirements.txt, Dockerfile, docker-compose.yml, .env.example)
├─ Database:               1 (migrations/001_initial_schema.sql)
└─ Documentation:          2 (in docs/)

Governance Files (New):     8 files
├─ .md files:              8 (all public, committable)

Total Now:                  18 files
├─ Code:                    3
├─ Config/Infrastructure:   4
├─ Database:               1
├─ Documentation:         10
```

After Phase 2 completes:
- src/database/models.py
- src/database/queries.py
- src/database/__init__.py
- tests/test_database.py
- etc.

---

## Git Workflow

### What to Commit

```
payment-recovery-system/
├─ main.py              ✅ COMMIT
├─ config.py            ✅ COMMIT
├─ models.py            ✅ COMMIT
├─ requirements.txt     ✅ COMMIT
├─ Dockerfile           ✅ COMMIT
├─ docker-compose.yml   ✅ COMMIT
├─ .env.example         ✅ COMMIT (template)
├─ .gitignore           ✅ COMMIT (ignore .env)
├─ README.md            ✅ COMMIT
├─ SPEC.md              ✅ COMMIT
├─ RULES.md             ✅ COMMIT
├─ AGENT.md             ✅ COMMIT
├─ INSTRUCTION.md       ✅ COMMIT
├─ SAFETY_RULES.md      ✅ COMMIT
├─ AI_GUIDELINES.md     ✅ COMMIT
├─ MASTER_TASK_CHECKLIST.md ✅ COMMIT (updated)
├─ migrations/
│  └─ 001_initial_schema.sql ✅ COMMIT
├─ docs/BLUEPRINT.md    ❌ DON'T COMMIT (internal)
├─ docs/PHASE_0_1_SUMMARY.md ✅ COMMIT
├─ .env                 ❌ DON'T COMMIT (secrets)
└─ src/                 ✅ COMMIT (as you create it)
```

### .gitignore

```
# Never commit these:
.env                    # Your secrets
*.pyc                   # Python bytecode
__pycache__/            # Cache
.vscode/                # IDE config
.idea/                  # IDE config
*.egg-info/             # Package info
.pytest_cache/          # Test cache
.coverage               # Coverage report
venv/                   # Virtual env
```

---

## File Dependencies

```
Docker Compose runs:
├─ docker-compose.yml depends on:
│  ├─ Dockerfile (builds image)
│  ├─ requirements.txt (pip install)
│  ├─ migrations/001_initial_schema.sql (init database)
│  ├─ main.py (entry point)
│  ├─ config.py (configuration)
│  ├─ models.py (imports)
│  └─ .env (environment)

Application runs:
├─ main.py depends on:
│  ├─ config.py (settings)
│  ├─ models.py (Pydantic models)
│  └─ src/ (future phases)

Database works:
├─ migrations/001_initial_schema.sql depends on:
│  └─ PostgreSQL (database server)

Phase 2+ depends on:
├─ src/database/models.py depends on:
│  ├─ models.py (Pydantic)
│  ├─ config.py (settings)
│  └─ migrations/001_initial_schema.sql (schema reference)
└─ src/database/queries.py depends on:
   ├─ src/database/models.py (ORM)
   ├─ models.py (Pydantic)
   └─ config.py (settings)
```

---

## Local Folder Setup Checklist

Print this and check off as you go:

```
FOLDER CREATION:
- [ ] Create payment-recovery-system/ folder
- [ ] Create payment-recovery-system/migrations/ subfolder
- [ ] Create payment-recovery-system/docs/ subfolder

COPY PHASE 0-1 OUTPUT FILES:
- [ ] main.py → payment-recovery-system/
- [ ] config.py → payment-recovery-system/
- [ ] models.py → payment-recovery-system/
- [ ] requirements.txt → payment-recovery-system/
- [ ] Dockerfile → payment-recovery-system/
- [ ] docker-compose.yml → payment-recovery-system/
- [ ] env.example → payment-recovery-system/.env.example
- [ ] 001_initial_schema.sql → payment-recovery-system/migrations/
- [ ] PHASE_0_1_SUMMARY.md → payment-recovery-system/docs/
- [ ] BLUEPRINT.md → payment-recovery-system/docs/

CREATE GOVERNANCE FILES:
- [ ] README.md → payment-recovery-system/
- [ ] SPEC.md → payment-recovery-system/
- [ ] RULES.md → payment-recovery-system/
- [ ] AGENT.md → payment-recovery-system/
- [ ] INSTRUCTION.md → payment-recovery-system/
- [ ] SAFETY_RULES.md → payment-recovery-system/
- [ ] AI_GUIDELINES.md → payment-recovery-system/
- [ ] MASTER_TASK_CHECKLIST.md → payment-recovery-system/

CREATE CONFIG FILES:
- [ ] Copy .env.example → .env
- [ ] Edit .env with Razorpay credentials
- [ ] Create .gitignore

VERIFY:
- [ ] All files in correct locations
- [ ] .env has Razorpay credentials
- [ ] docker-compose up starts without errors
- [ ] curl http://localhost:8000/health returns 200 OK
- [ ] Database tables exist (10 tables)
```

---

## File Sizes (Reference)

```
Code Files:
├─ main.py              ~400 lines
├─ config.py            ~450 lines
├─ models.py            ~500 lines

Config Files:
├─ requirements.txt     ~50 lines
├─ Dockerfile           ~50 lines
├─ docker-compose.yml   ~150 lines
├─ .env.example         ~50 lines

Database:
└─ 001_initial_schema.sql ~300 lines

Governance:
├─ README.md            ~250 lines
├─ SPEC.md              ~800 lines (comprehensive)
├─ RULES.md             ~300 lines
├─ AGENT.md             ~250 lines
├─ INSTRUCTION.md       ~300 lines
├─ SAFETY_RULES.md      ~400 lines
├─ AI_GUIDELINES.md     ~350 lines
└─ MASTER_TASK_CHECKLIST.md ~500 lines

Total: ~6,000+ lines of code, config, and documentation
```

---

## Public vs Internal

### Files You Can Share Publicly

✅ COMMIT & SHARE:
- main.py, config.py, models.py (code)
- Dockerfile, docker-compose.yml (infrastructure)
- README.md, SPEC.md, RULES.md (governance)
- AGENT.md, INSTRUCTION.md (guidance)
- SAFETY_RULES.md, AI_GUIDELINES.md (guidelines)
- MASTER_TASK_CHECKLIST.md (progress)
- migrations/001_initial_schema.sql (schema)

### Files to Keep Private

❌ DO NOT SHARE:
- .env (Razorpay credentials)
- docs/BLUEPRINT.md (your internal spec)
- docs/MASTER_TASK_LIST.md (your internal task decomposition)
- .env.local (local overrides)

---

## Next Steps

1. **Copy all 10 Phase 0-1 output files** into payment-recovery-system/
2. **Copy all 8 governance files** I created into payment-recovery-system/
3. **Create .env** from .env.example
4. **Run docker-compose up** and verify
5. **Start Phase 2** following INSTRUCTION.md
6. **Update MASTER_TASK_CHECKLIST.md** after each task

---

**Total setup time: 20-30 minutes**

