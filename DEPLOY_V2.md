# Deploying the v2 corpus to Railway (Phase 5 Step 6, ING-008)

This runbook takes production from the v1 corpus to v2 and back if needed. Nothing here has been
executed against Railway. Every step that spends OpenAI money says so; each needs the owner's go-ahead.

- **What v2 is:** re-ingested books in structure-aware chunks, an ingest-time saints index, and citations with the question or saint and printed pages.
- **Why switch:** on the two-run tune+holdout evaluation (ING-006):
  - Arabic coverage rises from 61.8 % to 75.1 %;
  - English is unchanged (76.6 % vs 76.4 %);
  - recall at equal context rises from 78.6 % to 90.1 %;
  - out-of-corpus refusals stay at 93.4 %;
  - faithfulness rises from 94.9 % to 97.8 %.
- **Cost:** about $0.004 per answer (+12 %; Arabic +42 %). The one-time embedding build is about $0.13.

---

## 1. How v2 gets built on Railway: in-process background build (B) vs `railway ssh` (A)

Both run the same command, `python -m ingestion build --corpus v2 --resume --chroma-dir /app/chroma_db/v2`.
- It embeds the reviewed chunks committed in `data/corpus/v2/chunks.jsonl.gz`, which is exactly the corpus of the Step 2 review and the Step 5 evaluation. PDFs are not re-extracted on Linux, where library output could differ.
- It refuses to start if those chunks do not hash to `data/corpus/v2/manifest.json`.
- It writes only to `/app/chroma_db/v2`, a directory the running v1 API never opens.
- It stops on the first quota or auth error.

| | **A: `railway ssh` + `setsid nohup`** | **B: `BUILD_CORPUS_V2=1` (in-process, child process)** |
|---|---|---|
| Starting it | Open a shell and type the command | Set one env var; the redeploy starts it |
| Survives the laptop or session dropping | Unverified: `setsid nohup` should detach, but I could not confirm Railway keeps it after the ssh session ends | Yes: no session involved |
| Restarts and redeploys | The build dies with the container; you ssh in again and rerun with `--resume` | Every boot relaunches it with `--resume` until the store matches the manifest, then logs `v2 complete` and does nothing |
| Isolation from the API | Separate process | **Separate process too**: a child of `start_backend`, own session, `nice 10`. A crash or quota stop in the build cannot take the API down |
| CPU and memory contention | Same container either way | Same; lowered CPU priority. The HNSW inserts are the heaviest part; watch the memory graph |
| Progress visibility | A log file on the volume (`tail -f`) | Railway service logs: `v2 en: upserted N/6079` per batch |
| Accidental re-runs | Only if someone runs it again (idempotent anyway) | It relaunches on each deploy **while the flag is set**, but only resumes (0 new embeddings once complete). After a quota or auth stop it writes `/app/chroma_db/v2/BUILD_FAILED` and **does not relaunch** until that file is deleted |
| Stopping it | `kill <pid>` over ssh | Remove `BUILD_CORPUS_V2` and redeploy (or `kill` over ssh) |
| Guards | None beyond the build's own checks | Refuses a target outside `RAILWAY_VOLUME_MOUNT_PATH` (st_dev and path); never runs while `CORPUS_VERSION=v2` |
| Tested | The command itself: locally, the full build and a resume from the committed chunks (0 embeddings, store matches) | The same command, plus the launcher decisions in `tests/test_v2_background_build.py` (off, outside volume, failed before, complete, started) |

**Recommendation: B.** It needs no interactive session, and it survives redeploys by resuming. Its progress shows in the service logs, and it cannot retry into a quota problem. A is the fallback if the service's memory is too tight to run the build next to the API. Then run A during a quiet hour and watch it.

- **Timing:** about 5 minutes locally for 10,563 chunks (6.64 M tokens, 47 rate-limit retries). On Railway, allow 5–15 minutes.
- **Space:** 240 MB. The 5 GB volume has ~0.3 GB used.

---

