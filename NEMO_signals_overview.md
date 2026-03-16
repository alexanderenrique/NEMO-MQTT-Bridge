## NEMO CE – Django signals overview

This file summarizes the Django signal **objects** used in a stock `nemo-ce` tree (plus the legacy in-tree MQTT plugin), so we can see which events are easy candidates to mirror into MQTT.

### Custom NEMO signals

- `**tool_enabled` / `tool_disabled`**
  - **Defined in**: `NEMO/signals.py`
  - **Type**: `django.dispatch.Signal()`
  - **Used in**: `NEMO/views/tool_control.py::determine_tool_status`
  - **Sender**: `Tool` model
  - **Payload**: `instance=<Tool>`
  - **Semantics**:
    - `tool_enabled`: emitted when `tool.operational` flips from `False → True`.
    - `tool_disabled`: emitted when `tool.operational` flips from `True → False`.

### Core model-level signals (Django `models.signals.*`)

These are built‑in Django signals that NEMO connects receivers to; they’re good hook points for additional MQTT publishing.

- **Generic document file cleanup**
  - **Signals**: `models.signals.post_delete`, `models.signals.pre_save`
  - **File**: `NEMO/models.py`
  - **Receivers**:
    - `auto_delete_file_on_document_delete(sender, instance: BaseDocumentModel, **kwargs)`
      - Deletes `instance.document` after any `BaseDocumentModel` subtype is deleted.
    - `auto_update_file_on_document_change(sender, instance: BaseDocumentModel, **kwargs)`
      - Cleans up/updates `instance.document` file on save.
- **Consumable inventory threshold notifications**
  - **Signal**: `models.signals.pre_save`
  - **File**: `NEMO/models.py`
  - **Receiver**: `check_consumable_quantity_threshold(sender, instance: Consumable, **kwargs)`
  - **Semantics**: Before saving a `Consumable`, checks quantity vs. `reminder_threshold` and sends re‑order emails when crossing the threshold (and clears the flag when replenished).
- **Tool image file management**
  - **Signals**: `models.signals.post_delete`, `models.signals.pre_save`
  - **File**: `NEMO/models.py`
  - **Receivers**:
    - `auto_delete_file_on_tool_delete(sender, instance: Tool, **kwargs)`
    - `auto_update_file_on_tool_change(sender, instance: Tool, **kwargs)`
  - **Semantics**: Keep `Tool.image` files in sync with DB lifecycle.
- **Task image file management**
  - **Signals**: `models.signals.post_delete`, `models.signals.pre_save`
  - **File**: `NEMO/models.py`
  - **Receivers**:
    - `auto_delete_file_on_task_image_delete(sender, instance: TaskImages, **kwargs)`
    - `auto_update_file_on_task_image_change(sender, instance: TaskImages, **kwargs)`
- **Chemical / hazard file management**
  - **Signals**: `models.signals.post_delete`, `models.signals.pre_save`
  - **File**: `NEMO/models.py`
  - **Receivers**:
    - `auto_delete_file_on_hazard_delete(sender, instance: ChemicalHazard, **kwargs)`
    - `auto_update_file_on_hazard_change(sender, instance: ChemicalHazard, **kwargs)`
    - `auto_delete_file_on_chemical_delete(sender, instance: Chemical, **kwargs)`
    - `auto_update_file_on_chemical_change(sender, instance: Chemical, **kwargs)`
  - **Semantics**: Remove or update hazard logos and chemical documents alongside model changes.
- **Tool operational outage tracking**
  - **Signal**: `models.signals.post_save`
  - **File**: `NEMO/models.py`
  - **Receiver**: `track_tool_operational_status(sender, instance: Tool, **kwargs)`
  - **Semantics**:
    - On `Tool` save, opens an `UnplannedOutage` if `operational=False` and no open outage exists.
    - Closes the outage (sets `end`) when the tool becomes operational again.

### Signals used by the in-tree `NEMO_mqtt_bridge` plugin

These live under `NEMO/plugins/NEMO_mqtt_bridge/` in the `nemo-ce` tree (the older, bundled plugin). Your standalone `nemo-mqtt-bridge` app already does something similar, but this section documents the Django signal hooks for completeness.

- **MQTT configuration cache invalidation**
  - **Signals**: `post_save`, `post_delete` (from `django.db.models.signals`)
  - **File**: `NEMO/plugins/NEMO_mqtt_bridge/models.py`
  - **Receivers**:
    - `clear_mqtt_config_cache_on_save(sender, instance, **kwargs)`
    - `clear_mqtt_config_cache_on_delete(sender, instance, **kwargs)`
  - **Sender**: `MQTTConfiguration`
  - **Semantics**: Clear cached active config and notify the bridge to reload whenever MQTT config rows are created/updated/deleted.
- **Tool metadata changes**
  - **Signal**: `post_save`
  - **File**: `NEMO/plugins/NEMO_mqtt_bridge/signals.py`
  - **Receiver**: `tool_saved(sender, instance, created, **kwargs)`
  - **Sender**: `Tool`
  - **Semantics**: Publishes a `tool_created` / `tool_updated` event to the MQTT queue with basic tool metadata.
- **Area metadata changes**
  - **Signal**: `post_save`
  - **File**: `NEMO/plugins/NEMO_mqtt_bridge/signals.py`
  - **Receiver**: `area_saved(sender, instance, created, **kwargs)`
  - **Sender**: `Area`
- **Reservation lifecycle**
  - **Signal**: `post_save`
  - **File**: `NEMO/plugins/NEMO_mqtt_bridge/signals.py`
  - **Receiver**: `reservation_saved(sender, instance, created, **kwargs)`
  - **Sender**: `Reservation`
- **Usage events (tool enable/disable)**
  - **Signal**: `post_save`
  - **File**: `NEMO/plugins/NEMO_mqtt_bridge/signals.py`
  - **Receiver**: `usage_event_saved(sender, instance, created, **kwargs)`
  - **Sender**: `UsageEvent`
  - **Semantics**:
    - `instance.end is None` → tool enabled; publishes `.../enabled`.
    - `instance.end is not None` → tool disabled; publishes `.../disabled`.
- **Area access events**
  - **Signal**: `post_save`
  - **File**: `NEMO/plugins/NEMO_mqtt_bridge/signals.py`
  - **Receiver**: `area_access_saved(sender, instance, created, **kwargs)`
  - **Sender**: `AreaAccessRecord`
  - **Semantics**: On creation, publishes an MQTT event with who accessed which area and when.

### Quick ideas for future MQTT hooks

- **Use `tool_enabled` / `tool_disabled`** to reflect *operational* vs. *down* state (distinct from “enabled for a user”).
- **Tap into `track_tool_operational_status*`* or the underlying `post_save(Tool)` to mirror unplanned outage start/end via MQTT.
- **Mirror other lifecycle events** (consumable threshold crossings, chemical/chemical hazard changes, document uploads) by adding MQTT‑oriented receivers to the same Django signals rather than adding new ones.

