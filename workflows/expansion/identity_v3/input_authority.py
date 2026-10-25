"""Consume exact actual547 CPU source pins; never narrow to the final common set."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import os
from pathlib import Path
import threading

from .. import full_queue_v1 as execution
from ..common import require
from workflows.data_v1_final.execution.queue_v1 import shared


@dataclass(frozen=True)
class BoundInput:
    source_id: str
    reference: dict
    expected_stat: dict
    locator: dict
    physical_count: int | None

    def current_path(self):
        require(execution.frame(self.reference["path"]) == self.expected_stat, "Identity source current frame changed: " + self.source_id)
        return Path(self.reference["path"])


def authorize(plan, proof):
    request = proof["request"]
    declared = {pin["path"]: pin for pin in request["source_references"]}
    for key in ("input_pin_receipt", "input_pin_actual_closure", "source_catalog"):
        execution.verify_small(plan[key], declared)
    producer = shared.load(plan["input_pin_receipt"]["path"])
    closure = shared.load(plan["input_pin_actual_closure"]["path"])
    catalog = shared.load(plan["source_catalog"]["path"])
    parent = closure["actual_parent"]
    require(producer["schema"] == "identity_only_current_physical_input_pins_cpu_v1" and
            producer["job_id"] == plan["expected_input_pin_job_id"] == "4520547" and producer["node"] == "compute-0-17" and
            producer["uid"] == 1278 and producer["status"] == "CURRENT_BOUND_INPUT_PINS_COMPLETE" and
            producer["source_catalog"] == plan["source_catalog"] and not producer["pending_locators"] and not producer["blocking_source_ids"] and
            producer["identity_or_role_columns_only"] is True and producer["target_or_feature_values_materialized"] is False and
            producer["identity_export_completed"] is False and len(set(producer["worker_thread_ids_observed"])) == 16,
            "Exact complete547 current physical pins required, not an identity-export assertion")
    require(closure["schema"] == "DATA_V1_IDENTITY_INPUT_PINS_ACTUAL_CLOSURE_V3" and
            closure["receipt"] == plan["input_pin_receipt"] and closure["status"] == "ACTUAL_PRODUCER_COMPLETED_NOT_IDENTITY_ACCEPTANCE" and
            parent["JobIDRaw"] == producer["job_id"] and parent["State"] == "COMPLETED" and parent["ExitCode"] == "0:0" and
            parent["NodeList"] == producer["node"] and parent["Partition"] == "cpu" and int(parent["AllocCPUS"]) == 16,
            "Root actual completed-parent closure must bind547 receipt")
    for pin in (closure["accounting_reference"], closure["raw_sacct_reference"], parent["receipt_reference"]):
        execution.verify_small(pin, declared)
    require(catalog["schema"] == "expansion_identity_source_locator_catalog_v2" and len(catalog["inputs"]) == 76,
            "Whole original76-input catalog required")
    for pin in catalog["metadata_authorities"]:
        execution.verify_small(pin, declared)
    locators = {row["source_id"]: row for row in catalog["inputs"]}
    outputs = {row["source_id"]: row for row in producer["outputs"]}
    require(len(locators) == len(outputs) == len(producer["outputs"]) == 76 and set(locators) == set(outputs), "76-source conservation differs")
    tickets, metadata_refs = {}, []
    for source_id, locator in locators.items():
        row = outputs[source_id]
        require(all(row[key] == locator[key] for key in ("path", "dataset", "kind", "scope_role", "required")) and
                row["status"] == "CURRENT_BYTES_SHA_AND_IDENTITY_METADATA_PINNED" and row["before"] == row["after"] and
                row["reference"]["path"] == locator["path"] and row["reference"]["bytes"] == row["after"]["size"] and
                row["after"]["uid"] == 1278 and row["identity_metadata"]["targets_or_features_materialized"] is False,
                "Actual source-pin identity/count/frame differs: " + source_id)
        for field in ("bytes", "sha256"):
            expected = locator.get("expected_" + field)
            require(expected is None or row["reference"][field] == expected, "Original source version differs: " + source_id)
        expected_count = locator.get("expected_records")
        count = row["identity_metadata"].get("records")
        require(expected_count is None or count == expected_count, "Actual independently counted source rows differ")
        current = execution.frame(locator["path"])
        require(execution.portable(current) == execution.portable(row["after"]), "Only device may differ across producer/consumer nodes")
        tickets[source_id] = BoundInput(source_id, row["reference"], current, locator, count)
        if locator["kind"] == "metadata_json":
            execution.verify_small(row["reference"], declared)
            metadata_refs.append(row["reference"])
    wanted = {ticket.reference["path"]: ticket.reference for ticket in tickets.values() if ticket.locator["kind"] != "metadata_json"}
    actual = {pin["path"]: pin for pin in request["data_references"]}
    require(len(actual) == len(request["data_references"]) and actual == wanted,
            "Root must bind all present body refs; metadata JSON is a disjoint small source")
    return tickets, {"producer": plan["input_pin_receipt"], "actual_closure": plan["input_pin_actual_closure"],
                     "catalog": plan["source_catalog"], "sources": 76, "metadata_source_references": metadata_refs,
                     "body_sources": len(wanted), "device_portability_only": True, "common_filter_applied": False,
                     "all_source_decontamination_accepted": False}


def verify_bodies(tickets, stop):
    barrier = threading.Barrier(16)
    def one(ticket):
        execution.file_pin(ticket.current_path(), expected=ticket.reference, expected_frame=ticket.expected_stat, stop=stop)
        return {"source_id": ticket.source_id, "worker_thread_id": threading.get_native_id()}
    with ThreadPoolExecutor(max_workers=16, initializer=lambda: barrier.wait(timeout=180)) as pool:
        rows = list(pool.map(one, tickets.values()))
    require(len(rows) == 76 and len({row["worker_thread_id"] for row in rows}) == 16, "Actual16-thread current SHA coverage differs")
    return rows


def verify_final(tickets):
    for ticket in tickets.values():
        ticket.current_path()
