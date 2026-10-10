"""Live journeys accept changed releases/content, but reject broken contracts over MCP."""

import json
import shlex
import shutil
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from conftest import STAND_IN, SUITE

pytest_plugins = ["pytester"]

FAMILIES = {
    "include": ("evs", "test_an_include_value_returns_its_section_and_no_other"),
    "identity": (
        "evs",
        "test_a_concept_carries_its_identity_and_the_status_the_platform_publishes",
    ),
    "paths": ("evs", "test_paths_to_root_are_the_platform_s_paths_in_its_order"),
    "maps": ("evs", "test_the_mappings_are_the_concept_s_maps_unchanged_in_order"),
    "relationships": (
        "evs",
        "test_every_relationship_of_the_catalogue_is_listed_by_code_name_and_kind",
    ),
    "element": (
        "cadsr",
        "test_a_data_element_is_its_own_fields_alone_with_its_version_and_statuses",
    ),
    "sections": ("cadsr", "test_each_include_returns_its_section_as_the_platform_gives_it"),
    "cross-domain": (
        "cross_domain",
        "test_the_data_elements_are_the_concept_s_and_with_expansion_its_descendants_too",
    ),
}
PIN = {"terminology": "ncit", "release": "99.test"}
ORIGIN = {
    "release": {"terminology": "ncit", "identifier": "99.test"},
    "source": "evs_rest",
    "servedBy": "live",
    "retrievedAt": "2026-10-10T12:00:00Z",
}
REGISTRY = ORIGIN | {"release": {"registry": "cadsr"}, "source": "cadsr_rest"}
CONCEPT = {
    "code": "C4817",
    "terminology": "ncit",
    "name": "Changed name",
    "active": True,
    "status": "Changed status",
    "provenance": ORIGIN,
}
ELEMENT = {
    "publicId": "2200604",
    "version": "99",
    "longName": "Changed element",
    "context": "New",
    "workflowStatus": "RELEASED",
    "registrationStatus": "Application",
    "dateCreated": "2026-01-01",
    "dateModified": "2026-10-10",
    "provenance": REGISTRY,
}
EVS_SECTIONS = {
    "synonyms": [{"name": "New synonym"}],
    "definitions": [{"definition": "New text"}],
    "properties": [{"code": "P106", "value": "New type"}],
    "semanticType": ["New type"],
}
CDE_SECTIONS = {
    "permissibleValues": [
        {
            "publicId": "998",
            "value": "New",
            "valueMeaning": {
                "publicId": "999",
                "version": "2",
                "longName": "New meaning",
                "concepts": [],
            },
            "provenance": REGISTRY,
        }
    ],
    "valueDomain": {"publicId": "997", "version": "2", "type": "Enumerated"},
    "conceptAssociations": [{"conceptCode": "C1", "longName": "New root", "role": "objectClass"}],
    "alternateNames": [{"name": "New alternate", "type": "Synonym"}],
    "classificationSchemes": [
        {
            "publicId": "996",
            "version": "2",
            "longName": "New scheme",
            "context": "New",
            "items": [],
            "provenance": REGISTRY,
        }
    ],
}


def reply(tool, arguments, result, family=None, broken=None):
    return {
        "tool": tool,
        "arguments": arguments,
        "result": result,
        "family": family,
        "broken": broken,
    }


def replies():
    rows = [
        reply(
            "resolve_release",
            {"terminology": "ncit", "channel": "monthly"},
            {"terminology": "ncit", "channel": "monthly", "version": "99.test"},
        ),
        reply(
            "resolve_registry_release",
            {},
            {
                "published": False,
                "generatedAt": "2026-10-10",
                "sourceDistribution": "releasedCDEsXML-OD.zip",
            },
        ),
    ]
    rows.append(
        reply("get_concept", PIN | {"code": "C4817"}, CONCEPT, "identity", CONCEPT | {"name": ""})
    )
    rows += [
        reply(
            "get_concept",
            PIN | {"code": "C4817", "include": [section]},
            CONCEPT | {section: value},
            "include",
            CONCEPT,
        )
        for section, value in EVS_SECTIONS.items()
    ]
    root = CONCEPT | {"code": "C1", "name": "New root"}
    paths = {"paths": [["C4817", "C1"]], "nodes": [root]}
    rows.append(
        reply(
            "get_concept_hierarchy",
            PIN | {"code": "C4817", "direction": "pathsToRoot"},
            paths,
            "paths",
            paths | {"paths": [["C999", "C1"]]},
        )
    )
    mapping = {
        "targetCode": "1234",
        "targetTerminology": "New target",
        "targetName": "New mapping",
        "type": "Related To",
        "provenance": ORIGIN,
    }
    rows.append(
        reply(
            "get_concept_mappings",
            PIN | {"code": "C4817"},
            {"mappings": [mapping]},
            "maps",
            {"mappings": [mapping | {"targetCode": ""}]},
        )
    )
    relation = {
        "code": "R42",
        "name": "New relation",
        "kind": "role",
        "polarity": "positive",
        "terminology": "ncit",
        "provenance": ORIGIN,
    }
    rows.append(
        reply(
            "list_relationships",
            PIN,
            {"relationships": [relation]},
            "relationships",
            {"relationships": [relation | {"kind": "invented"}]},
        )
    )
    return rows + cde_replies() + cross_replies()


