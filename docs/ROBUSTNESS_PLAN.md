# MQTT bridge robustness roadmap

Actionable follow-up work so the plugin tolerates configuration changes, broker/DB blips, and cold starts **without requiring a Django or process restart**. Items are ordered by impact and dependency.

**Status (2.1.5):** Phases 1–5 below are implemented in code; Phase 6 remains optional.

---

## Phase 0 — Already done

- **Config reload reliability**: `LISTEN nemo_mqtt_reload` plus DB fingerprint polling on the queue interval; `post_delete` on `MQTTConfiguration` notifies the bridge. See [CHANGELOG.md](../CHANGELOG.md) (2.1.4) and [postgres_mqtt_bridge.py](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py).

---

## Phase 1 — Bridge lifecycle when MQTT starts disabled or `start()` fails (P0) — done

**Problem:** [apps.py](../src/NEMO_mqtt_bridge/apps.py) always calls `_start_external_mqtt_service()`. If [PostgresMQTTBridge.start()](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py) returns `False` (no enabled config or MQTT init failure), `running` stays false, the daemon thread exits, and `_auto_service_started` remains true—so **enabling MQTT later never starts the bridge** until Django restarts.

**Approach (pick one consistent strategy):**

1. **Idle `_run` loop (recommended):**  
   - `start()` always sets `running = True` and starts the worker thread after **PostgreSQL LISTEN** is up (and optionally after migrations/config table exist).  
   - If there is no enabled MQTT config, skip `_initialize_mqtt()` in `start()`; `_run` sleeps briefly and only runs fingerprint polling + queue polling (no publish until config appears).  
   - When fingerprint shows an enabled config, call the same path as `_reload_mqtt_config_and_reconnect`.  
   - `apps.py`: do not treat “no config” as failure; avoid logging “start bridge anyway” as the only path—align with env/settings (see Phase 3).

2. **Retry wrapper (alternative):**  
   - Keep `start()` strict, but change `run_bridge_service` to a `while True` loop: if `not mqtt_bridge.start()`, sleep (e.g. 5–10s) and retry, without setting `_auto_service_started` until first successful `start()` *or* until a max retry policy if you want bounded noise.

**Files:** [apps.py](../src/NEMO_mqtt_bridge/apps.py), [postgres_mqtt_bridge.py](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py)

**Acceptance criteria:**

- With MQTT disabled at Django boot, enabling it in the UI (without restart) results in the bridge connecting and draining the queue within one fingerprint interval (default ~2s) plus connect time.  
- No duplicate bridge processes; lock file behavior unchanged.

**Dependencies:** None (can ship before Phase 2).

---

## Phase 2 — Only mark queue rows processed after successful publish (P0) — done

**Problem:** [_process_pending_events](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py) sets `processed=True` after [_process_event](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py) even when [_publish_to_mqtt](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py) bails (not connected, `MQTT_ERR_*`, exception). Events are **lost** for retry.

**Approach:**

1. Change `_publish_to_mqtt` to return `bool` (success).  
2. In `_process_pending_events`, only `save(processed=True)` when publish returns true.  
3. Optional: on failure, `break` the batch so ordering is preserved; next poll retries the same row.  
4. Optional (later): add `retry_count` / `last_error` on `MQTTEventQueue` if you want caps and dead-letter behavior.

**Files:** [postgres_mqtt_bridge.py](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py), optionally [models.py](../src/NEMO_mqtt_bridge/models.py) + migration if you add columns.

**Acceptance criteria:**

- Disconnect MQTT, enqueue events, reconnect: events eventually publish and **then** flip to processed.  
- No silent drop on `publish` failure for the default path.

**Dependencies:** None. Composes well with Phase 1 (idle loop + retry publishes).

---

## Phase 3 — PostgreSQL LISTEN connection recovery (P1) — done

**Problem:** If the dedicated `psycopg2` connection used for `LISTEN` drops, `poll()` can error; the loop logs and sleeps but **does not reconnect or re-`LISTEN`**. Queue polling still drains rows, but NOTIFY latency for events/reload is gone until restart.

**Approach:**

