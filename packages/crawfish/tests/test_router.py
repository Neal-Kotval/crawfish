"""CRA-136 acceptance: Router & Classifier (conditional routing / branching)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from crawfish.core.context import RunContext
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue, Node, NodeKind
from crawfish.definition import Definition
from crawfish.nodes.router import Classifier, Router, UnroutableLabelError
from crawfish.output import Output
from crawfish.runtime import MockRuntime
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


class _DummyNode(Node):
    """A minimal Node stand-in usable as a branch target."""

    def __init__(self, name: str) -> None:
        self.id = new_id()
        self.name = name
        self.kind = NodeKind.SINK


def _item(kind: str, **extra: JSONValue) -> Output[JSONValue]:
    return Output(output_schema=[], value={"kind": kind, **extra}, produced_by="s")


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore())  # type: ignore[arg-type]


def _definition(tmp_path: Path) -> Definition:
    dest = tmp_path / "full"
    shutil.copytree(FIXTURES / "full", dest)
    return Definition.from_package(str(dest))


def _predicate_router() -> tuple[Router, dict[str, _DummyNode]]:
    branches = {
        "bug": _DummyNode("pr_sink"),
        "question": _DummyNode("slack"),
        "default": _DummyNode("dead_letter"),
    }
    classifier = Classifier.from_predicates(
        {
            "bug": lambda v: v.get("kind") == "bug",
            "question": lambda v: v.get("kind") == "question",
        },
        default="default",
    )
    return Router(branches, classifier), branches


# -- predicate classifier + router --------------------------------------------
def test_predicate_router_routes_each_label_correctly() -> None:
    router, branches = _predicate_router()

    label, node = router.route(_item("bug", title="x"))
    assert label == "bug" and node is branches["bug"]

    label, node = router.route(_item("question"))
    assert label == "question" and node is branches["question"]

    label, node = router.route(_item("praise"))  # unknown -> dead letter
    assert label == "default" and node is branches["default"]


def test_predicate_classifier_first_match_wins() -> None:
    classifier = Classifier.from_predicates(
        {
            "a": lambda v: True,
            "b": lambda v: True,
        },
        default="default",
    )
    assert classifier.classify(_item("anything")) == "a"
    assert classifier.labels == ["a", "b", "default"]


def test_router_is_a_router_node() -> None:
    router, _ = _predicate_router()
    assert router.kind is NodeKind.ROUTER
    assert isinstance(router, Node)


# -- Definition-backed classifier + router ------------------------------------
async def test_definition_backed_classifier_routes_end_to_end(tmp_path: Path) -> None:
    d = _definition(tmp_path)
    # MockRuntime echoes the fluid inputs as JSON; for an item whose value carries no
    # allowed label token, normalisation falls back to the default branch.
    classifier = Classifier.from_definition(d, labels=["urgent", "default"], default="default")
    router = Router(
        branches := {"urgent": _DummyNode("p1"), "default": _DummyNode("dl")}, classifier
    )

    label, node = await router.route_async(_item("calm", title="x"), _ctx(), MockRuntime())
    assert label == "default"
    assert node is branches["default"]


async def test_definition_backed_normalises_known_label(tmp_path: Path) -> None:
    d = _definition(tmp_path)

    def responder(_request: object) -> str:
        return "the label is bug."

    classifier = Classifier.from_definition(d, labels=["bug", "default"], default="default")
    router = Router(
        {"bug": _DummyNode("pr_sink"), "default": _DummyNode("dead_letter")}, classifier
    )

    label, node = await router.route_async(
        _item("bug"),
        _ctx(),
        MockRuntime(responder=responder),  # type: ignore[arg-type]
    )
    assert label == "bug"
    assert node.name == "pr_sink"


# -- assembly-time coverage check ---------------------------------------------
def test_uncovered_label_raises_at_construction() -> None:
    classifier = Classifier.from_predicates(
        {"bug": lambda v: v.get("kind") == "bug"},
        default="default",
    )
    # "bug" has no branch -> unroutable.
    with pytest.raises(UnroutableLabelError):
        Router({"default": _DummyNode("dead_letter")}, classifier)


def test_missing_default_branch_raises() -> None:
    classifier = Classifier.from_predicates(
        {"bug": lambda v: True},
        default="default",
    )
    with pytest.raises(UnroutableLabelError):
        Router({"bug": _DummyNode("pr_sink")}, classifier)


def test_default_must_be_in_labels() -> None:
    with pytest.raises(ValueError):
        Classifier(labels=["a", "b"], default="z")