def cde_replies():
    rows = [
        reply(
            "get_data_element",
            {"publicId": "2200604"},
            ELEMENT,
            "element",
            ELEMENT | {"version": []},
        ),
        reply(
            "get_data_element",
            {"publicId": "2200604", "version": "1"},
            ELEMENT | {"version": "1"},
            "element",
            ELEMENT | {"version": "99"},
        ),
    ]
    return rows + [
        reply(
            "get_data_element",
            {"publicId": "2200604", "include": [section]},
            ELEMENT | {section: value},
            "sections",
            ELEMENT,
        )
        for section, value in CDE_SECTIONS.items()
    ]


def cross_replies():
    origin = ORIGIN | {
        "source": "ssis_sparql",
        "registry": {"published": False, "generatedAt": "2026-10-10"},
    }
    item = {
        "dataElement": {"publicId": "882", "version": "9", "longName": "New CDE"},
        "provenance": origin,
    }
    broken = item | {
        "provenance": origin | {"release": {"terminology": "ncit", "identifier": "old"}}
    }
    return [
        reply(
            "find_data_elements_for_concept",
            PIN | {"conceptCode": "C17357", "expandDescendants": expand},
            {"dataElements": [item]},
            "cross-domain",
            {"dataElements": [broken]},
        )
        for expand in (False, True)
    ]


@pytest.fixture
def live_suite(compliant, monkeypatch):
    for module in ("evs", "cadsr", "cross_domain"):
        shutil.copy(SUITE / f"test_{module}.py", compliant.path / "tests")
    # Original cases still read these before the live-mode change; retain real old evidence.
    for relative in (
        "evs/concepts/C4817.json",
        "evs/paths-to-root.json",
        "evs/roles.json",
        "evs/associations.json",
        "cadsr/data-element-2200604.json",
        "cadsr/data-element-2200604-version-1.json",
        "ssis-sparql/data-elements-c17357.json",
        "ssis-sparql/data-elements-c17357-descendants.json",
    ):
        destination = compliant.path / "fixtures/recorded" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SUITE.parent / "fixtures/recorded" / relative, destination)
    monkeypatch.setenv("NCI_SI_ACCEPTANCE_MODE", "live")
    monkeypatch.delenv("NCI_SI_ACCEPTANCE_PREPARE", raising=False)
    server = Path(__file__).with_name("live_content_server.py")
    monkeypatch.setenv(
        "NCI_SI_ACCEPTANCE_SERVER",
        shlex.join([sys.executable, str(server), str(compliant.path / "replies.json")]),
    )
    return compliant


def run_family(suite, family, malformed=False, replacement=None):
    responses = deepcopy(replies())
    for row in responses:
        if malformed and row["family"] == family:
            row["result"] = row["broken"]
        if replacement is not None and row["family"] == family:
            row["result"] = replacement
    (suite.path / "replies.json").write_text(json.dumps(responses))
    module, function = FAMILIES[family]
    result = suite.runpytest_subprocess(
        f"tests/test_{module}.py::{function}",
        "-p",
        "no:cacheprovider",
        "-p",
        STAND_IN,
        "--report=run.json",
        "--disable-warnings",
    )
    tests = json.loads((suite.path / "run.json").read_text())["tests"]
    return result, {node: row["outcome"] for node, row in tests.items()}


@pytest.mark.parametrize("family", FAMILIES)
def test_live_checks_accept_changed_release_and_content(live_suite, family):
    result, outcomes = run_family(live_suite, family)
    assert outcomes and all(
        value == ("not_live" if "[retired]" in node else "passed")
        for node, value in outcomes.items()
    )
    assert result.ret == 0


@pytest.mark.parametrize("family", FAMILIES)
def test_live_checks_reject_malformed_content(live_suite, family):
    result, outcomes = run_family(live_suite, family, malformed=True)
    assert outcomes and all(
        value == ("not_live" if "[retired]" in node else "failed")
        for node, value in outcomes.items()
    )
    assert result.ret == 1


@pytest.mark.parametrize("content", [{}, {"relationships": None}, {"relationships": 42}])
def test_live_catalogue_refuses_a_missing_or_non_list_container(live_suite, content):
    result, outcomes = run_family(live_suite, "relationships", replacement=content)
    assert outcomes and set(outcomes.values()) == {"failed"}
    assert result.ret == 1


@pytest.mark.parametrize(
    ("family", "content"),
    [
        ("maps", {"mappings": []}),
        ("relationships", {"relationships": []}),
        ("cross-domain", {"dataElements": []}),
    ],
)
def test_live_content_accepts_valid_empty_lists(live_suite, family, content):
    result, outcomes = run_family(live_suite, family, replacement=content)
    assert outcomes and set(outcomes.values()) == {"passed"}
    assert result.ret == 0