## 2. Environment variables (backend service)

| Variable | v1 today | During the build | After the switch | Notes |
|---|---|---|---|---|
| `CORPUS_VERSION` | unset (= v1) | unset | **`v2`** | Selects directory, collections, saints index |
| `CHROMA_DIR` | `/app/chroma_db` (the volume) | same | same | Unchanged |
| `CHROMA_DIR_V2` | – | unset (= `/app/chroma_db/v2`) | unset | Must stay inside the volume; startup refuses otherwise |
| `BUILD_CORPUS_V2` | – | **`1`** | **remove** | Option B only |
| `AUTO_INGEST_ON_START` | 1 | 1 | 1 or 0 | v2 never ingests at boot; with v1 it still rebuilds an empty v1 |
| `TOP_K_V2` | – | – | unset (= 16) | Matched-context top-k (ING-006); 12 is the logged cost option |
| `MAX_TOP_K` | unset (= 12) | – | unset (= 16 under v2) | |
| `VECTOR_DISTANCE_THRESHOLD` | 1.25 | – | 1.25 | Re-derived for v2, same value |
| `OPENAI_CHAT_MODEL` | gpt-4.1-mini | – | gpt-4.1-mini | Unchanged |

The Vercel frontend needs no new variables.

---

## 3. Runbook

### 3.0 Before starting
1. Merge `phase-5-ingest` (this branch was not pushed; the owner merges).
2. Confirm the OpenAI budget limit is set and has at least $1 headroom. Confirm the volume has 5 GB with ~0.3 GB used.
3. Optional record of v1, via `railway ssh`:

   ```sh
   find /app/chroma_db -path /app/chroma_db/v2 -prune -o -type f -print0 | xargs -0 sha256sum > /tmp/v1.sha
   ```

   It proves later that v1 was never written.

### 3.1 Deploy the code, still serving v1
1. Deploy the merged code with **no** new variables. Behaviour stays v1:
   - prompts, payloads and saint indexes were proven identical (ING-005);
   - the intended changes are the "saints named X" list fix (ING-007) and the frontend's RTL page ranges.
2. Check:

   ```sh
   INTERNAL_API_KEY=… python eval/smoke_v2.py --backend https://<backend> --expect v1 --no-chat
   ```

   It makes no OpenAI calls.

### 3.2 Build v2 in the background (option B) — **OpenAI: ~$0.13**
1. Set `BUILD_CORPUS_V2=1`; Railway redeploys. The v1 API comes up as usual.
2. In the service logs expect:
   - `[start_backend] v2 build started in the background (pid …)`;
   - then `v2 en: upserted …/6079` and `v2 ar: upserted …/4484`;
   - then `v2 store matches data/corpus/v2/manifest.json`.
3. Rules while it runs:
   - **Do not change anything else.** A redeploy only resumes, but it wastes the batches in flight.
   - If the logs show `v2 build stopped:` with a quota or auth error, stop here. The marker `/app/chroma_db/v2/BUILD_FAILED` keeps it from retrying. Fix the key or budget, delete the marker over ssh, and redeploy.
4. Remove `BUILD_CORPUS_V2`. The next boot would only log `v2 complete` anyway.

Option A instead:

```sh
railway ssh
cd /app && setsid nohup python -m ingestion build --corpus v2 --resume --chroma-dir /app/chroma_db/v2 > /app/chroma_db/v2-build.log 2>&1 &
tail -f /app/chroma_db/v2-build.log   # reconnect and rerun the same command if the container restarted
```

### 3.3 Switch
1. Set `CORPUS_VERSION=v2`; Railway redeploys.
2. `start_backend` checks the following before uvicorn starts:
   - the v2 directory exists and sits on the volume;
   - both collections match the manifest's counts and ID hashes.
3. If anything fails it prints `v2 check failed: …` and exits 1. Railway keeps the previous deployment serving, and the restart policy retries 3 times.
4. `/health` must show `"corpus_version": "v2"`.

