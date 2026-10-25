"""Native-record and full-molecule-group bindings for quick TRAIN panels."""
from __future__ import annotations

import re

from .v3_dev_panel import ALLOWED_ROLES, canonical, molecule_folds


class GroupedTrainingView:
    """Preserve source records while grouping duplicate molecules/isoforms.

    ``group_map`` must come from separately byte-bound source membership
    metadata. A source record UID is deliberately not an identity fallback.
    No targets are read to split, cap or purge the populations.
    """

    def __init__(self, store, dataset_id, fold_id, group_map, *, seed=20261025,
                 max_train_groups=8192, max_validation_groups=2048):
        if any(type(cap) is not int or cap < 1 for cap in (max_train_groups, max_validation_groups)):
            raise ValueError("Positive fixed molecule-group caps required")
        self.__store = store
        self.dataset_id, self.fold_id = str(dataset_id), str(fold_id)
        contract = store.contract(self.dataset_id, self.fold_id)
        self.tasks, self.output_level = tuple(contract["tasks"]), contract["output_level"]
        members, source_uids, molecule_groups = {}, {}, {}
        for role in ALLOWED_ROLES:
            ids = tuple(store.view(self.dataset_id, self.fold_id, role=role))
            uids = tuple(contract["ordered_members"][role])
            if ids != tuple(contract["member_indices"][role]) or len(ids) != len(uids) or len(set(ids)) != len(ids):
                raise ValueError("Frozen source membership/UID association differs")
            members[role] = ids
            for index, uid in zip(ids, uids):
                binding = group_map.get((self.dataset_id, index))
                if (not isinstance(binding, dict) or binding.get("member_uid") != uid
                        or not re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", binding.get("full_inchikey", ""))):
                    raise ValueError("Byte-bound full molecule identity absent or inconsistent")
                if index in source_uids:
                    raise ValueError("Original TRAIN-source roles overlap")
                source_uids[index], molecule_groups[index] = uid, binding["full_inchikey"]
        if self.dataset_id == "expansionrx":
            if members[ALLOWED_ROLES[1]]:
                raise ValueError("The official Expansion contract must remain unchanged")
            assignment = molecule_folds([molecule_groups[i] for i in members[ALLOWED_ROLES[0]]], folds=5, seed=seed)
            original = members[ALLOWED_ROLES[0]]
            members = {ALLOWED_ROLES[0]: tuple(i for i in original if assignment[molecule_groups[i]] != 0),
                       ALLOWED_ROLES[1]: tuple(i for i in original if assignment[molecule_groups[i]] == 0)}
        original_counts = {role: len(values) for role, values in members.items()}
        validation_groups = {molecule_groups[i] for i in members[ALLOWED_ROLES[1]]}
        purged = tuple(i for i in members[ALLOWED_ROLES[0]] if molecule_groups[i] in validation_groups)
        purged_set = set(purged)
        members[ALLOWED_ROLES[0]] = tuple(i for i in members[ALLOWED_ROLES[0]] if i not in purged_set)
        caps = {ALLOWED_ROLES[0]: max_train_groups, ALLOWED_ROLES[1]: max_validation_groups}
        for role, cap in caps.items():
            groups = {molecule_groups[i] for i in members[role]}
            selected = set(sorted(groups, key=lambda group: (canonical([seed, self.dataset_id, group]), group))[:cap])
            members[role] = tuple(i for i in members[role] if molecule_groups[i] in selected)
        if not all(members.values()):
            raise ValueError("Both molecular optimization and inner-validation cohorts must be nonempty")
        if ({molecule_groups[i] for i in members[ALLOWED_ROLES[0]]}
                & {molecule_groups[i] for i in members[ALLOWED_ROLES[1]]}):
            raise ValueError("Chemical groups leak across the inner boundary")
        self.__members = members
        self.__sets = {role: set(values) for role, values in members.items()}
        self.__uids, self.__groups = source_uids, molecule_groups
        self.membership = {"schema": "model_v3_inner_membership_v1", "dataset_id": self.dataset_id,
            "source_fold_id": self.fold_id, "seed": seed,
            "original_training_source_counts": original_counts,
            "purged_optimization_member_indices": list(purged),
            "caps": caps, "target_values_consulted": False,
            "roles": {role: [{"member_index": i, "member_uid": source_uids[i], "full_inchikey": molecule_groups[i]}
                             for i in values] for role, values in members.items()}}
        self.membership_sha256 = canonical(self.membership)

    def view(self, role):
        if role not in ALLOWED_ROLES:
            raise ValueError("Only TRAIN-source inner roles are available")
        return self.__members[role]

    def molecule_group(self, index):
        if not any(index in values for values in self.__sets.values()):
            raise ValueError("Member is outside the selected TRAIN-source cohort")
        return self.__groups[index]

    def get(self, member_index, *, role):
        if role not in ALLOWED_ROLES or member_index not in self.__sets[role]:
            raise ValueError("Target access outside the selected TRAIN-source role")
        sample = self.__store.get(self.dataset_id, member_index)
        if (sample.dataset_id != self.dataset_id or sample.member_index != member_index
                or sample.member_uid != self.__uids[member_index]):
            raise ValueError("Physical source member identity differs")
        return sample