- Add `_ensure_pg_listener()` (or similar): if `pg_conn` is missing/closed or `poll()` raises, close safely, reconnect via existing `pg_connection_mgr.connect_with_retry`, re-execute `LISTEN` on `nemo_mqtt_events` and `nemo_mqtt_reload`.  
- Call from the top of each `_run` iteration (or wrap `poll()` in try/except and reconnect on failure).

**Files:** [postgres_mqtt_bridge.py](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py)

**Acceptance criteria:**

- After killing Postgres session or simulating closed connection, bridge recovers LISTEN without process restart; queue + fingerprint behavior unchanged.

**Dependencies:** None.

---

## Phase 4 — Django DB connections in the bridge thread (P1) — done

**Problem:** Long-lived thread using Django ORM can hold **stale DB connections** (idle timeout, server disconnect).

**Approach:**

- At the start of each `_run` loop iteration (or around each `_process_pending_events` batch), call `django.db.close_old_connections()`.  
- Document that the bridge thread is not a per-request worker.

**Files:** [postgres_mqtt_bridge.py](../src/NEMO_mqtt_bridge/postgres_mqtt_bridge.py)

**Acceptance criteria:**

- No increase in “connection already closed” errors under idle + burst traffic in typical deployments.

**Dependencies:** None.

---

## Phase 5 — `apps.py` policy and dead code (P2) — done

**Problem:** “Start bridge anyway for development” when config is disabled is risky in production; [disconnect_mqtt](../src/NEMO_mqtt_bridge/apps.py) references `self.mqtt_client`, which this `AppConfig` never sets.

**Approach:**

- Introduce a clear setting or env var, e.g. `NEMO_MQTT_BRIDGE_RUN_IN_DJANGO` (default True for backward compat or False for production—**decide explicitly** and document in [README.md](../README.md)).  
- When False, do not spawn the bridge from `ready()`; operators run `python -m NEMO_mqtt_bridge.postgres_mqtt_bridge` (or systemd) separately.  
- Remove or implement `disconnect_mqtt`: e.g. register `django.apps` shutdown hook to `get_mqtt_bridge().stop()` when the bridge was started in-process.

**Files:** [apps.py](../src/NEMO_mqtt_bridge/apps.py), [README.md](../README.md), optionally [CHANGELOG.md](../CHANGELOG.md)

**Acceptance criteria:**

- Documented behavior for embedded vs external bridge process; no misleading `disconnect_mqtt`.

**Dependencies:** Phase 1 makes embedded mode behave well when config is toggled; Phase 5 is mostly policy/docs.

---

## Phase 6 — Optional follow-ups (P3)

| Item | Notes |
|------|--------|
| Single enabled `MQTTConfiguration` | Validation in admin / customization save to reject multiple `enabled=True` rows. |
| TLS / WebSockets for MQTT | Extend [mqtt_connection.py](../src/NEMO_mqtt_bridge/bridge/mqtt_connection.py). |
| Publish acks | QoS 1 + `wait_for_publish` or `on_publish` correlation if you need stronger “broker accepted” semantics before `processed=True`. |
| Metrics / structured logs | Reload reason, publish failures, queue depth, PG reconnect count. |

---

## Suggested implementation order

1. **Phase 1** — unblocks “enable MQTT without restart.”  
2. **Phase 2** — prevents silent event loss.  
3. **Phase 3** + **Phase 4** — operational hardening.  
4. **Phase 5** — production clarity.  
5. **Phase 6** — as needed.

---

## Testing checklist (incremental)

- [ ] Enable MQTT after cold start with plugin-loaded, config initially disabled.  
- [ ] Publish failure (broker down): rows stay unprocessed; recovery after broker up.  
- [ ] Config save (broker host change): reconnect without restart (existing fingerprint tests + integration smoke).  
- [ ] Simulate PG listener disconnect: LISTEN restored, NOTIFY path works again.  
- [ ] Long idle then burst: ORM queries succeed (`close_old_connections`).

Use existing tests under [tests/](../tests/) plus targeted additions per phase (mock MQTT/Postgres where appropriate).