### 3.4 Verify
1. No OpenAI calls:

   ```sh
   INTERNAL_API_KEY=… python eval/smoke_v2.py --backend https://<backend> --no-chat
   ```

   It checks `/health`, and `/saints` and `/saint-suggestions` in English and Arabic.
2. **OpenAI, ~$0.04** (8 answers with gpt-4.1-mini):

   ```sh
   INTERNAL_API_KEY=… python eval/smoke_v2.py --backend https://<backend>
   ```

   Each answer must have the expected outcome and v2-shaped sources:
   - prayer, Athanasius the Apostolic, St. George (a bare name on `data/saint_defaults.json`: answered about the Cappadocian, with the "Looking for a different St. George?" link, whose menu is checked for free, RET-011), the saints named Gregory, and a FIFA refusal (English);
   - prayer, Paul the First Hermit, and a capital-of-France refusal (Arabic).
3. In the browser, through the Vercel site:
   - one English and one Arabic answer. Sources show the question or saint and the printed pages. Arabic page ranges read in order ("118–119"; `ui-audit/tools/rtl-sources.mjs` checks this locally);
   - a `/calendar` saint link opens the right saint. v1 names still resolve through v2 aliases, so existing links and saved chat chips keep working before step 3.5.
4. Watch the first hour of logs:
   - `outcome=refused` rate close to before (0–1 % of answerable);
   - no `error_type`;
   - latency ~4 s;
   - prompt tokens ~8–9k (Arabic ~12.5k).

### 3.5 Regenerate the calendar's saint links (frontend commit, after the switch)
The links work without this step (aliases). Regenerating uses v2's own names and links more saints. In a local checkout with the v2 store (`chroma_db/v2`, built in Step 3) and the Katameros clone:

```sh
CORPUS_VERSION=v2 .venv/Scripts/python.exe orthodox-site/scripts/calendar/snapshot-saints-index.py
.venv/Scripts/python.exe orthodox-site/scripts/calendar/migrate-overrides-v2.py      # 19 override names -> v2 names, 0 unmapped
cd orthodox-site && npm run calendar:saints -- <path-to-katameros-api clone> && npm test && cd ..
.venv/Scripts/python.exe orthodox-site/scripts/calendar/compare-saint-links.py   # kept / changed / new / lost; fails if a link opens another entry
```

**Done 2026-09-23 (CAL-008, branch `calendar-v2-links`):** 156 English and 196 Arabic links, none lost, every link opening its own entry; the preview below was the plan.

- **Expected result (previewed 2026-09-23, not committed):** 149 English links (82 kept, 67 new, 5 lost) and 184 Arabic (153 kept, 31 new, 12 lost), vs 87 / 165 today.
- **The losses are names the conservative matcher now finds ambiguous:**
  - St. Anthony, Sophia, Basilissa, Philotheus, Irene;
  - the Arabic Abanoub (twice), Philip the Apostle, Abib, Euphrosyne and others.
- Review the diff of `lib/calendar/data/saints.katameros.json`, add overrides for the ones that matter, commit, and deploy Vercel.

### 3.6 Rollback
- **Set `CORPUS_VERSION=v1`**; Railway redeploys onto v1's untouched files.
- If the calendar links were regenerated (3.5), revert that frontend commit too. v1 does not know every v2 display name, though links that fall back to the chat still answer.
- The v2 directory can stay for a retry. To remove it: `rm -rf /app/chroma_db/v2` over ssh.

### 3.7 After two weeks on v2
- Delete v1's files over ssh: `/app/chroma_db/chroma.sqlite3` and the UUID segment folders next to it; **not** `v2/`.
- Then set `CHROMA_DIR_V2` explicitly if the layout is ever changed.
- `python -m ingestion build --corpus v1-legacy` can still rebuild v1 exactly (ING-002).
- Later cleanups:
  - drop the v1 code paths;
  - move production to `TOP_K_V2=12` after a coverage check (ING-007);
  - fix the saints-index residue listed in ING-003/ING-006.
