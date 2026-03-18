"""Detecção automática do tipo de inversor para o CleanSun."""

CATALOG = {
    "growatt": {
        "models": {
            "MIN 5000TL-X": {"type": "on-grid", "confidence": 0.97, "family": "grid_tie"},
            "MOD 5000TL3-X": {"type": "on-grid", "confidence": 0.97, "family": "grid_tie"},
            "SPF 5000 ES": {"type": "off-grid", "confidence": 0.95, "family": "off_grid"},
            "SPH5000": {"type": "hybrid", "confidence": 0.98, "family": "hybrid"},
            "SPH 5000TL BL-UP": {"type": "hybrid", "confidence": 0.98, "family": "hybrid"},
        },
        "families": {
            "grid_tie": {"type": "on-grid", "confidence": 0.9},
            "off_grid": {"type": "off-grid", "confidence": 0.9},
            "hybrid": {"type": "hybrid", "confidence": 0.92},
        },
        "serial_prefixes": {
            "GRT": {"type": "on-grid", "confidence": 0.86},
            "GOF": {"type": "off-grid", "confidence": 0.84},
            "GHY": {"type": "hybrid", "confidence": 0.88},
        },
    }
}


def normalize_type(value):
    raw = str(value or "").strip().lower()
    if raw in ("híbrido", "hibrido"):
        return "hybrid"
    if raw in ("on-grid", "off-grid", "hybrid"):
        return raw
    return None


def confidence_label(confidence):
    if confidence >= 0.9:
        return "alta"
    if confidence >= 0.65:
        return "média"
    return "baixa"


def metadata_from_snapshot(snapshot):
    keys = ("manufacturer", "brand", "model", "product_family", "firmware_version", "inverter_mode", "serial_number", "inverter_capabilities")
    return {key: snapshot.get(key) for key in keys if snapshot.get(key) not in (None, "")}


def detect_by_model(metadata):
    manufacturer = str(metadata.get("manufacturer") or metadata.get("brand") or "").strip().lower()
    model = str(metadata.get("model") or "").strip().upper()
    family = str(metadata.get("product_family") or "").strip().lower()
    if manufacturer not in CATALOG:
        return None
    catalog = CATALOG[manufacturer]
    if model in catalog.get("models", {}):
        hit = catalog["models"][model]
        return {"detected_inverter_type": hit["type"], "detection_source": "model_lookup", "confidence": hit["confidence"]}
    if family in catalog.get("families", {}):
        hit = catalog["families"][family]
        return {"detected_inverter_type": hit["type"], "detection_source": "family_lookup", "confidence": hit["confidence"]}
    return None


def detect_by_serial(metadata):
    manufacturer = str(metadata.get("manufacturer") or metadata.get("brand") or "").strip().lower()
    serial = str(metadata.get("serial_number") or "").strip().upper()
    if not serial or manufacturer not in CATALOG:
        return None
    prefixes = CATALOG[manufacturer].get("serial_prefixes", {})
    for prefix, hit in prefixes.items():
        if serial.startswith(prefix):
            return {"detected_inverter_type": hit["type"], "detection_source": "serial_lookup", "confidence": hit["confidence"]}
    return None


def infer_by_telemetry(snapshot):
    has_battery = any(snapshot.get(key) not in (None, 0, 0.0, "") for key in ("battery_soc_percent", "battery_voltage_v", "battery_current_a", "battery_power_kw"))
    has_grid_exchange = any(abs(float(snapshot.get(key, 0.0) or 0.0)) > 0.01 for key in ("import_power_w", "export_power_w"))
    has_grid_metrics = any(snapshot.get(key) not in (None, 0, 0.0, "") for key in ("grid_status", "grid_available"))
    backup_mode = bool(snapshot.get("backup_mode_active", False))
    operating_mode = str(snapshot.get("operating_mode") or "").lower()
    if has_battery and (has_grid_exchange or has_grid_metrics):
        confidence = 0.83 if backup_mode or "grid" in operating_mode or "backup" in operating_mode else 0.74
        return {"detected_inverter_type": "hybrid", "detection_source": "telemetry_inference", "confidence": confidence}
    if has_battery and not has_grid_exchange:
        return {"detected_inverter_type": "off-grid", "detection_source": "telemetry_inference", "confidence": 0.72}
    if (has_grid_exchange or has_grid_metrics) and not has_battery:
        return {"detected_inverter_type": "on-grid", "detection_source": "telemetry_inference", "confidence": 0.78}
    return {"detected_inverter_type": None, "detection_source": "telemetry_inference", "confidence": 0.2}


def resolve_effective_inverter_type(detection_state, manual_override=False, manual_selected_type=None):
    manual_type = normalize_type(manual_selected_type)
    detected = normalize_type(detection_state.get("detected_inverter_type")) if detection_state else None
    effective = manual_type if manual_override and manual_type else detected or "hybrid"
    return {
        "detected_inverter_type": detected,
        "detection_source": detection_state.get("detection_source") if detection_state else "unknown",
        "confidence": round(float(detection_state.get("confidence", 0.0) if detection_state else 0.0), 2),
        "confidence_label": confidence_label(float(detection_state.get("confidence", 0.0) if detection_state else 0.0)),
        "manual_override": bool(manual_override and manual_type),
        "manual_selected_type": manual_type,
        "effective_inverter_type": effective,
    }


def detect_inverter_type(snapshot, config):
    metadata = metadata_from_snapshot(snapshot)
    detection = detect_by_model(metadata) or detect_by_serial(metadata) or infer_by_telemetry(snapshot)
    status = resolve_effective_inverter_type(detection, manual_override=config.get("manual_override", False), manual_selected_type=config.get("manual_selected_type"))
    status["metadata"] = metadata
    return status
