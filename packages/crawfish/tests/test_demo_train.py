"""Deterministic, mock-backed acceptance test for the Milestone-3 FLAGSHIP train/eval step.

Runs the cumulative triage-bot scenario (``demo/triage-bot/self_improve.py``) entirely
off the mock runtime — NO live model calls — and asserts the load-bearing guarantees of
the train/eval thesis the milestone ships:

* **calibrate** produced a real :class:`CalibrationReport` — the per-metric noise band
  (``rubric_std``) was measured over ``CALIBRATE_RUNS`` seeded re-runs (a non-degenerate,
  reproducible band, not a fabricated zero), with the Brier diagnostic populated;
* **tune under the cost-regularized Objective** selected a winning temperature;
* the **variance-aware promotion gate** returned a reasoned verdict (on the deterministic
  path the cooler candidate's gain clears the calibrated band -> a promotion);
* the winner's knobs **round-trip** through ``state_dict`` / ``load_state`` to a
  bit-identical knob-value sha (sha-identity on the 'weights');
* the winner is **eval()-frozen** before it may fire the consequential Sink;
* the whole run stays within the honest worst-case budget and replays at **$0** (the
  calibrate fan-out is folded into the structural worst-case call count).

These run alongside (not instead of) the prior F + M1 + M2 assertions, which the cumulative
scenario's own ``passed()`` predicate already enforces.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO = REPO_ROOT / "demo" / "triage-bot" / "self_improve.py"


def _load_scenario():
    spec = importlib.util.spec_from_file_location("crawfish_demo_train_test", SCENARIO)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # so dataclass forward-refs resolve
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    if not SCENARIO.exists():  # pragma: no cover - demo always present in-repo
        pytest.skip(f"demo scenario not found at {SCENARIO}")
    return _load_scenario()


@pytest.fixture(scope="module")
def result(module):
    return module.run_self_improvement(live=False)  # deterministic mock path only


# --- the whole cumulative scenario still passes end to end (F + M1 + M2 + M3) ------
def test_scenario_passes_end_to_end(result) -> None:
    assert result.passed(), result.summary()


def test_flagship_step_ok(result) -> None:
    """The Milestone-3 flagship operator certified itself (the composite predicate)."""
    assert result._train_eval_step_ok(), result.summary()


# --- calibrate produced a real CalibrationReport -----------------------------------
def test_calibrate_ran(result, module) -> None:
    assert result.train_ran
    assert result.calib_runs == module.CALIBRATE_RUNS
    assert result.calib_runs >= 2  # a real noise-band sample needs >= 2 observations
    assert result.calib_cases == len(module._SEED_TICKETS)  # full trusted gold (poison dropped)


def test_calibration_noise_band_real_and_bounded(result) -> None:
    """The measured noise band is a genuine, small, reproducible std (not zero, not huge)."""
    assert result.calib_rubric_std > 0.0  # a real run-to-run band (seeded jitter)
    assert result.calib_rubric_std < 0.1  # tight enough that an honest gain can clear it


def test_calibration_brier_populated(result) -> None:
    """The labelled gold yields a real Brier diagnostic (correctness was measurable)."""
    assert result.calib_brier is not None
    assert 0.0 <= result.calib_brier <= 1.0


# --- tune under the cost-regularized Objective -------------------------------------
def test_tuned_the_temperature_knob(result, module) -> None:
    # the flagship tunes the lead agent's decode temperature (a safe, non-consequential knob).
    assert result.tuned_knob == "agent.lead.temperature"
    assert result.tuned_temperature in module._CANDIDATE_TEMPS
    # cooler decoding wins on this classification task (matches the step-7 promotion).
    assert result.tuned_temperature == min(module._CANDIDATE_TEMPS)


# --- the variance-aware promotion gate fired with a reasoned verdict ---------------
def test_variance_gate_promoted_past_the_band(result) -> None:
    verdict = result.promotion
    assert verdict is not None
    # On the deterministic path the cooler candidate's gain clears the calibrated band.
    assert verdict.promoted is True
    assert verdict.cleared_band is True
    assert verdict.regressed is False
    assert verdict.primary == "accuracy"
    assert verdict.primary_gain > verdict.primary_band  # the gain genuinely cleared the band
    assert verdict.reason  # a stated why, either way


# --- state_dict round-trip: sha-identity on the knob VALUES -------------------------
def test_state_dict_roundtrip_sha_identity(result) -> None:
    assert result.state_dict_sha
    assert result.state_roundtrip_ok  # load_state(state_dict) re-minted the same knob sha


# --- eval() freeze gates the consequential Sink ------------------------------------
def test_winner_eval_frozen(result) -> None:
    assert result.train_eval_frozen_sha  # the winner was re-frozen (eval mode) before the Sink


# --- cost honesty: the worst-case bounds the actual spend, replay is $0 ------------
def test_worst_case_bounds_spend_with_calibrate_folded(result) -> None:
    assert result.total_spend_usd <= result.worst_case_usd
    assert result.worst_case_usd <= result.budget_usd
    # mock path: every call is $0, so the whole run (calibrate included) is free.
    assert result.total_spend_usd == 0.0


def test_replay_is_bit_identical(module) -> None:
    """A second deterministic run reproduces the flagship's content identities + decision.

    The knob-value sha, the eval-frozen winner sha, and the promotion decision are
    content-addressed / decision-stable, so they are bit-identical across runs. (The
    measured ``calib_rubric_std`` is NOT asserted bit-identical: ``calibrate`` derives its
    per-run seed schedule from each correction's id, and corrections get fresh random ids
    per run — an honest, intended source of run-to-run noise. The band stays in a tight,
    gate-clearing range every run; ``test_calibration_noise_band_real_and_bounded`` pins
    that range.)"""
    a = module.run_self_improvement(live=False)
    b = module.run_self_improvement(live=False)
    assert a.state_dict_sha == b.state_dict_sha
    assert a.train_eval_frozen_sha == b.train_eval_frozen_sha
    assert a.promotion is not None and b.promotion is not None
    assert a.promotion.promoted == b.promotion.promoted is True


# --- the worst-case call model accounts for the calibrate + objective sweep ---------
def test_worst_case_call_model_includes_calibrate(module) -> None:
    """Dropping the calibrate/objective terms must LOWER the bound — proving they're folded in."""
    n_cases = len(module._SEED_TICKETS)
    n_tune = n_cases // 2
    n_gate = n_cases - n_tune
    n_cand = len(module._CANDIDATE_TEMPS)
    with_calib = module._worst_case_calls(
        n_cases=n_cases, n_tune=n_tune, n_gate=n_gate, n_candidates=n_cand, n_calib=n_cases
    )
    without_calib = module._worst_case_calls(
        n_cases=n_cases, n_tune=n_tune, n_gate=n_gate, n_candidates=n_cand, n_calib=0
    )
    assert with_calib > without_calib
    # the delta is exactly the calibrate + objective-sweep fan-out (x the repair factor).
    expected_delta = (module.CALIBRATE_RUNS * n_cases + n_cand * n_cases) * module._REPAIR_FACTOR
    assert with_calib - without_calib == expected_delta
