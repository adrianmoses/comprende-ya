"""Pure unit tests for B2 seed data — no database required."""

from __future__ import annotations

from collections import defaultdict

from mcp_server.b2_seed import CONTRAST_PAIRS, load_concepts, validate_dag


class TestConceptIntegrity:
    def setup_method(self):
        self.metadata, self.concepts = load_concepts()
        self.concept_ids = {c["id"] for c in self.concepts}

    def test_concept_count_matches_metadata(self):
        assert len(self.concepts) == self.metadata["total_concepts"]
        assert len(self.concepts) == 53

    def test_layer_counts_match_metadata(self):
        layer_counts: dict[str, int] = defaultdict(int)
        for c in self.concepts:
            layer_counts[c["layer"]] += 1
        for layer, expected in self.metadata["layers"].items():
            assert layer_counts[layer] == expected, (
                f"Layer '{layer}': expected {expected}, got {layer_counts[layer]}"
            )

    def test_all_concepts_have_required_fields(self):
        required = {"id", "label", "description", "layer", "cefr_range"}
        for c in self.concepts:
            missing = required - set(c.keys())
            assert not missing, (
                f"Concept '{c.get('id', '?')}' missing fields: {missing}"
            )

    def test_no_self_referencing_prerequisites(self):
        for c in self.concepts:
            assert c["id"] not in c.get("prerequisites", []), (
                f"Concept '{c['id']}' lists itself as a prerequisite"
            )

    def test_all_prerequisite_ids_exist(self):
        for c in self.concepts:
            for prereq in c.get("prerequisites", []):
                assert prereq in self.concept_ids, (
                    f"Concept '{c['id']}' has unknown prerequisite '{prereq}'"
                )

    def test_all_related_ids_exist(self):
        for c in self.concepts:
            for rel in c.get("related", []):
                assert rel in self.concept_ids, (
                    f"Concept '{c['id']}' has unknown related '{rel}'"
                )

    def test_prerequisite_dag_is_acyclic(self):
        # Should not raise
        validate_dag(self.concepts)

    def test_all_contrast_pairs_reference_valid_ids(self):
        for a, b in CONTRAST_PAIRS:
            assert a in self.concept_ids, f"Contrast pair has unknown concept '{a}'"
            assert b in self.concept_ids, f"Contrast pair has unknown concept '{b}'"

    def test_contrast_pairs_are_distinct(self):
        for a, b in CONTRAST_PAIRS:
            assert a != b, f"Contrast pair has same concept on both sides: '{a}'"
