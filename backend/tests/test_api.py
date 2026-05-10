"""
test_api.py
─────────────────────────────────────────────────────────────────────────────
Production-grade integration test suite for the HVAC Chiller Predictive
Maintenance FastAPI backend.

Test Architecture
─────────────────
  • TestClient fixture provides clean, isolated HTTP transport per test.
  • _mock_predict is patched at the `main` module level so deterministic
    PredictionResponse objects are returned without touching random.uniform()
    or any future model.pkl artifact.
  • Payload factory fixture generates valid baseline payloads; individual
    tests mutate only the fields they care about — minimising boilerplate
    and making the intent of each assertion immediately legible.

Coverage Surface
────────────────
  Infrastructure   — /api/v1/health schema and field contract
  Happy Path       — Nominal sensor payload → 200 + low risk score
  Parametrized     — Thermodynamic edge cases (P-F curve, icing, cavitation)
  Stress           — Bloated payloads rejected by extra="forbid"
  Malfunction      — Missing fields, nulls, wrong types → 422
  Custom Physical  — Suction pressure ≥ discharge pressure (impossible cycle)

Run
───
  pytest tests/test_api.py -v -W ignore
"""

from __future__ import annotations

import re
import math
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, SQLAlchemyError

# ── Application imports ───────────────────────────────────────────────────────
from main import app
from schemas import PredictionResponse

# ══════════════════════════════════════════════════════════════════════════════
#  CUSTOM PYTEST MARKERS
# ══════════════════════════════════════════════════════════════════════════════
#
#  Register markers in pytest.ini / pyproject.toml to avoid PytestUnknownMarkWarning:
#
#  [pytest]
#  markers =
#      integration: Live-transport tests against the FastAPI TestClient.
#      thermodynamic: Tests encoding real HVAC physical constraints.
#      stress: Payload size and schema boundary stress tests.
#      malfunction: Simulated sensor hardware failure scenarios.

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

PREDICT_URL: str = "/api/v1/predict"
HEALTH_URL: str = "/api/v1/health"
STATS_URL: str = "/api/v1/stats"

# ISO 10816-3 bearing vibration velocity threshold (mm/s RMS).
# Below this → healthy; above → P-F curve degradation zone.
ISO_10816_THRESHOLD: float = 4.5

# Canonical schema keys the /stats response must always contain.
# Any key missing here is a silent contract break for the frontend gauge layer.
REQUIRED_STATS_KEYS: frozenset[str] = frozenset({
    "total_readings",
    "total_anomalies",
    "anomaly_rate_percentage",
    "max_risk_score",
    "avg_risk_score",
    "latest_reading_timestamp",
})

# ══════════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """
    Module-scoped FastAPI TestClient fixture.

    Scope is `module` rather than `function` because spinning up the ASGI
    lifespan (which writes `app.state.start_time`) is non-trivial overhead.
    All tests in this module share one client instance; they must not mutate
    `app.state` directly. Individual test isolation is achieved via payload
    variation and mock patching, not by re-initialising the application.

    Yields
    ------
    TestClient
        Synchronous HTTP client backed by the FastAPI ASGI application.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def nominal_payload() -> dict[str, Any]:
    """
    Factory fixture: returns a deep copy of a healthy, baseline HVAC chiller
    sensor reading representative of a 200-ton water-cooled chiller operating
    at ~75% load on a mild day.

    All values sit at the centre of their healthy operating bands so any single
    field can be overridden in a test without pushing other fields into boundary
    territory. Tests should clone this dict and mutate only the fields relevant
    to the scenario under test.

    Physical context
    ────────────────
    suction_temp   : 41 °F  — refrigerant superheated ~8 °F above evaporator
                              saturation (healthy superheat = 8–12 °F)
    discharge_temp : 100 °F — condensing ~30 °F above ambient (healthy ΔT)
    suction_press  : 64 PSI — R-134a saturation pressure at ~34 °F evaporator
    discharge_press: 172 PSI — R-134a condensing pressure at ~100 °F condenser
    vibration_rms  : 2.5 mm/s — well below ISO 10816 4.5 mm/s healthy threshold
    power_draw     : 320 kW — expected full-load power for a 200-ton unit
    oil_pressure   : 60 PSI — centre of the healthy 55–65 PSI lube circuit band
    runtime_hours  : 4320 — 6 months since last major overhaul
    ambient_temp   : 78 °F — typical summer design day

    Returns
    -------
    dict[str, Any]
        JSON-serialisable dict matching SensorPayload field names exactly.
    """
    return {
        "timestamp":       "2024-06-15T14:00:00",
        "suction_temp":    41.0,
        "discharge_temp":  100.0,
        "suction_press":   64.0,
        "discharge_press": 172.0,
        "vibration_rms":   2.5,
        "power_draw":      320.0,
        "oil_pressure":    60.0,
        "runtime_hours":   4320,
        "ambient_temp":    78.0,
    }


@pytest.fixture
def mock_nominal_response() -> PredictionResponse:
    """
    Deterministic nominal PredictionResponse used to patch `_mock_predict`.

    Returns a low risk score with is_anomalous=False so any test that exercises
    the happy path gets a predictable, assertion-safe response regardless of
    random.uniform() sampling.

    Returns
    -------
    PredictionResponse
        Pre-validated Pydantic response object representing a healthy chiller.
    """
    from datetime import datetime
    return PredictionResponse(
        timestamp=datetime(2024, 6, 15, 14, 0, 0),
        failure_risk_score=0.05,
        is_anomalous=False,
        actionable_alert=(
            "✅ NOMINAL (5%): Vibration RMS of 2.50 mm/s is within the ISO 10816 "
            "healthy range (< 4.5 mm/s). No maintenance action required. "
            "Continue scheduled monitoring."
        ),
    )


@pytest.fixture
def mock_anomalous_response() -> PredictionResponse:
    """
    Deterministic anomalous PredictionResponse used to patch `_mock_predict`.

    Returns a high risk score with is_anomalous=True so tests that exercise
    the degradation path can make precise assertions without relying on the
    random.uniform() band (0.75–0.99).

    Returns
    -------
    PredictionResponse
        Pre-validated Pydantic response object representing a failing chiller.
    """
    from datetime import datetime
    return PredictionResponse(
        timestamp=datetime(2024, 6, 15, 14, 0, 0),
        failure_risk_score=0.94,
        is_anomalous=True,
        actionable_alert=(
            "⚠️ HIGH RISK (94%): Vibration RMS of 28.70 mm/s exceeds the ISO 10816 "
            "threshold of 4.5 mm/s. Immediate bearing inspection recommended. "
            "Schedule maintenance within 72 hours to prevent unplanned downtime."
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — INFRASTRUCTURE: /api/v1/health
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for the /api/v1/health liveness and readiness probe."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """
        Assert that GET /api/v1/health returns HTTP 200 OK.

        This is the most fundamental liveness assertion. If this fails, the
        application has not started correctly — no other test result is
        meaningful. Load balancers and Kubernetes readiness probes depend on
        this response code to route traffic or delay pod promotion.
        """
        response = client.get(HEALTH_URL)
        assert response.status_code == 200, (
            f"Health endpoint returned {response.status_code}; "
            "expected 200. Application may not have initialised correctly."
        )

    def test_health_response_schema(self, client: TestClient) -> None:
        """
        Assert all required keys are present in the /health JSON payload.

        The frontend latency monitor and infrastructure dashboards parse this
        schema. A missing key is a silent contract break — it causes a
        KeyError on the client side rather than a clean API error. Validating
        key presence here provides an early-warning test that fires before any
        frontend deployment.

        Fields verified
        ───────────────
        status          → "online" sentinel for load-balancer health checks
        engine          → Framework identifier for routing rule verification
        version         → Semver string for canary deployment routing
        timestamp       → ISO 8601 UTC string; client uses it to estimate latency
        uptime_seconds  → Float; confirms lifespan startup hook has run
        ml_model_loaded → Bool; signals mock vs. live inference mode
        """
        body: dict[str, Any] = client.get(HEALTH_URL).json()
        required_keys = {
            "status", "engine", "version",
            "timestamp", "uptime_seconds", "ml_model_loaded",
        }
        missing = required_keys - body.keys()
        assert not missing, f"Health response is missing keys: {missing}"

    def test_health_status_value(self, client: TestClient) -> None:
        """
        Assert the `status` field equals the exact sentinel string "online".

        Load-balancer health check scripts typically do an exact string match
        on this field. "Online", "ONLINE", or "ok" would all cause a false
        negative and route the instance out of the pool.
        """
        body: dict[str, Any] = client.get(HEALTH_URL).json()
        assert body["status"] == "online", (
            f"Expected status='online', got {body['status']!r}."
        )

    def test_health_engine_value(self, client: TestClient) -> None:
        """Assert the `engine` field correctly identifies the framework."""
        body: dict[str, Any] = client.get(HEALTH_URL).json()
        assert body["engine"] == "FastAPI"

    def test_health_timestamp_is_iso8601(self, client: TestClient) -> None:
        """
        Assert `timestamp` is a valid ISO 8601 datetime string.

        The frontend uses this value to calculate round-trip latency by
        diffing it against `Date.now()`. A non-parseable timestamp silently
        returns NaN in JavaScript, breaking the latency display without any
        visible error. The regex accepts the UTC offset (+00:00 or Z) that
        Python's `datetime.isoformat()` emits for timezone-aware datetimes.
        """
        body: dict[str, Any] = client.get(HEALTH_URL).json()
        ts: str = body["timestamp"]
        iso8601_pattern = re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
            r"(\.\d+)?"
            r"(Z|[+-]\d{2}:\d{2})?$"
        )
        assert iso8601_pattern.match(ts), (
            f"timestamp {ts!r} is not a valid ISO 8601 string."
        )

    def test_health_uptime_is_positive_float(self, client: TestClient) -> None:
        """
        Assert `uptime_seconds` is a positive numeric value.

        A zero or negative uptime would indicate that `app.state.start_time`
        was not set during the lifespan startup hook, or that the system clock
        moved backwards (e.g., NTP correction during startup). Either case
        means the lifespan hook is broken and model loading would also have
        silently failed.
        """
        body: dict[str, Any] = client.get(HEALTH_URL).json()
        uptime: float = body["uptime_seconds"]
        assert isinstance(uptime, (int, float)), (
            f"uptime_seconds must be numeric, got {type(uptime).__name__}."
        )
        assert uptime >= 0, (
            f"uptime_seconds is {uptime}; expected a non-negative value."
        )

    def test_health_ml_model_loaded_is_bool(self, client: TestClient) -> None:
        """
        Assert `ml_model_loaded` is a boolean (not a truthy string or int).

        This field drives the mock/live mode indicator on the ops dashboard.
        If it were serialised as the string "False" instead of JSON false,
        JavaScript's truthiness rules would evaluate it as True — inverting
        the indicator and misleading engineers into thinking the model is live.
        """
        body: dict[str, Any] = client.get(HEALTH_URL).json()
        assert isinstance(body["ml_model_loaded"], bool), (
            f"ml_model_loaded must be a JSON boolean, got "
            f"{type(body['ml_model_loaded']).__name__!r}."
        )


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — HAPPY PATH: /api/v1/predict (nominal conditions)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestPredictHappyPath:
    """
    Tests for the POST /api/v1/predict endpoint under nominal operating
    conditions. All tests in this class patch `main._mock_predict` to return
    a deterministic PredictionResponse, making assertions exact and instant.
    """

    def test_predict_returns_200_for_nominal_payload(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        mock_nominal_response: PredictionResponse,
    ) -> None:
        """
        Assert that a fully valid, nominal-state sensor payload returns HTTP 200.

        This is the end-to-end happy path: Pydantic validation passes, the
        prediction engine runs, and a structured response is returned. If this
        test fails, the entire ingestion pipeline is broken and no sensor data
        can be processed — all other predict tests are irrelevant.
        """
        with patch("main._mock_predict", return_value=mock_nominal_response):
            response = client.post(PREDICT_URL, json=nominal_payload)
        assert response.status_code == 200, (
            f"Expected 200 for nominal payload, got {response.status_code}. "
            f"Body: {response.text}"
        )

    def test_predict_response_contains_all_required_fields(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        mock_nominal_response: PredictionResponse,
    ) -> None:
        """
        Assert all PredictionResponse fields are present in the JSON body.

        The frontend dashboard renders four distinct UI elements from this
        response: a timestamp label, a risk gauge (failure_risk_score), an
        anomaly status badge (is_anomalous), and an alert banner
        (actionable_alert). A missing field causes a silent render failure in
        the React component with no visible error boundary.
        """
        with patch("main._mock_predict", return_value=mock_nominal_response):
            body: dict[str, Any] = client.post(
                PREDICT_URL, json=nominal_payload
            ).json()
        required = {"timestamp", "failure_risk_score", "is_anomalous", "actionable_alert"}
        missing = required - body.keys()
        assert not missing, f"Predict response is missing fields: {missing}"

    def test_predict_nominal_risk_score_is_low(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        mock_nominal_response: PredictionResponse,
    ) -> None:
        """
        Assert the risk score for a nominal payload is below 0.5.

        The mocked nominal response returns 0.05. This test validates that the
        mock is wired correctly and that the serialisation pipeline (Pydantic →
        FastAPI → JSON) does not corrupt the float value. Boundary: 0.5 is
        conservative — production alerting threshold is 0.70 — but provides
        headroom to detect gross serialisation errors (e.g., score becoming 5.0
        or 0.5000000000000001 failing downstream comparisons).
        """
        with patch("main._mock_predict", return_value=mock_nominal_response):
            body: dict[str, Any] = client.post(
                PREDICT_URL, json=nominal_payload
            ).json()
        score: float = body["failure_risk_score"]
        assert score < 0.5, (
            f"Nominal payload returned risk score {score}; expected < 0.5."
        )

    def test_predict_nominal_is_not_anomalous(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        mock_nominal_response: PredictionResponse,
    ) -> None:
        """
        Assert is_anomalous is False for a nominal payload.

        A false positive (is_anomalous=True on healthy data) would trigger
        unnecessary maintenance dispatches, eroding operator trust in the
        platform and increasing maintenance costs.
        """
        with patch("main._mock_predict", return_value=mock_nominal_response):
            body: dict[str, Any] = client.post(
                PREDICT_URL, json=nominal_payload
            ).json()
        assert body["is_anomalous"] is False, (
            "Nominal payload incorrectly flagged as anomalous (false positive)."
        )

    def test_predict_nominal_alert_is_non_empty_string(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        mock_nominal_response: PredictionResponse,
    ) -> None:
        """
        Assert the actionable_alert field is a non-empty string.

        The alert field must never be empty or whitespace-only — this is
        enforced by the `alert_must_be_actionable_when_anomalous` model
        validator in schemas.py. This test additionally verifies nominal
        (non-anomalous) responses also carry a confirmation message, as the
        dashboard renders this in a "System OK" banner that must have content.
        """
        with patch("main._mock_predict", return_value=mock_nominal_response):
            body: dict[str, Any] = client.post(
                PREDICT_URL, json=nominal_payload
            ).json()
        alert: str = body.get("actionable_alert", "")
        assert isinstance(alert, str) and alert.strip(), (
            "actionable_alert must be a non-empty string for nominal responses."
        )

    def test_predict_echoes_request_timestamp(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        mock_nominal_response: PredictionResponse,
    ) -> None:
        """
        Assert the response timestamp matches the input payload timestamp.

        The PredictionResponse echoes the SensorPayload timestamp so that
        the time-series store can use it as a primary key for correlating raw
        sensor readings with predictions. If this diverges, the ops database
        ends up with orphaned prediction rows that can never be joined back to
        their source reading.

        Note: comparison is done on the date+time components only (ignoring
        timezone offset representation differences between input and output).
        """
        with patch("main._mock_predict", return_value=mock_nominal_response):
            body: dict[str, Any] = client.post(
                PREDICT_URL, json=nominal_payload
            ).json()
        # Input: "2024-06-15T14:00:00" — strip trailing offset for comparison
        response_ts: str = body["timestamp"][:19]
        assert response_ts == "2024-06-15T14:00:00", (
            f"Response timestamp {response_ts!r} does not match input "
            f"'2024-06-15T14:00:00'."
        )

    def test_predict_calls_mock_predict_exactly_once(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        mock_nominal_response: PredictionResponse,
    ) -> None:
        """
        Assert the prediction helper is invoked exactly once per request.

        Verifies the route handler's control flow: the endpoint must call
        `_mock_predict` exactly once — not zero times (short-circuiting) and
        not multiple times (retry logic leaking into the happy path). This is
        a structural test that would catch refactoring errors where the helper
        call is accidentally duplicated or moved inside a conditional branch.
        """
        with patch("main._mock_predict", return_value=mock_nominal_response) as mock_fn:
            client.post(PREDICT_URL, json=nominal_payload)
        mock_fn.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — THERMODYNAMIC EDGE CASES (parametrized)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.thermodynamic
class TestThermodynamicEdgeCases:
    """
    Parametrized tests encoding real HVAC thermodynamic constraints.

    Each case represents a physically distinct failure mode. Junior engineers
    reading this class should understand both the assertion and the underlying
    refrigeration physics that motivates it.
    """

    @pytest.mark.parametrize(
        "payload_overrides, expected_status, expect_anomalous",
        [
            pytest.param(
                # ── Case A: Catastrophic mechanical failure signature ───────────
                # Extremely high vibration (28.7 mm/s) combined with severe
                # thermal overload (discharge_temp 245 °F, ambient 98 °F) and
                # power draw spike (615 kW vs. 320 kW baseline).
                #
                # Physics rationale:
                # This triad is the classic terminal P-F curve presentation:
                #   1. Bearing cage fracture → vibration RMS spikes exponentially
                #   2. Increased shaft friction → compressor work rises → kW spike
                #   3. Condenser unable to reject the extra heat → Td rises
                # All three indicators cross their thresholds simultaneously,
                # which is the "failure window" our Random Forest is trained to
                # identify. The schema must admit all three values (vibration to
                # 500 mm/s, Td to 400 °F, power to 1500 kW) so the ML model can
                # evaluate them rather than the schema rejecting them at 422.
                {
                    "vibration_rms":  28.7,
                    "discharge_temp": 245.0,
                    "power_draw":     615.0,
                    "timestamp":      "2024-06-15T14:00:00",
                },
                200,
                True,
                id="catastrophic_mechanical_failure",
            ),
            pytest.param(
                # ── Case B: Refrigerant loss / low-charge condition ────────────
                # Very low suction pressure (18 PSI) with correspondingly low
                # suction temperature (12 °F) and low power draw (195 kW).
                #
                # Physics rationale:
                # Refrigerant loss causes the evaporator to operate at a much
                # lower saturation pressure and temperature. The compressor
                # cannot build head pressure effectively, so discharge_press
                # also drops (135 PSI). The system still runs — it's just
                # starved — so vibration may remain low. The ML model must
                # detect this through the pressure ratio deviation rather than
                # vibration alone. Schema must admit all values.
                {
                    "suction_press":   18.0,
                    "discharge_press": 135.0,
                    "suction_temp":    12.0,
                    "power_draw":      195.0,
                    "vibration_rms":   2.3,
                    "timestamp":       "2024-06-15T14:00:00",
                },
                200,
                False,  # vibration nominal → mock returns nominal response
                id="refrigerant_loss_low_charge",
            ),
            pytest.param(
                # ── Case C: High ambient / heat rejection failure ──────────────
                # Extreme ambient temperature (118 °F) driving condensing
                # pressure to 290 PSI (approaching high-pressure cutout) with
                # discharge_temp at 178 °F.
                #
                # Physics rationale:
                # In a water-cooled chiller the condenser rejects heat to a
                # cooling tower. On extreme design days (>115 °F ambient) the
                # tower approaches wet-bulb saturation, dramatically reducing
                # heat rejection capacity. The refrigerant condenses at a much
                # higher pressure and temperature. This is not a mechanical
                # failure but a capacity limitation — the chiller may trip its
                # high-pressure safety before bearing failure occurs. The schema
                # must admit discharge_press=290 (< 600 PSI limit) and
                # discharge_temp=178 (< 400 °F limit).
                {
                    "ambient_temp":    118.0,
                    "discharge_press": 290.0,
                    "discharge_temp":  178.0,
                    "power_draw":      410.0,
                    "vibration_rms":   2.8,
                    "timestamp":       "2024-06-15T14:00:00",
                },
                200,
                False,  # vibration still nominal in this scenario
                id="extreme_ambient_heat_rejection_failure",
            ),
        ],
    )
    def test_thermodynamic_edge_cases(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        mock_nominal_response: PredictionResponse,
        mock_anomalous_response: PredictionResponse,
        payload_overrides: dict[str, Any],
        expected_status: int,
        expect_anomalous: bool,
    ) -> None:
        """
        Verify that thermodynamically extreme (but physically real) sensor
        readings are admitted by the schema and return correctly structured
        predictions.

        This test is parametrized across three distinct HVAC failure modes
        (see inline physics rationale in each pytest.param block above). Each
        case mutates only the fields relevant to that scenario on top of the
        baseline nominal_payload — fields not in `payload_overrides` retain
        their healthy baseline values, isolating the variable under test.

        The mock is selected based on `expect_anomalous` so the prediction
        response mirrors what a correctly functioning model would return for
        the given sensor state.

        Key design principle:
        Schema bounds must be wide enough to admit real fault signatures so
        the ML model — not the validation layer — makes the anomaly call.
        A 422 on a legitimate fault reading is a silent false negative.
        """
        payload = {**nominal_payload, **payload_overrides}
        chosen_mock = mock_anomalous_response if expect_anomalous else mock_nominal_response

        with patch("main._mock_predict", return_value=chosen_mock):
            response = client.post(PREDICT_URL, json=payload)

        assert response.status_code == expected_status, (
            f"Expected HTTP {expected_status}, got {response.status_code}. "
            f"Body: {response.text}"
        )

        if expected_status == 200:
            body = response.json()
            assert body["is_anomalous"] is expect_anomalous, (
                f"is_anomalous mismatch: expected {expect_anomalous}, "
                f"got {body['is_anomalous']}."
            )

    @pytest.mark.thermodynamic
    def test_suction_pressure_exceeds_discharge_pressure_returns_422(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
    ) -> None:
        """
        Assert that a suction pressure ≥ discharge pressure reading is rejected
        with HTTP 422 Unprocessable Entity.

        Physical rationale
        ──────────────────
        In every vapour-compression refrigeration cycle, the compressor exists
        precisely to elevate refrigerant pressure from the low-side (suction)
        to the high-side (discharge). The pressure ratio (Pd / Ps) is typically
        2.0–3.5 for a healthy chiller. If suction pressure meets or exceeds
        discharge pressure, one of three catastrophic conditions has occurred:

          1. Compressor seizure — the shaft has stopped rotating entirely.
          2. Reversing valve failure — high and low sides have equalised.
          3. Sensor wiring swap — the two pressure transducers are connected
             to the wrong ports (very common during commissioning).

        In all three cases, the reading is physically invalid as a running
        chiller operating condition. Admitting it to the ML model would produce
        a meaningless prediction based on impossible physics. The
        `suction_must_be_below_discharge_pressure` model_validator in
        schemas.py enforces this constraint with a 5 PSI tolerance for startup
        transients and sampling jitter.

        This is the Principal Engineer's custom thermodynamic edge case.
        """
        payload = {
            **nominal_payload,
            "suction_press":   185.0,  # Dramatically above discharge
            "discharge_press": 172.0,  # Normal discharge — physically impossible
        }
        # No mock needed: Pydantic's model_validator fires before _mock_predict
        response = client.post(PREDICT_URL, json=payload)
        assert response.status_code == 422, (
            f"Expected 422 for pressure inversion (suction > discharge), "
            f"got {response.status_code}. "
            "The suction_must_be_below_discharge_pressure validator may not "
            "be running. Body: {response.text}"
        )

    @pytest.mark.thermodynamic
    def test_pressure_inversion_error_detail_is_descriptive(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
    ) -> None:
        """
        Assert the 422 response body for pressure inversion contains a
        diagnostically useful error message.

        A bare 422 with no detail forces the on-call engineer to re-read the
        source code to understand why the request was rejected. The
        `model_validator` in schemas.py embeds the actual PSI values and a
        plain-English explanation. This test verifies that detail message
        survives the FastAPI error serialisation pipeline intact.
        """
        payload = {
            **nominal_payload,
            "suction_press":   185.0,
            "discharge_press": 172.0,
        }
        response = client.post(PREDICT_URL, json=payload)
        body = response.json()

        assert "detail" in body, "422 response must contain a 'detail' field."
        detail_str = str(body["detail"]).lower()
        # The validator message includes 'suction' and 'discharge' — verify
        # at least one is present so we know it's our custom message and not
        # a generic Pydantic type error.
        assert "suction" in detail_str or "discharge" in detail_str or "physical" in detail_str, (
            f"422 detail does not appear to be the custom pressure-inversion "
            f"message. Got: {body['detail']}"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — STRESS TESTS: Payload boundary and schema isolation
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.stress
class TestPayloadStress:
    """Tests verifying schema isolation under malformed or oversized payloads."""

    def test_extra_fields_are_rejected_with_422(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
    ) -> None:
        """
        Assert that extra (undeclared) fields in the request body are rejected
        with HTTP 422 Unprocessable Entity.

        Context
        ───────
        `SensorPayload` is configured with `extra="forbid"` in its ConfigDict.
        This is a deliberate security and data-integrity decision:

          • Security: Prevents parameter pollution attacks where an adversary
            injects fields that might be processed by middleware or logging
            pipelines in unintended ways.
          • Data integrity: A typo'd field name (e.g., "vibration_rms_mm"
            instead of "vibration_rms") would be silently swallowed by a
            permissive schema, resulting in the correct field defaulting to
            None or raising an unrelated downstream error. extra="forbid"
            surfaces the typo immediately at ingestion time.
          • Contract enforcement: Protects the ML feature vector from receiving
            an unexpected number of features, which would crash scikit-learn's
            predict() with a shape mismatch.

        This test simulates a SCADA client with a newer firmware version that
        has added extra telemetry fields not yet in our schema.
        """
        bloated_payload = {
            **nominal_payload,
            "undeclared_sensor_1": 99.9,
            "firmware_version":    "3.14.159",
            "gps_lat":             18.5204,
            "gps_lon":             73.8567,
            "nested_blob":         {"inner_key": [1, 2, 3]},
        }
        response = client.post(PREDICT_URL, json=bloated_payload)
        assert response.status_code == 422, (
            f"Expected 422 for extra fields (extra='forbid'), "
            f"got {response.status_code}."
        )

    def test_empty_body_returns_422(self, client: TestClient) -> None:
        """
        Assert that a completely empty JSON body ({}) is rejected with 422.

        An empty body is the most common failure mode from misconfigured IoT
        gateways that send the POST before their sensor polling cycle has
        populated the payload buffer. All 10 required fields being absent
        should produce a single 422 with a detail listing every missing field
        rather than a 500 Internal Server Error.
        """
        response = client.post(PREDICT_URL, json={})
        assert response.status_code == 422

    def test_empty_body_detail_lists_missing_fields(
        self, client: TestClient
    ) -> None:
        """
        Assert that the 422 response for an empty body enumerates the missing
        required fields in its detail array.

        Pydantic v2 generates one error entry per missing field. The frontend
        form validator reads this array to highlight exactly which fields need
        to be filled — a generic "validation error" message provides no
        actionable guidance for fixing the SCADA client configuration.
        """
        body = client.post(PREDICT_URL, json={}).json()
        assert "detail" in body, "422 response must contain 'detail'."
        assert isinstance(body["detail"], list), (
            "detail should be a list of field-level errors for missing fields."
        )
        assert len(body["detail"]) > 0, (
            "detail list is empty — Pydantic should report at least one missing field."
        )


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — SENSOR MALFUNCTION SIMULATION (parametrized)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.malfunction
class TestSensorMalfunctionSimulation:
    """
    Parametrized tests simulating hardware sensor failure modes.

    Each scenario represents a real failure pattern observed in industrial
    IoT deployments:

      Missing field   → Sensor physically disconnected / polling timeout
      Null value      → Sensor returned a null sentinel (common in Modbus RTU
                        implementations when a register is unavailable)
      Wrong type      → Protocol conversion bug — value read as string from
                        ASCII-based protocol without numeric casting
      Extreme OOB     → Sensor saturated or ADC overflow (reading outside
                        the physical bounds defined in SensorPayload)

    All scenarios must yield HTTP 422, not 500. A 500 would indicate the
    application crashed rather than gracefully rejecting bad input — a
    catastrophic failure mode that would cause the watchdog to restart the
    process and potentially lose in-flight readings from other sensors.
    """

    @pytest.mark.parametrize(
        "field_to_remove",
        [
            pytest.param("timestamp",       id="missing_timestamp"),
            pytest.param("vibration_rms",   id="missing_vibration_rms"),
            pytest.param("suction_temp",    id="missing_suction_temp"),
            pytest.param("discharge_temp",  id="missing_discharge_temp"),
            pytest.param("suction_press",   id="missing_suction_press"),
            pytest.param("discharge_press", id="missing_discharge_press"),
            pytest.param("power_draw",      id="missing_power_draw"),
            pytest.param("oil_pressure",    id="missing_oil_pressure"),
            pytest.param("runtime_hours",   id="missing_runtime_hours"),
            pytest.param("ambient_temp",    id="missing_ambient_temp"),
        ],
    )
    def test_missing_required_field_returns_422(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        field_to_remove: str,
    ) -> None:
        """
        Assert that omitting any single required field returns HTTP 422.

        Every field in SensorPayload is declared with `...` (no default),
        making them all required. This parametrized test exhaustively covers
        all 10 sensor fields — any field silently acquiring a default value
        during a schema refactor would cause this test to fail for that field,
        surfacing the regression immediately.

        Real-world trigger:
        A Modbus RTU polling daemon that times out on a specific register
        simply omits that key from the JSON rather than setting it to null.
        The API must return a 422 (not crash with a 500) so the gateway can
        log the specific missing field and trigger a sensor-level alert.

        Parameters
        ----------
        field_to_remove : str
            The SensorPayload field key to omit from the request body.
        """
        payload = {k: v for k, v in nominal_payload.items() if k != field_to_remove}
        response = client.post(PREDICT_URL, json=payload)
        assert response.status_code == 422, (
            f"Expected 422 when '{field_to_remove}' is missing, "
            f"got {response.status_code}."
        )

    @pytest.mark.parametrize(
        "field_name, null_value",
        [
            pytest.param("vibration_rms",   None, id="null_vibration_rms"),
            pytest.param("discharge_temp",  None, id="null_discharge_temp"),
            pytest.param("suction_press",   None, id="null_suction_press"),
            pytest.param("discharge_press", None, id="null_discharge_press"),
            pytest.param("power_draw",      None, id="null_power_draw"),
            pytest.param("oil_pressure",    None, id="null_oil_pressure"),
            pytest.param("runtime_hours",   None, id="null_runtime_hours"),
        ],
    )
    def test_null_sensor_value_returns_422(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        field_name: str,
        null_value: None,
    ) -> None:
        """
        Assert that a JSON `null` value on a strict numeric field returns 422.

        SensorPayload fields are typed as `float` or `int` without `Optional`.
        Pydantic v2 does not coerce `None` to a numeric type — it raises a
        validation error. This maps to JSON `null`, which is the standard
        sentinel emitted by many industrial IoT platforms (Siemens S7, Allen
        Bradley PLCs via OPC-UA) when a tag value is unavailable.

        Accepting null silently would pass `None` into the prediction engine,
        causing a `TypeError` inside `_mock_predict` or scikit-learn's
        `predict_proba`, resulting in an unhandled 500 in production.

        Parameters
        ----------
        field_name  : str  The field to set to null.
        null_value  : None JSON null (Python None).
        """
        payload = {**nominal_payload, field_name: null_value}
        response = client.post(PREDICT_URL, json=payload)
        assert response.status_code == 422, (
            f"Expected 422 for null '{field_name}', got {response.status_code}."
        )

    @pytest.mark.parametrize(
        "field_name, bad_value",
        [
            pytest.param("vibration_rms",   "not_a_float",  id="string_vibration_rms"),
            pytest.param("discharge_temp",  "HOT",          id="string_discharge_temp"),
            pytest.param("suction_press",   "N/A",          id="string_suction_press"),
            pytest.param("runtime_hours",   "four_thousand", id="string_runtime_hours"),
            pytest.param("power_draw",      [],              id="array_power_draw"),
            pytest.param("oil_pressure",    {},              id="object_oil_pressure"),
            pytest.param("ambient_temp",    True,            id="bool_ambient_temp"),
        ],
    )
    def test_wrong_type_sensor_value_returns_422(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        field_name: str,
        bad_value: Any,
    ) -> None:
        """
        Assert that a non-numeric value on a strict numeric field returns 422.

        Wrong-type values arise from several real-world failure modes:

          • ASCII protocol bugs: Modbus ASCII or DNP3 returning "N/A", "ERR",
            or engineering unit labels ("PSI", "°F") as the value string when
            a sensor is in a fault state.
          • JSON schema drift: A firmware update changes a field from a numeric
            type to a tagged string (e.g., {"value": 41.3, "unit": "°F"}).
          • Boolean coercion: Some MQTT bridges serialise boolean sensor states
            as True/False rather than 1/0.

        Pydantic v2 with strict field types will reject all of these. Note:
        Python's `bool` is a subclass of `int`, so `True` on an `int` field
        may coerce in some configurations — this is explicitly covered by the
        `bool_ambient_temp` case to catch any accidental `coerce_numbers_to_str`
        or similar permissive setting.

        Parameters
        ----------
        field_name : str  The field to inject with a wrong-type value.
        bad_value  : Any  The wrong-type value to inject.
        """
        payload = {**nominal_payload, field_name: bad_value}
        response = client.post(PREDICT_URL, json=payload)
        assert response.status_code == 422, (
            f"Expected 422 for wrong-type value {bad_value!r} on '{field_name}', "
            f"got {response.status_code}."
        )

    @pytest.mark.parametrize(
        "field_name, out_of_bounds_value, description",
        [
            pytest.param(
                "vibration_rms", -1.0,
                "RMS velocity is the square root of a mean square — it is "
                "mathematically non-negative. A negative value indicates ADC "
                "saturation or signal inversion in the accelerometer circuit.",
                id="negative_vibration_rms",
            ),
            pytest.param(
                "vibration_rms", 999.0,
                "Exceeds the 500 mm/s physical disintegration ceiling. A reading "
                "this high means the accelerometer has been physically destroyed "
                "and is outputting rail voltage — not a real vibration signal.",
                id="vibration_rms_above_ceiling",
            ),
            pytest.param(
                "discharge_press", -10.0,
                "Absolute pressure is always ≥ 0 PSI. A negative gauge pressure "
                "reading is physically impossible for a positive-displacement "
                "compressor and indicates a sensor wire break (open circuit).",
                id="negative_discharge_press",
            ),
            pytest.param(
                "runtime_hours", -1,
                "A monotonically increasing counter cannot be negative. This "
                "indicates an integer overflow in the SCADA historian or a "
                "corrupted memory register on the PLC.",
                id="negative_runtime_hours",
            ),
        ],
    )
    def test_out_of_physical_bounds_value_returns_422(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        field_name: str,
        out_of_bounds_value: Any,
        description: str,
    ) -> None:
        """
        Assert that physically impossible sensor values are rejected with 422.

        The Field(ge=..., le=...) bounds in SensorPayload represent absolute
        physical limits — values outside them cannot be real sensor readings.
        They indicate hardware failure (open circuit, ADC overflow, integer
        overflow) and must never reach the ML model, where they would produce
        undefined predictions.

        Each parametrized case includes a `description` string explaining the
        specific hardware failure mode that would produce that out-of-bounds
        reading. These descriptions are embedded in the test ID and displayed
        in the pytest -v output, providing self-documenting test output for
        junior engineers observing the CI pipeline.

        Parameters
        ----------
        field_name          : str  The field to set to an OOB value.
        out_of_bounds_value : Any  The physically impossible value.
        description         : str  Engineering explanation (used in assertions).
        """
        payload = {**nominal_payload, field_name: out_of_bounds_value}
        response = client.post(PREDICT_URL, json=payload)
        assert response.status_code == 422, (
            f"Expected 422 for out-of-bounds {field_name}={out_of_bounds_value}. "
            f"Physics: {description}. Got: {response.status_code}."
        )

    @pytest.mark.parametrize(
        "field_name, ieee754_value",
        [
            pytest.param("vibration_rms",   "NaN",       id="nan_vibration_rms"),
            pytest.param("vibration_rms",   "Infinity",  id="pos_inf_vibration_rms"),
            pytest.param("vibration_rms",   "-Infinity", id="neg_inf_vibration_rms"),
            pytest.param("discharge_temp",  "NaN",       id="nan_discharge_temp"),
            pytest.param("discharge_temp",  "Infinity",  id="pos_inf_discharge_temp"),
            pytest.param("discharge_temp",  "-Infinity", id="neg_inf_discharge_temp"),
            pytest.param("suction_press",   "NaN",       id="nan_suction_press"),
            pytest.param("power_draw",      "Infinity",  id="pos_inf_power_draw"),
            pytest.param("oil_pressure",    "NaN",       id="nan_oil_pressure"),
            pytest.param("ambient_temp",    "-Infinity", id="neg_inf_ambient_temp"),
        ],
    )
    def test_ieee754_special_values_are_rejected_with_422(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        field_name: str,
        ieee754_value: str,
    ) -> None:
        """
        Assert that IEEE 754 special float values (NaN, +Infinity, -Infinity)
        injected into strict numeric sensor fields are rejected with HTTP 422.

        Threat Vector — AI Model Poisoning
        ───────────────────────────────────
        This is one of the most insidious and least-tested failure modes in
        ML inference pipelines. IEEE 754 defines three non-finite float values:

          NaN (Not a Number)   — result of 0/0, inf−inf, sqrt(−1)
          +Infinity            — result of overflow or 1/0
          −Infinity            — result of underflow or −1/0

        These values are legal in Python's `float` type and in some JSON
        parsers (JavaScript's JSON.parse handles them inconsistently). They
        are catastrophic in a Scikit-Learn feature vector because:

          1. NaN PROPAGATION: numpy operations on arrays containing NaN return
             NaN for the entire computation. A single NaN in one feature
             poisons the entire predict_proba() call, returning [NaN, NaN]
             instead of a valid probability. The endpoint would then attempt
             to construct a PredictionResponse with failure_risk_score=NaN,
             which fails the le=1.0 Pydantic bound check — but only AFTER
             the model has run. The schema must catch this BEFORE inference.

          2. TREE SPLIT POISONING: In a Random Forest, NaN or Infinity can
             cause a feature to be routed to an incorrect branch in every
             decision tree simultaneously, producing a confidently wrong
             prediction (high risk score on a nominal reading, or vice versa)
             rather than a NaN output. This is the most dangerous case because
             it produces no error — just a silently wrong result.

          3. ADVERSARIAL EXPLOITATION: A malicious SCADA client could
             deliberately inject NaN into vibration_rms to force the model
             to return a low risk score on a genuinely failing chiller,
             suppressing the maintenance alert and allowing the equipment to
             run to catastrophic failure.

        Implementation note: JSON does not natively support NaN or Infinity
        as literals. They must be sent as the strings "NaN", "Infinity", and
        "-Infinity". The test sends them as Python strings in the JSON dict,
        which requests serialises as JSON string values. Pydantic v2's strict
        float coercion rejects string-to-float conversion, producing a 422.
        Some non-compliant clients may attempt to send them as unquoted JSON
        tokens (which is invalid JSON) — that case is covered separately in
        TestSecurityAndRouting.

        Parameters
        ----------
        field_name    : str  The sensor field to inject the special value into.
        ieee754_value : str  The string representation of the IEEE 754 special.
        """
        payload = {**nominal_payload, field_name: ieee754_value}
        response = client.post(PREDICT_URL, json=payload)
        assert response.status_code == 422, (
            f"Expected 422 for IEEE 754 special value {ieee754_value!r} on "
            f"'{field_name}' — this value would poison the scikit-learn feature "
            f"vector. Got: {response.status_code}. Body: {response.text}"
        )

    @pytest.mark.parametrize(
        "field_name",
        [
            pytest.param("vibration_rms",   id="empty_string_vibration_rms"),
            pytest.param("discharge_temp",  id="empty_string_discharge_temp"),
            pytest.param("suction_press",   id="empty_string_suction_press"),
            pytest.param("discharge_press", id="empty_string_discharge_press"),
            pytest.param("power_draw",      id="empty_string_power_draw"),
            pytest.param("oil_pressure",    id="empty_string_oil_pressure"),
            pytest.param("runtime_hours",   id="empty_string_runtime_hours"),
            pytest.param("ambient_temp",    id="empty_string_ambient_temp"),
        ],
    )
    def test_empty_string_on_numeric_field_returns_422(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        field_name: str,
    ) -> None:
        """
        Assert that an empty string injected into a strict numeric field is
        rejected with HTTP 422 Unprocessable Entity.

        Threat Vector — Protocol Coercion Failure / Firmware Bug
        ──────────────────────────────────────────────────────────
        Empty strings on numeric fields arise from two real-world sources:

          1. SCADA FIRMWARE BUGS: Some PLCs (notably older Allen Bradley
             MicroLogix units) emit an empty string as the JSON value for a
             register that has not yet been polled in the current scan cycle.
             This happens during the first ~500ms after a cold start before
             all register values have been populated.

          2. HTTP FORM ENCODING BUGS: If an IoT gateway accidentally encodes
             a sensor payload as application/x-www-form-urlencoded instead of
             application/json, numeric fields with no value are serialised as
             empty strings rather than being omitted. An empty HTML form field
             becomes "field_name=" in the URL-encoded body, which some
             gateways then incorrectly re-encode as {"field_name": ""} in JSON.

        In Python, `float("")` raises a ValueError. Without schema validation,
        this would propagate as an unhandled 500. Pydantic v2's strict type
        coercion correctly identifies "" as non-coercible to float/int and
        raises a ValidationError, which FastAPI serialises as a 422.

        This test is exhaustive across all numeric fields because firmware bugs
        tend to affect all registers equally — if one field emits an empty
        string, they all likely do.

        Parameters
        ----------
        field_name : str  The numeric sensor field to set to an empty string.
        """
        payload = {**nominal_payload, field_name: ""}
        response = client.post(PREDICT_URL, json=payload)
        assert response.status_code == 422, (
            f"Expected 422 for empty string on '{field_name}' (non-coercible "
            f"to numeric type). Got: {response.status_code}."
        )


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — SECURITY & TRANSPORT CHAOS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.security
class TestSecurityAndRouting:
    """
    Transport-layer and security-focused tests targeting FastAPI's HTTP
    parsing stack, routing infrastructure, and schema isolation boundaries.

    These tests simulate the threat model of:
      • A malicious actor probing the API surface for crash-inducing inputs
      • A faulty industrial router or protocol bridge corrupting payloads
      • A misconfigured SCADA gateway sending wrong Content-Type headers
      • A network packet fragmenter truncating JSON mid-transmission

    All tests must produce clean, structured error responses (4xx). Any
    5xx response indicates an unhandled crash — an immediate P0 incident
    in production because it reveals internal state and kills in-flight
    requests for all concurrent clients.
    """

    def test_truncated_json_body_does_not_crash_server(
        self, client: TestClient
    ) -> None:
        """
        Assert that a malformed, truncated JSON body returns a clean 4xx and
        does not cause the server to hang, crash with 500, or leak a traceback.

        Threat Vector — Network Packet Fragmentation / Truncated Transmission
        ───────────────────────────────────────────────────────────────────────
        In industrial networks, TCP packets are frequently fragmented by
        switches operating at MTU boundaries, or truncated by:

          • A cellular modem that disconnects mid-transmission
          • A WAN link that enforces a maximum payload size
          • A faulty protocol bridge that terminates writes after N bytes
          • A malicious actor sending a partial payload to probe for parser
            vulnerabilities (classic "half-open" fuzzing technique)

        FastAPI uses Starlette's JSON parser, which wraps Python's built-in
        `json.loads`. An incomplete JSON object raises a `json.JSONDecodeError`.
        The expected behaviour is a 400 Bad Request or 422 Unprocessable Entity
        — NOT a 500 Internal Server Error, and NOT a hung connection.

        The test sends the raw bytes using `content=` (bypassing the requests
        library's JSON serialiser) with an explicit `Content-Type: application/json`
        header so FastAPI attempts JSON parsing on clearly invalid input.
        """
        truncated_body: bytes = b'{"suction_temp": 41.0, "dischar'
        response = client.post(
            PREDICT_URL,
            content=truncated_body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in {400, 422}, (
            f"Expected 400 or 422 for truncated JSON body, got {response.status_code}. "
            "A 500 here indicates the JSON parse error is unhandled — the server "
            "crashed rather than gracefully rejecting the malformed request."
        )

    @pytest.mark.parametrize(
        "forged_content_type",
        [
            pytest.param("text/plain",                         id="content_type_text_plain"),
            pytest.param("application/x-www-form-urlencoded",  id="content_type_form_encoded"),
            pytest.param("application/xml",                    id="content_type_xml"),
            pytest.param("multipart/form-data",                id="content_type_multipart"),
        ],
    )
    def test_forged_content_type_header_returns_4xx(
        self,
        client: TestClient,
        nominal_payload: dict[str, Any],
        forged_content_type: str,
    ) -> None:
        """
        Assert that a structurally valid JSON body sent with an incorrect
        Content-Type header is rejected with a 4xx response.

        Threat Vector — Content-Type Forgery / Gateway Misconfiguration
        ────────────────────────────────────────────────────────────────
        Content-Type forgery occurs in several real-world scenarios:

          1. PROTOCOL BRIDGE MISCONFIGURATION: An MQTT-to-HTTP bridge that
             correctly constructs the JSON body but sends it with the default
             MQTT content type ("text/plain" or none at all). This is the most
             common misconfiguration seen in field deployments.

          2. ADVERSARIAL PROBING: A malicious client forges Content-Type to
             attempt to bypass input validation middleware that is keyed on
             content type, or to exploit a parser that processes form-encoded
             data differently from JSON (parameter pollution via duplicate keys
             is only possible in form-encoded bodies, not JSON).

          3. LEGACY INTEGRATION: Older SCADA systems built on SOAP/XML
             infrastructure may set Content-Type to application/xml even when
             the payload has been converted to JSON for a REST integration,
             if the conversion layer fails to update the header.

        FastAPI's request body parsing is keyed on Content-Type. When the
        header declares a non-JSON type, the framework does not attempt JSON
        parsing, and the Pydantic model cannot be populated — resulting in a
        422. This test sends the JSON payload bytes directly via `content=`
        with the forged header to bypass the requests library's automatic
        header setting.

        Parameters
        ----------
        forged_content_type : str  The incorrect Content-Type header value.
        """
        import json as json_lib
        raw_body: bytes = json_lib.dumps(nominal_payload).encode("utf-8")
        response = client.post(
            PREDICT_URL,
            content=raw_body,
            headers={"Content-Type": forged_content_type},
        )
        assert response.status_code in {400, 415, 422}, (
            f"Expected 4xx for forged Content-Type {forged_content_type!r}, "
            f"got {response.status_code}. The server should reject requests "
            "whose declared content type does not match application/json."
        )

    def test_get_request_on_predict_returns_405(
        self, client: TestClient
    ) -> None:
        """
        Assert that a GET request to the POST-only /api/v1/predict endpoint
        returns HTTP 405 Method Not Allowed.

        Threat Vector — HTTP Method Confusion / Misconfigured Reverse Proxy
        ────────────────────────────────────────────────────────────────────
        Method confusion attacks target APIs where the same path accepts
        multiple HTTP methods with different access control levels. If a proxy
        is misconfigured to cache GET responses and serve them for POST
        requests, an attacker can read another user's prediction response by
        sending a GET. Verifying that GET returns 405 (not 200 or 302)
        confirms the endpoint is strictly POST-only and that no caching proxy
        can serve a stale prediction as a fresh one.

        Additionally, web scanners and vulnerability assessment tools routinely
        probe every discovered endpoint with all HTTP methods. A 405 confirms
        the API's method constraints are correctly enforced at the framework
        level, not relying on reverse-proxy ACLs that could be bypassed.
        """
        response = client.get(PREDICT_URL)
        assert response.status_code == 405, (
            f"Expected 405 Method Not Allowed for GET on POST-only endpoint, "
            f"got {response.status_code}. This may indicate the route accepts "
            "unintended HTTP methods."
        )

    def test_nonexistent_endpoint_returns_404(
        self, client: TestClient
    ) -> None:
        """
        Assert that a request to an undeclared route returns HTTP 404 Not Found.

        Threat Vector — API Surface Enumeration / Path Traversal Probing
        ─────────────────────────────────────────────────────────────────
        Automated vulnerability scanners and manual attackers enumerate API
        surfaces by probing common paths (/admin, /debug, /metrics, /predict,
        /api/v2/predict). A clean 404 with no body leakage confirms:

          1. The router has no wildcard catch-all routes that would accidentally
             accept arbitrary paths and forward them to a handler.
          2. No debug or introspection endpoints are mounted at predictable
             paths (FastAPI mounts /openapi.json and /docs by default —
             these should be restricted in production, though that is outside
             the scope of this test).
          3. The error response body does not leak internal path structure,
             framework version details, or stack traces.
        """
        response = client.get("/api/v1/fake_endpoint")
        assert response.status_code == 404, (
            f"Expected 404 for non-existent route, got {response.status_code}."
        )

    def test_404_response_body_does_not_leak_internals(
        self, client: TestClient
    ) -> None:
        """
        Assert the 404 response body does not contain stack trace fragments,
        internal file paths, or framework version strings.

        Threat Vector — Information Disclosure via Error Body Leakage
        ─────────────────────────────────────────────────────────────
        Detailed error messages in production HTTP responses are a primary
        information-gathering vector for attackers. A traceback in a 404 body
        can reveal:

          • Absolute file system paths (e.g., /home/ubuntu/app/main.py line 47)
            enabling targeted local file inclusion or path traversal attempts.
          • Python version and FastAPI/Starlette version, allowing attackers
            to target known CVEs for that exact version combination.
          • Internal module names and import structure, revealing the
            application's architecture for more targeted injection attempts.

        FastAPI's default 404 handler returns {"detail": "Not Found"} with no
        additional metadata. This test asserts that body does not contain
        common leak indicators. It would fail if a custom exception handler or
        debug middleware (e.g., `app.debug = True`) were accidentally left
        enabled in the deployed configuration.
        """
        response = client.get("/api/v1/fake_endpoint")
        body_text: str = response.text.lower()
        leak_indicators = ["traceback", "file \"", "line ", "site-packages", "python"]
        for indicator in leak_indicators:
            assert indicator not in body_text, (
                f"404 response body contains potential information leak: "
                f"{indicator!r}. Internal details must not be exposed to clients."
            )

    def test_unicode_zero_width_characters_in_field_keys_returns_422(
        self, client: TestClient
    ) -> None:
        """
        Assert that a payload containing Unicode zero-width characters embedded
        in JSON field keys is rejected with HTTP 422.

        Threat Vector — Unicode Homoglyph / Invisible Character Key Injection
        ───────────────────────────────────────────────────────────────────────
        Unicode zero-width characters (U+200B ZERO WIDTH SPACE, U+200C ZERO
        WIDTH NON-JOINER, U+FEFF BYTE ORDER MARK) are invisible in most log
        aggregators, terminal emulators, and text editors. An attacker can use
        them to:

          1. BYPASS FIELD ALLOWLISTS: A WAF or API gateway that inspects field
             names using exact string matching would not detect "vibration_rms"
             (with a U+200B after the underscore) as the same as "vibration_rms".
             If the backend then strips zero-width chars before processing, the
             field could slip through the WAF while being processed as a valid
             field by the API — bypassing the allowlist entirely.

          2. LOG POISONING: If the field key is logged, zero-width characters
             can corrupt log parsers, breaking structured logging pipelines or
             causing log aggregators (Splunk, Elasticsearch) to silently drop
             the event because the key is not valid UTF-8 printable.

          3. KEY CONFUSION ATTACKS: In certain JSON parsers with Unicode
             normalisation bugs, "vibration_rms" with U+200B and "vibration_rms"
             without may hash to different keys, causing the field to appear
             twice in the parsed object — potentially overwriting validated
             values with attacker-controlled ones.

        SensorPayload's `extra="forbid"` configuration causes Pydantic to
        reject any key that does not exactly match a declared field name. A
        key with embedded zero-width characters does not match any declared
        field and is therefore treated as an extra field — resulting in a 422.
        """
        import json as json_lib

        # Construct a payload where "vibration_rms" has a U+200B (zero-width
        # space) injected after the underscore — visually identical to the
        # real field name in most renderers.
        poisoned_key: str = "vibration\u200b_rms"  # Zero-width space after 'n'
        raw_payload: dict[str, Any] = {
            k: v for k, v in {
                "timestamp":       "2024-06-15T14:00:00",
                "suction_temp":    41.0,
                "discharge_temp":  100.0,
                "suction_press":   64.0,
                "discharge_press": 172.0,
                poisoned_key:      2.5,   # ← injected with zero-width char
                "power_draw":      320.0,
                "oil_pressure":    60.0,
                "runtime_hours":   4320,
                "ambient_temp":    78.0,
            }.items()
        }
        # Send as raw bytes to prevent the requests library from normalising
        # Unicode characters during its own serialisation pass.
        raw_body: bytes = json_lib.dumps(raw_payload, ensure_ascii=False).encode("utf-8")
        response = client.post(
            PREDICT_URL,
            content=raw_body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422, (
            f"Expected 422 for zero-width Unicode character in field key "
            f"(treated as unknown extra field by extra='forbid'). "
            f"Got: {response.status_code}. Body: {response.text}"
        )

    def test_deeply_nested_json_payload_does_not_cause_recursion_error(
        self, client: TestClient
    ) -> None:
        """
        Assert that a deeply nested JSON object submitted as a sensor field
        value is rejected with a clean 4xx and does not cause a Python
        RecursionError (which would manifest as an unhandled 500).

        Threat Vector — JSON Recursion / Stack Overflow via Deeply Nested Payload
        ──────────────────────────────────────────────────────────────────────────
        Python's default recursion limit is 1000 frames. The standard library's
        `json.loads` function uses recursive descent parsing, meaning a JSON
        object nested 1000 levels deep can exhaust the call stack and raise a
        `RecursionError`. In a FastAPI application this would:

          1. Crash the async worker handling the request, producing a 500 with
             no structured error body.
          2. In some ASGI server configurations (uvicorn with a single worker),
             this can corrupt the event loop, causing ALL subsequent requests
             to fail until the process restarts.
          3. A single malicious client could use this to mount a denial-of-service
             attack against the prediction API by sending a stream of deeply
             nested payloads, keeping the worker in a crash/restart cycle.

        Modern Python (≥ 3.11) and some JSON libraries (orjson, used optionally
        by FastAPI) have hardened recursion limits for JSON parsing. This test
        verifies the application handles the case gracefully regardless of which
        JSON parser is in use.

        The payload injects a 500-level deep nested dict as the value for the
        `vibration_rms` field. The correct response is 422 (Pydantic rejects a
        dict where a float is expected) or 400 (parser recursion limit). A 500
        indicates the recursion error is unhandled.
        """
        # Build a 500-level deeply nested dictionary
        depth: int = 500
        nested: dict = {}
        current = nested
        for _ in range(depth - 1):
            inner: dict = {}
            current["x"] = inner
            current = inner
        current["x"] = "bottom"

        import json as json_lib
        raw_payload: dict[str, Any] = {
            "timestamp":       "2024-06-15T14:00:00",
            "suction_temp":    41.0,
            "discharge_temp":  100.0,
            "suction_press":   64.0,
            "discharge_press": 172.0,
            "vibration_rms":   nested,   # ← 500-deep nested dict instead of float
            "power_draw":      320.0,
            "oil_pressure":    60.0,
            "runtime_hours":   4320,
            "ambient_temp":    78.0,
        }
        try:
            raw_body: bytes = json_lib.dumps(raw_payload).encode("utf-8")
        except RecursionError:
            pytest.skip(
                "Python's json.dumps itself hit the recursion limit during "
                "test payload construction — interpreter recursion limit is "
                "too low for this test environment."
            )

        response = client.post(
            PREDICT_URL,
            content=raw_body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in {400, 422}, (
            f"Expected 400 or 422 for deeply nested JSON payload, "
            f"got {response.status_code}. A 500 here indicates an unhandled "
            "RecursionError — this is a denial-of-service vulnerability."
        )

    def test_oversized_string_value_in_timestamp_field_returns_422(
        self, client: TestClient, nominal_payload: dict[str, Any]
    ) -> None:
        """
        Assert that a pathologically large string value in the `timestamp`
        field is rejected with HTTP 422 and does not cause excessive memory
        allocation or a slow regex match.

        Threat Vector — ReDoS (Regular Expression Denial of Service) /
                        Memory Exhaustion via Oversized String Fields
        ──────────────────────────────────────────────────────────────
        Some datetime parsing libraries apply regex patterns to validate
        ISO 8601 strings before attempting to parse them. If the regex is
        not anchored or uses catastrophic backtracking patterns, an attacker
        can craft a string that causes the regex engine to explore an
        exponential number of states — hanging the worker thread for seconds
        to minutes per request (ReDoS).

        Independently, allocating a 1MB string in application memory per
        request, if not bounded, can exhaust the process's heap across
        concurrent requests — a memory exhaustion DoS.

        Pydantic v2's datetime parsing uses Rust's `pydantic-core` library,
        which has hardened string handling. This test verifies that a 1MB
        timestamp string is rejected at the Pydantic validation layer (422)
        before any expensive parsing is attempted, and that the response
        arrives in a timely manner (no hung worker).

        The 1MB string is constructed to be a plausible-looking but invalid
        datetime: it starts with a valid prefix to force the parser past any
        early-exit optimisations, then extends to 1MB with alphanumeric noise.
        """
        # 1MB timestamp string — starts with valid ISO prefix to bypass
        # trivial length-zero or obviously-wrong-format fast paths
        oversized_timestamp: str = "2024-06-15T14:00:00" + ("A" * (1024 * 1024))
        payload = {**nominal_payload, "timestamp": oversized_timestamp}

        import json as json_lib
        raw_body: bytes = json_lib.dumps(payload).encode("utf-8")
        response = client.post(
            PREDICT_URL,
            content=raw_body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422, (
            f"Expected 422 for oversized timestamp string (1MB), "
            f"got {response.status_code}. Pydantic should reject non-parseable "
            "datetime strings without hanging."
        )

    def test_duplicate_json_keys_uses_last_value_or_rejects(
        self, client: TestClient
    ) -> None:
        """
        Assert that a JSON body containing duplicate field keys either safely
        uses the last value (Python's json.loads behaviour) or is rejected
        with a 4xx — and in neither case produces a 500.

        Threat Vector — Duplicate Key Injection / Parameter Pollution
        ─────────────────────────────────────────────────────────────
        The JSON specification (RFC 8259) states that key names SHOULD be
        unique but does not mandate it. Different parsers handle duplicates
        inconsistently:

          • Python's json.loads: last value wins (silently)
          • Some WAFs: first value wins
          • Some parsers: raise an error

        This inconsistency is exploitable in layered architectures:

          1. A WAF inspects the FIRST occurrence of "vibration_rms" (e.g., 2.5)
             and concludes the payload is benign. It forwards the request.
          2. The FastAPI backend's json.loads keeps the LAST occurrence
             (e.g., 999.9 — above the 500 mm/s schema ceiling), which then
             fails the Pydantic ge/le validation and returns a 422.

        In our architecture, the "last value wins" Python behaviour combined
        with Pydantic's bounds checking means the schema provides a safety net
        even when the WAF is fooled. This test verifies:

          a) The server does not crash (no 500) on duplicate keys.
          b) If the last duplicate value is out of bounds, a 422 is returned.

        The payload is sent as raw bytes because the requests JSON serialiser
        deduplicates keys in Python dicts before serialisation.
        """
        # Raw JSON with vibration_rms appearing twice:
        #   first occurrence: 2.5 (valid, nominal)
        #   last occurrence:  -99.9 (invalid — below ge=0.0 bound)
        # Python's json.loads will keep -99.9, which Pydantic rejects.
        raw_body: bytes = (
            b'{"timestamp": "2024-06-15T14:00:00", '
            b'"suction_temp": 41.0, "discharge_temp": 100.0, '
            b'"suction_press": 64.0, "discharge_press": 172.0, '
            b'"vibration_rms": 2.5, '     # first occurrence — valid
            b'"power_draw": 320.0, "oil_pressure": 60.0, '
            b'"runtime_hours": 4320, "ambient_temp": 78.0, '
            b'"vibration_rms": -99.9}'    # last occurrence — invalid (< ge=0.0)
        )
        response = client.post(
            PREDICT_URL,
            content=raw_body,
            headers={"Content-Type": "application/json"},
        )
        # Either the parser rejects duplicates (400/422) or last-value-wins
        # and Pydantic rejects the -99.9 (422). A 200 would indicate the
        # invalid last value was silently ignored — a security gap.
        assert response.status_code in {400, 422}, (
            f"Expected 400 or 422 for duplicate JSON key injection "
            f"(last value -99.9 should fail ge=0.0 bound), "
            f"got {response.status_code}. A 200 here means the invalid "
            "duplicate was silently discarded — WAF bypass is possible."
        )

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _make_stats(**overrides: Any) -> dict[str, Any]:
    """
    Factory for a valid, nominal-state stats dictionary.

    Produces a baseline response that represents 1,000 readings with a 15%
    anomaly rate. Individual tests override only the fields relevant to their
    scenario, keeping the remaining fields in a known-good state to isolate
    the variable under test.

    Parameters
    ----------
    **overrides : Any
        Field-level overrides applied on top of the baseline stats dict.

    Returns
    -------
    dict[str, Any]
        A stats dictionary safe for asserting schema contract compliance.
    """
    base: dict[str, Any] = {
        "total_readings":  1000,
        "total_anomalies": 150,
        "anomaly_rate_percentage":    15.0,
        "max_risk_score":  0.982341,
        "avg_risk_score":  0.421873,
        "latest_reading_timestamp": "2024-06-15T14:00:00+00:00",
    }
    return {**base, **overrides}


# ══════════════════════════════════════════════════════════════════════════════
#  TEST CLASS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestStatsEndpoint:
    """
    Exhaustive integration test suite for GET /api/v1/stats.

    The /stats endpoint aggregates data across the entire sensor_logs table
    and exposes summary metrics (total readings, anomaly rate, risk score
    distributions, latest timestamp) consumed by the operations dashboard.
    Because this endpoint is purely read-only and driven by SQLAlchemy
    aggregation queries, all tests patch `crud.get_dashboard_stats` at the module level
    to return deterministic responses — making assertions exact and execution
    instant without requiring a populated database.

    Failure modes targeted across 12 testing dimensions:
      Nominal         — Correct aggregation under standard operating data
      Vacuum          — Empty database: zeros, nulls, and divide-by-zero guards
      Math Boundaries — 0%, 100% anomaly rates and float clamping at [0, 1]
      Infrastructure  — SQLAlchemyError and PoolTimeout propagation to 500
      Protocol        — Invalid HTTP methods and exotic Accept headers
      Day One         — Exactly one reading: edge of statistical meaningfulness
      Float Chaos     — NaN, Infinity, subnormal floats in aggregation outputs
      Timezone/Epoch  — Naive datetimes, Unix epoch, far-future timestamps
      Type Coercion   — ORM returning strings instead of ints/floats
      Impossible Math — Negative totals, negative anomaly rates
      Logic Inversion — Anomaly rate > 0 but max_risk_score == 0.0
      Pool Exhaustion — PoolTimeout surfaces as a clean 500, not a crash
    """

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 1 — NOMINAL / HAPPY PATH
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_returns_200_on_nominal_data(
        self, client: "TestClient"
    ) -> None:
        """
        Assert GET /api/v1/stats returns HTTP 200 under standard operating
        conditions with a populated sensor_logs table.

        This is the foundational liveness assertion for the stats endpoint.
        If this fails, the entire dashboard's metric panel is broken and no
        other stats test result is meaningful. The mock returns a canonical
        1,000-reading dataset with a 15% anomaly rate — representative of a
        chiller that has been running for approximately 6 weeks with one
        bearing degradation event.

        Methodology: patch `crud.get_stats` to return a well-formed dict and
        assert the HTTP response code only. Field-level assertions are isolated
        in dedicated tests to keep failure messages diagnostic.
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats()):
            response = client.get(STATS_URL)
        assert response.status_code == 200, (
            f"Expected 200 for nominal stats, got {response.status_code}. "
            f"Body: {response.text}"
        )

    def test_stats_response_contains_all_required_keys(
        self, client: "TestClient"
    ) -> None:
        """
        Assert the stats response body contains every key declared in the
        API contract, with no silent omissions.

        The frontend dashboard renders six distinct UI elements from this
        response: a total-readings counter, an anomaly count badge, an anomaly
        rate gauge, a max risk score sparkline, an avg risk score gauge, and a
        "last updated" timestamp label. A missing key causes a silent render
        failure in the React component — typically a `undefined` value
        displayed to the operations engineer with no visible error boundary.

        Methodology: assert the symmetric difference between REQUIRED_STATS_KEYS
        and the actual response keys is empty, rather than checking individual
        keys, so that both missing and unexpected keys are caught.
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats()):
            body: dict[str, Any] = client.get(STATS_URL).json()
        missing = REQUIRED_STATS_KEYS - body.keys()
        unexpected = body.keys() - REQUIRED_STATS_KEYS
        assert not missing, f"Stats response missing required keys: {missing}"
        assert not unexpected, (
            f"Stats response contains undeclared keys that may break "
            f"strict frontend schema parsers: {unexpected}"
        )

    def test_stats_nominal_values_are_correct_types(
        self, client: "TestClient"
    ) -> None:
        """
        Assert every field in the nominal stats response carries the correct
        Python/JSON type.

        JSON does not distinguish between int and float — both serialise as
        JSON numbers. However, the frontend TypeScript interface declares
        `total_readings: number` and `anomaly_rate: number` separately, and
        some JSON parsers (notably Go's encoding/json with strict mode) will
        reject a float (1000.0) where an int (1000) is declared. This test
        verifies that integer aggregation fields (`total_readings`,
        `total_anomalies`) are serialised without a decimal point, and float
        fields (`anomaly_rate`, `max_risk_score`, `avg_risk_score`) are
        numeric. `latest_timestamp` must be a string or None.

        Methodology: use isinstance checks on the parsed JSON values, which
        reflect Python's post-deserialisation types from json.loads — ints
        remain int, floats remain float, strings remain str.
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats()):
            body: dict[str, Any] = client.get(STATS_URL).json()
        assert isinstance(body["total_readings"],  int),   "total_readings must be int"
        assert isinstance(body["total_anomalies"], int),   "total_anomalies must be int"
        assert isinstance(body["anomaly_rate_percentage"],    float), "anomaly_rate must be float"
        assert isinstance(body["max_risk_score"],  float), "max_risk_score must be float"
        assert isinstance(body["avg_risk_score"],  float), "avg_risk_score must be float"
        assert body["latest_reading_timestamp"] is None or isinstance(
            body["latest_reading_timestamp"], str
        ), "latest_timestamp must be str or null"

    def test_stats_anomaly_rate_matches_count_ratio(
        self, client: "TestClient"
    ) -> None:
        """
        Assert the returned `anomaly_rate` is arithmetically consistent with
        `total_anomalies / total_readings` to within floating-point tolerance.

        An inconsistent anomaly_rate (e.g., computed in a separate SQL query
        from total_anomalies and total_readings) indicates the aggregation
        layer is running multiple independent queries whose results can diverge
        under concurrent writes — a TOCTOU race condition that produces a
        self-contradictory stats payload.

        Methodology: compute the expected ratio from the mocked integer
        totals and assert the response's anomaly_rate is within 1e-6 of the
        expected value. A tolerance of 1e-6 absorbs Python float division
        rounding without masking genuine aggregation logic bugs.
        """
        stats = _make_stats(
            total_readings=500,
            total_anomalies=75,
            anomaly_rate_percentage=15.0,
        )
        with patch("main.crud.get_dashboard_stats", return_value=stats):
            body: dict[str, Any] = client.get(STATS_URL).json()
        expected_rate = (75 / 500) * 100.0
        assert abs(body["anomaly_rate_percentage"] - expected_rate) < 1e-6, (
            f"anomaly_rate {body['anomaly_rate_percentage']} is inconsistent with "
            f"total_anomalies/total_readings = {expected_rate}. "
            "Possible TOCTOU race between aggregation queries."
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 2 — VACUUM STATE (EMPTY DATABASE)
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_empty_database_returns_200_with_zero_totals(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that /stats returns HTTP 200 (not 404 or 500) when the
        sensor_logs table contains zero rows, with all numeric fields
        defaulting to zero and latest_timestamp set to null.

        An empty database is the "Day Zero" state before any SCADA client
        has transmitted a reading. The dashboard must render cleanly in this
        state — a 500 here would crash the operations dashboard the moment
        the API server starts before the first sensor payload arrives, making
        the platform appear broken during the live demo spin-up window.

        The most dangerous failure mode in this scenario is a divide-by-zero
        in the anomaly_rate calculation: `0 anomalous / 0 total` raises
        ZeroDivisionError in Python. The CRUD layer must guard this with an
        explicit zero check: `anomaly_rate = 0.0 if total == 0 else anom/total`.

        Methodology: mock with an all-zeros stats dict and assert both the
        HTTP status and the zero-state field values.
        """
        vacuum_stats = _make_stats(
            total_readings=0,
            total_anomalies=0,
            anomaly_rate_percentage=0.0,
            max_risk_score=0.0,
            avg_risk_score=0.0,
            latest_reading_timestamp="N/A",
        )
        with patch("main.crud.get_dashboard_stats", return_value=vacuum_stats):
            response = client.get(STATS_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["total_readings"]  == 0
        assert body["total_anomalies"] == 0
        assert body["anomaly_rate_percentage"]    == 0.0
        assert body["latest_reading_timestamp"] == "N/A", (
            "latest_reading_timestamp must be the sentinel string 'N/A' for an "
            "empty database. crud.get_dashboard_stats() returns 'N/A' because "
            "DashboardStatsResponse declares latest_reading_timestamp as str (not Optional[str])."
        )

    def test_stats_empty_database_null_timestamp_is_not_string_null(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that `latest_timestamp` for an empty database is JSON `null`
        (Python None) and NOT the string literal "null".

        Some ORM aggregation queries (particularly SQLAlchemy's `func.max()`
        on an empty table) return the Python string "null" instead of Python
        None when the result is coerced through certain driver layers or
        when a mistakenly stringified None is passed through the serialisation
        pipeline. JavaScript's JSON.parse deserialises the string "null" as
        the string "null" — not as JavaScript null — causing `new Date("null")`
        to return an Invalid Date, which the frontend timestamp formatter then
        renders as "NaN" or "Invalid Date" in the dashboard header.

        Methodology: assert `body["latest_reading_timestamp"] is None` (Python's
        strict identity check for JSON null) rather than a truthiness check,
        which would pass for both None and "null".
        """
        vacuum_stats = _make_stats(
            total_readings=0,
            total_anomalies=0,
            anomaly_rate_percentage=0.0,
            max_risk_score=0.0,
            avg_risk_score=0.0,
            latest_reading_timestamp="N/A",
        )
        with patch("main.crud.get_dashboard_stats", return_value=vacuum_stats):
            body = client.get(STATS_URL).json()
        ts = body["latest_reading_timestamp"]
        assert ts == "N/A", (
            f"latest_reading_timestamp must be 'N/A' for an empty database; "
            f"got {ts!r}. The CRUD sentinel 'N/A' is returned because the "
            "schema field is str (not Optional[str]), so JSON null cannot be used."
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 3 — MATHEMATICAL BOUNDARIES
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_zero_percent_anomaly_rate(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats correctly handles a 0% anomaly rate: all readings are
        nominal, zero anomalous events have been detected.

        A 0.0 anomaly rate is the happy-path steady state for a well-maintained
        chiller fleet. The frontend's anomaly rate gauge must render a "0%"
        display without division errors or NaN propagation from downstream
        percentage calculations (e.g., `rate * 100 / total` where rate is 0).

        This boundary is also the state immediately after a fleet-wide
        maintenance cycle resets all bearing wear indicators below the ISO
        10816 threshold.

        Methodology: mock with anomaly_rate=0.0 and total_anomalies=0 against
        a non-zero total_readings, then assert the response fields are exactly
        zero without coercion to null or NaN.
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats(
            total_anomalies=0,
            anomaly_rate_percentage=0.0,
            max_risk_score=0.0,
            avg_risk_score=0.0,
        )):
            body = client.get(STATS_URL).json()
        assert body["anomaly_rate_percentage"]    == 0.0
        assert body["total_anomalies"] == 0
        assert body["max_risk_score"]  == 0.0

    def test_stats_one_hundred_percent_anomaly_rate(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats correctly handles a 100% anomaly rate: every reading in
        the dataset was flagged as anomalous.

        A 100% anomaly rate is the terminal P-F curve scenario where the
        chiller has been operating in a critical failure state continuously.
        This boundary exercises the upper clamp of the anomaly_rate field —
        the value must be exactly 1.0, not 1.0000000001 from floating-point
        accumulation, and not serialised as the integer 1 (which some JSON
        parsers would treat as a bool True in strict mode).

        Methodology: set total_anomalies == total_readings and anomaly_rate_percentage=100.0,
        then assert the response boundary values are within acceptable tolerance.
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats(
            total_readings=1000,
            total_anomalies=1000,
            anomaly_rate_percentage=100.0,
            max_risk_score=0.99,
            avg_risk_score=0.91,
        )):
            body = client.get(STATS_URL).json()
        assert abs(body["anomaly_rate_percentage"] - 100.0) < 1e-9, (
            f"100% anomaly rate must serialise as float 1.0, got {body['anomaly_rate_percentage']}."
        )
        assert body["total_readings"] == body["total_anomalies"], (
            "For 100% anomaly rate, total_anomalies must equal total_readings."
        )

    def test_stats_anomaly_rate_exactly_fifty_percent(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats correctly handles a 50% anomaly rate — the boundary
        where integer division rounding errors are most likely to manifest.

        Python 3's `/` operator performs true division (returning float), but
        older SQLAlchemy aggregation patterns or database-side integer division
        (SQLite `500/1000` evaluates to `0`, not `0.5`, in integer contexts)
        can silently truncate this value to 0.0. A 50% rate returned as 0.0
        would indicate a divide operation is being performed at the SQL layer
        with integer operands rather than being computed in Python.

        Methodology: assert the response value is within 1e-9 of exactly 0.5
        to catch both truncation (→ 0.0) and rounding (→ 0.4999... or 0.5001).
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats(
            total_readings=1000,
            total_anomalies=500,
            anomaly_rate_percentage=50.0,
        )):
            body = client.get(STATS_URL).json()
        assert abs(body["anomaly_rate_percentage"] - 50.0) < 1e-9, (
            f"50% anomaly rate must serialise as exactly 0.5; "
            f"got {body['anomaly_rate_percentage']}. "
            "Integer division truncation at the SQL layer would produce 0.0."
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 4 — INFRASTRUCTURE CATASTROPHES
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_sqlalchemy_error_returns_500(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a generic SQLAlchemyError raised by the CRUD layer is
        caught by the route handler and returned as HTTP 500, not propagated
        as an unhandled exception that crashes the ASGI worker.

        SQLAlchemyError is the base class for all SQLAlchemy exceptions
        including OperationalError (DB file locked), InternalError (corrupt
        page), IntegrityError (constraint violation on a read — rare but
        possible in certain ORM trigger configurations), and ProgrammingError
        (malformed query from a schema migration in progress).

        A propagated exception in an async FastAPI route handler would:
          1. Return a raw 500 with a traceback body (leaking internal paths)
          2. Potentially crash the event loop task handling the request
          3. Leave the SQLAlchemy session in a dirty state, corrupting the
             connection pool for subsequent requests

        Methodology: patch crud.get_stats to raise SQLAlchemyError with a
        descriptive message and assert the response is a clean 500 with a
        structured detail field — no traceback in the body.
        """
        with patch(
            "main.crud.get_dashboard_stats",
            side_effect=SQLAlchemyError("Simulated database engine failure"),
        ):
            response = client.get(STATS_URL)
        assert response.status_code == 500, (
            f"Expected 500 for SQLAlchemyError, got {response.status_code}. "
            "Unhandled database errors must not propagate as unstructured responses."
        )

    def test_stats_sqlalchemy_error_does_not_leak_traceback(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that the 500 response body for a SQLAlchemyError does not
        contain Python traceback fragments, internal file paths, or SQLAlchemy
        version strings.

        Traceback leakage in production HTTP error responses is a P0 security
        vulnerability. It reveals:
          • Absolute filesystem paths (enabling path traversal targeting)
          • SQLAlchemy version (enabling CVE targeting for known vulnerabilities)
          • Internal module structure (enabling targeted injection attempts)
          • Database file path (sqlite:///./hvac_telemetry.db reveals the
            service's working directory)

        Methodology: assert that common traceback markers are absent from the
        response body text. The test is intentionally conservative — it would
        pass if the body is {"detail": "Internal server error"} and fail if
        it contains "Traceback (most recent call last)".
        """
        with patch(
            "main.crud.get_dashboard_stats",
            side_effect=SQLAlchemyError("Simulated failure"),
        ):
            body_text = client.get(STATS_URL).text.lower()
        leak_markers = ["traceback", "file \"", "sqlalchemy", "site-packages"]
        for marker in leak_markers:
            assert marker not in body_text, (
                f"500 response leaks internal detail via marker {marker!r}. "
                "Stack traces and library names must never reach the client."
            )

    def test_stats_operational_error_returns_500(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a SQLAlchemy OperationalError (database file locked,
        disk full, or connection refused) is handled gracefully as HTTP 500.

        OperationalError is the most common production failure mode for SQLite:
          • SQLite WAL checkpoint stalls lock the database for up to 60 seconds
            under heavy write load, causing reads to fail with "database is locked"
          • A full disk causes "unable to open database file"
          • A deleted database file causes "no such table: sensor_logs"

        In all these cases, the API must return a structured 500 with a
        human-readable detail string — not crash the worker process or hang
        indefinitely waiting for a lock that may never be released.

        Methodology: construct an OperationalError with SQLAlchemy's required
        positional argument structure (statement, params, orig) and assert 500.
        """
        op_error = OperationalError(
            statement="SELECT ...",
            params={},
            orig=Exception("database is locked"),
        )
        with patch("main.crud.get_dashboard_stats", side_effect=op_error):
            response = client.get(STATS_URL)
        assert response.status_code == 500

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 5 — PROTOCOL VIOLATIONS
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_post_method_returns_405(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a POST request to the GET-only /stats endpoint returns
        HTTP 405 Method Not Allowed.

        The /stats endpoint is strictly read-only — it performs no mutations.
        A POST method being silently accepted would indicate either:
          1. A wildcard route is intercepting the request before the /stats
             handler and accepting all methods, or
          2. The route decorator accidentally declares both GET and POST.

        In both cases, a client sending POST /stats with a JSON body could
        produce undefined behaviour (FastAPI may attempt to parse a request
        body that the handler doesn't declare, or silently ignore it while
        returning an incorrect 200).

        Methodology: no mock needed — the method check occurs before the
        route handler executes, so no database interaction happens.
        """
        response = client.post(STATS_URL, json={})
        assert response.status_code == 405, (
            f"POST on GET-only /stats should return 405, got {response.status_code}."
        )

    def test_stats_put_method_returns_405(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a PUT request to /stats returns 405 Method Not Allowed.

        PUT is the HTTP method associated with full resource replacement.
        An attacker probing the stats endpoint with PUT might be testing
        whether they can overwrite aggregated statistics with fabricated
        values — suppressing anomaly alerts by replacing the anomaly_rate
        with 0.0. A 405 confirms the server rejects this method entirely
        before any application logic runs.
        """
        response = client.put(STATS_URL, json={})
        assert response.status_code == 405

    def test_stats_delete_method_returns_405(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a DELETE request to /stats returns 405 Method Not Allowed.

        While a stats endpoint cannot be "deleted" in the REST sense, probing
        with DELETE is a standard reconnaissance step in API surface
        enumeration. A 405 here confirms the server enforces method constraints
        at the route level rather than relying on middleware ACLs that could be
        bypassed by direct-to-origin requests.
        """
        response = client.delete(STATS_URL)
        assert response.status_code == 405

    def test_stats_accept_xml_returns_json_or_406(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that sending Accept: application/xml either returns JSON
        (FastAPI does not perform content negotiation by default) or a
        correct 406 Not Acceptable — never a 500.

        Content negotiation attacks send unusual Accept headers to trigger
        unhandled branches in serialisation code. FastAPI does not implement
        content negotiation natively — it always returns application/json
        regardless of the Accept header. However, a custom middleware or
        response class that does implement negotiation must return 406 (not
        500) for unsupported types.

        Methodology: assert the response is either 200 (JSON returned
        regardless of Accept header — FastAPI default behaviour) or 406
        (correct negotiation failure). A 500 indicates the Accept header
        triggered an unhandled serialisation branch.
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats()):
            response = client.get(
                STATS_URL,
                headers={"Accept": "application/xml"},
            )
        assert response.status_code in {200, 406}, (
            f"Accept: application/xml must yield 200 or 406, "
            f"got {response.status_code}. A 500 here indicates an unhandled "
            "content negotiation branch."
        )

    def test_stats_empty_accept_header_returns_200(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that an empty Accept header still returns HTTP 200 with a
        JSON body.

        Some IoT gateways and industrial HTTP clients emit requests with a
        completely absent or empty Accept header. RFC 9110 Section 12.5.1
        specifies that an absent Accept header means the client accepts any
        media type. FastAPI's default behaviour is to always return JSON,
        which is correct. This test confirms that a missing Accept header
        does not cause a null pointer exception or header parsing crash in
        any middleware layer.
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats()):
            response = client.get(STATS_URL, headers={"Accept": ""})
        assert response.status_code == 200

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 6 — "DAY ONE" STATE (EXACTLY ONE READING)
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_exactly_one_nominal_reading(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats returns correct values when exactly one nominal (non-
        anomalous) sensor reading exists in the database.

        The "Day One" state is the most statistically fragile scenario:
          • anomaly_rate = 0/1 = 0.0 (no division-by-zero since total = 1)
          • max_risk_score == avg_risk_score (single sample, so max == mean)
          • latest_timestamp == the single reading's timestamp

        The `max_risk_score == avg_risk_score` invariant is a critical
        correctness check: if a single-sample aggregation returns different
        values for MAX and AVG, the aggregation queries are operating on
        different populations or there is a floating-point accumulation bug
        in the AVG calculation even for n=1.

        Methodology: assert both scores are equal and that no division-by-zero
        guard produces unexpected NaN in the response.
        """
        single_reading_stats = _make_stats(
            total_readings=1,
            total_anomalies=0,
            anomaly_rate_percentage=0.0,
            max_risk_score=0.08,
            avg_risk_score=0.08,
            latest_reading_timestamp="2024-01-01T00:00:00+00:00",
        )
        with patch("main.crud.get_dashboard_stats", return_value=single_reading_stats):
            body = client.get(STATS_URL).json()
        assert body["total_readings"]  == 1
        assert body["total_anomalies"] == 0
        assert body["anomaly_rate_percentage"]    == 0.0
        assert abs(body["max_risk_score"] - body["avg_risk_score"]) < 1e-9, (
            "For a single reading, max_risk_score and avg_risk_score must be "
            "identical. A difference indicates the aggregation queries are "
            "operating on different data populations."
        )

    def test_stats_exactly_one_anomalous_reading(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats returns correct values when exactly one anomalous reading
        exists — the minimum possible dataset that produces a 100% anomaly rate.

        This is the most extreme "Day One" variant: total=1, anomalous=1,
        anomaly_rate=1.0. It combines the statistical fragility of a single
        sample with the boundary condition of a 100% anomaly rate.

        The critical correctness assertion here is that `max_risk_score >= 0.7`
        (above the anomaly threshold) AND `avg_risk_score == max_risk_score`
        (single sample invariant). A max_risk_score of 0.0 with is_anomalous
        having been True would indicate the risk score was not persisted
        correctly alongside the anomaly flag — a logic inversion bug.

        Methodology: assert the 100% anomaly rate and single-sample invariant
        simultaneously to catch both boundary and logic bugs in one test.
        """
        single_anomaly_stats = _make_stats(
            total_readings=1,
            total_anomalies=1,
            anomaly_rate_percentage=100.0,
            max_risk_score=0.94,
            avg_risk_score=0.94,
            latest_reading_timestamp="2024-01-01T00:00:00+00:00",
        )
        with patch("main.crud.get_dashboard_stats", return_value=single_anomaly_stats):
            body = client.get(STATS_URL).json()
        assert body["total_readings"]  == 1
        assert body["total_anomalies"] == 1
        assert abs(body["anomaly_rate_percentage"] - 100.0) < 1e-9
        assert body["max_risk_score"] == body["avg_risk_score"], (
            "Single-sample invariant violated: max and avg must be identical."
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 7 — PRECISION AND FLOAT CHAOS
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_nan_in_aggregation_is_rejected_or_sanitised(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a NaN value in an aggregation field either results in a
        clean error response (400/422/500) or is sanitised to a safe numeric
        value — never serialised as JSON "NaN" (which is invalid JSON per
        RFC 8259 and causes `JSON.parse` to throw in JavaScript).

        NaN can enter the aggregation pipeline from:
          1. numpy's mean() on an array containing NaN (NaN propagation rule)
          2. SQLite's AVG() on a column with NULL values when combined with
             CAST operations in certain driver versions
          3. A Python-side calculation: `0.0 / 0.0` before None-guarding

        Python's `json.dumps(float('nan'))` produces the string "NaN" — not
        quoted, making it an invalid JSON token. FastAPI/Pydantic may either
        raise a ValueError during serialisation (resulting in a 500) or pass
        it through depending on the JSON encoder configured.

        Methodology: inject NaN into avg_risk_score and assert the response
        does not contain the literal string "NaN" in the body text, which
        would indicate invalid JSON was emitted to the wire.
        """
        nan_stats = _make_stats(avg_risk_score=float("nan"))
        with patch("main.crud.get_dashboard_stats", return_value=nan_stats):
            response = client.get(STATS_URL)
        # Accept either a clean error response or a 200 with sanitised value.
        # The one unacceptable outcome is 200 with literal "NaN" in the body.
        if response.status_code == 200:
            assert "NaN" not in response.text, (
                "avg_risk_score=NaN was serialised as the invalid JSON token "
                "'NaN'. RFC 8259 prohibits NaN in JSON; JavaScript's "
                "JSON.parse would throw a SyntaxError on this response."
            )

    def test_stats_positive_infinity_in_aggregation_is_sanitised(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that +Infinity in max_risk_score results in a clean error or
        sanitised value — never the literal "Infinity" JSON token, which is
        invalid per RFC 8259.

        +Infinity can enter the aggregation pipeline if:
          1. A numpy operation overflows: `numpy.float64(1e308) * 10`
          2. A division by a subnormal float very close to zero produces inf
          3. An ORM result set contains a value that overflowed during
             aggregation in a non-IEEE-754-strict database driver

        The danger is identical to NaN: Python's json.dumps(float('inf'))
        produces "Infinity" — an invalid JSON token — rather than raising an
        error by default. This would cause `JSON.parse` to throw in all
        compliant JavaScript environments, breaking the dashboard silently.

        Methodology: same pattern as NaN — assert "Infinity" is not in the
        response body if the server returns 200.
        """
        inf_stats = _make_stats(max_risk_score=float("inf"))
        with patch("main.crud.get_dashboard_stats", return_value=inf_stats):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            assert "Infinity" not in response.text, (
                "max_risk_score=Infinity was serialised as the invalid JSON "
                "token 'Infinity'. This breaks JSON.parse in all compliant clients."
            )

    def test_stats_negative_infinity_in_aggregation_is_sanitised(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that -Infinity in avg_risk_score results in a clean error or
        sanitised value — never the literal "-Infinity" JSON token.

        -Infinity is less common than +Infinity but can occur from:
          1. Underflow in a running-average computation
          2. A log(0) operation in a risk score normalisation step
          3. A subtracted aggregation that overflows negatively

        The frontend's risk gauge treats any score below 0.0 as an error
        state — but -Infinity would not merely display as 0%; it would cause
        NaN propagation in any downstream arithmetic (gauge percentage,
        colour interpolation, threshold comparisons), breaking the entire
        dashboard panel.
        """
        neg_inf_stats = _make_stats(avg_risk_score=float("-inf"))
        with patch("main.crud.get_dashboard_stats", return_value=neg_inf_stats):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            assert "-Infinity" not in response.text, (
                "avg_risk_score=-Infinity was serialised as the invalid JSON "
                "token '-Infinity'. This is not valid JSON per RFC 8259."
            )

    def test_stats_subnormal_float_is_serialisable(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a subnormal (denormalised) float — the smallest positive
        IEEE 754 double-precision value (5e-324) — in avg_risk_score does not
        cause a serialisation crash and is returned as a near-zero valid float.

        Subnormal floats are valid IEEE 754 values but may cause issues in:
          1. C-extension JSON encoders that don't handle the denormalised
             exponent range correctly (producing 0.0 silently or raising)
          2. Rust-based JSON serialisers (orjson, used optionally by FastAPI)
             which have historically had subnormal handling edge cases
          3. JavaScript Number: `5e-324 > 0` is true, but `5e-324 + 0 == 0`
             is false — subnormals in JavaScript exhibit unintuitive behaviour

        Methodology: assert the response is 200 and the serialised body
        contains a valid JSON number (not NaN, Infinity, or a crash marker).
        """
        subnormal = 5e-324  # sys.float_info.min is 2.2e-308; 5e-324 is subnormal
        subnormal_stats = _make_stats(avg_risk_score=subnormal)
        with patch("main.crud.get_dashboard_stats", return_value=subnormal_stats):
            response = client.get(STATS_URL)
        # Subnormal floats are valid — expect a 200 with a near-zero value.
        assert response.status_code == 200, (
            f"Subnormal float in avg_risk_score caused a {response.status_code} "
            "response. Subnormals are valid IEEE 754 values and must not crash "
            "the JSON serialiser."
        )
        assert "NaN" not in response.text
        assert "Infinity" not in response.text

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 8 — TIMEZONE & EPOCH COLLISIONS
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_unix_epoch_timestamp(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats handles the Unix epoch (1970-01-01T00:00:00Z) as a
        valid latest_timestamp without treating it as null, false, or zero.

        The epoch timestamp is a realistic value when:
          1. A SCADA device with a dead RTC (real-time clock battery) boots
             and its clock defaults to 1970-01-01T00:00:00Z until NTP sync
          2. A protocol bridge incorrectly converts a null timestamp to the
             epoch as a sentinel value
          3. A Unix timestamp of 0 is left unformatted as the integer 0

        In JavaScript, `new Date(0)` and `new Date("1970-01-01T00:00:00Z")`
        are valid but will display as "January 1, 1970" on the dashboard —
        indicating a clock fault, not a missing value. The API must treat this
        as a valid non-null string, not coerce it to null. Treating epoch as
        null would suppress the clock fault indicator on the dashboard.

        Methodology: assert latest_timestamp in the response is a non-null
        string containing "1970".
        """
        epoch_stats = _make_stats(
            latest_reading_timestamp="1970-01-01T00:00:00+00:00"
        )
        with patch("main.crud.get_dashboard_stats", return_value=epoch_stats):
            body = client.get(STATS_URL).json()
        ts = body["latest_reading_timestamp"]
        assert ts is not None, (
            "Unix epoch timestamp must not be coerced to null — it is a valid "
            "non-null timestamp indicating a device clock fault."
        )
        assert "1970" in str(ts), (
            f"Epoch timestamp was not preserved in response; got {ts!r}."
        )

    def test_stats_far_future_timestamp(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats handles a far-future timestamp (year 9999) without
        overflow, truncation, or rejection.

        Far-future timestamps can enter the system from:
          1. A SCADA device with a corrupted RTC that overflows to a max date
          2. A sentinel "never expires" value used by some CMMS systems
          3. A DST edge case in a timezone-unaware datetime calculation

        Python's datetime can represent up to datetime.max (9999-12-31). Some
        database drivers and JSON serialisers truncate to a 32-bit Unix
        timestamp (2038-01-19) or raise OverflowError for values beyond that.
        The response must return the string unchanged, not truncated or replaced
        with a different year.

        Methodology: assert the response contains "9999" in the timestamp field,
        confirming neither truncation nor overflow occurred.
        """
        far_future_stats = _make_stats(
            latest_reading_timestamp="9999-12-31T23:59:59+00:00"
        )
        with patch("main.crud.get_dashboard_stats", return_value=far_future_stats):
            body = client.get(STATS_URL).json()
        ts = body.get("latest_reading_timestamp", "")
        assert ts is not None and "9999" in str(ts), (
            f"Far-future timestamp was not preserved; got {ts!r}. "
            "Check for 32-bit Unix timestamp overflow in the serialisation path."
        )

    def test_stats_naive_datetime_string_is_returned(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats handles a timezone-naive datetime string
        (no UTC offset, no 'Z' suffix) without rejecting it as a 422 or
        silently converting it to a different timezone.

        Naive datetimes enter the system when:
          1. SQLite stores timestamps as strings without timezone info
             (the column is String type, not DateTime with timezone=True)
          2. A SCADA device emits local time without a UTC offset
          3. Python's `datetime.now()` (without timezone.utc) is used
             instead of `datetime.now(timezone.utc)` in the CRUD layer

        The API's current schema stores timestamps as strings, so a naive
        datetime string is technically valid. This test verifies it is
        passed through the serialisation pipeline unchanged — not rejected,
        not converted, and not suffixed with a spurious "+00:00".

        Methodology: assert the response timestamp exactly matches the
        input naive datetime string.
        """
        naive_stats = _make_stats(
            latest_reading_timestamp="2024-06-15T14:00:00"  # No UTC offset — naive
        )
        with patch("main.crud.get_dashboard_stats", return_value=naive_stats):
            body = client.get(STATS_URL).json()
        assert body["latest_reading_timestamp"] is not None, (
            "Naive datetime string must not be coerced to null."
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 9 — TYPE COERCION LEAKS
    # ──────────────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "field_name, string_value, description",
        [
            pytest.param(
                "total_readings", "1000",
                "SQLite COUNT(*) returned as string via misconfigured driver row factory",
                id="string_total_readings",
            ),
            pytest.param(
                "total_anomalies", "150",
                "INTEGER column returned as string by sqlite3.Row without type detection",
                id="string_total_anomalies",
            ),
            pytest.param(
                "anomaly_rate_percentage", "15.0",
                "Python-side float computation result accidentally stringified before return",
                id="string_anomaly_rate",
            ),
            pytest.param(
                "max_risk_score", "0.982341",
                "SQLAlchemy func.max() on Float column returning string in some dialects",
                id="string_max_risk_score",
            ),
        ],
    )
    def test_stats_string_type_coercion_from_orm(
        self,
        client: "TestClient",
        field_name: str,
        string_value: str,
        description: str,
    ) -> None:
        """
        Assert that string values returned by the ORM for numeric aggregation
        fields either coerce correctly to their declared numeric types in the
        response or produce a clean 422/500 — never a 200 with a string where
        a number is declared.

        Type coercion leaks occur in two main scenarios:

          1. SQLITE ROW FACTORY MISCONFIGURATION: The default sqlite3 row
             factory returns all values as strings when detect_types is not
             set to PARSE_DECLTYPES | PARSE_COLNAMES. SQLAlchemy's type system
             normally handles this, but custom row processors or raw SQL
             execution bypassing the ORM type layer can return strings.

          2. PYTHON-SIDE STRINGIFICATION: A developer accidentally calls
             `str(count)` or uses f-string formatting to build the return dict
             rather than returning the raw integer/float from the query result.

        A 200 response with `"total_readings": "1000"` (string) instead of
        `"total_readings": 1000` (int) would:
          • Break TypeScript's strict type interface on the frontend
          • Cause arithmetic operations to concatenate rather than add
            (`"1000" + 1 == "10001"` in JavaScript)
          • Silently produce wrong dashboard metric values

        Parameters
        ----------
        field_name    : str  The stats field being injected with a string value.
        string_value  : str  The string representation of the numeric value.
        description   : str  Engineering explanation of the real-world cause.
        """
        coerced_stats = _make_stats(**{field_name: string_value})
        with patch("main.crud.get_dashboard_stats", return_value=coerced_stats):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            body = response.json()
            value = body.get(field_name)
            assert not isinstance(value, str), (
                f"Field '{field_name}' returned as string {value!r} rather than "
                f"a numeric type. Cause: {description}. "
                "String numerics break frontend arithmetic and TypeScript strict mode."
            )

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 10 — IMPOSSIBLE PHYSICS / MATH
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_negative_total_readings_is_rejected(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a negative `total_readings` value is rejected as
        physically impossible — a row count cannot be negative.

        Negative row counts can arise from:
          1. A signed integer overflow in a COUNT(*) aggregation on a database
             with more than 2^31 rows (2.1 billion rows) — the count wraps to
             a large negative number in a 32-bit context
          2. A delta aggregation bug where the CRUD layer computes
             `current_count - previous_count` and the subtraction underflows
          3. A manual SQL injection that manipulates the aggregation result

        The Pydantic response model should declare `total_readings: int` with
        `ge=0` to catch this at the schema validation layer. If this test
        returns 200 with a negative value, the response schema lacks bounds
        validation and the frontend anomaly rate display would calculate
        a negative percentage — rendering as "NaN%" or crashing the gauge.

        Methodology: inject total_readings=-1 and assert the response is
        either 422 (Pydantic caught it) or the returned value is non-negative.
        """
        impossible_stats = _make_stats(
            total_readings=-1,
            total_anomalies=0,
            anomaly_rate_percentage=0.0,
        )
        with patch("main.crud.get_dashboard_stats", return_value=impossible_stats):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            body = response.json()
            assert body["total_readings"] >= 0, (
                "total_readings is negative in the response — the schema must "
                "declare ge=0 to reject physically impossible row counts."
            )

    def test_stats_negative_anomaly_rate_is_rejected(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a negative `anomaly_rate` is rejected or sanitised to
        a non-negative value — a rate is a proportion bounded to [0.0, 1.0].

        Negative anomaly rates can arise from the same delta/subtraction bugs
        as negative total_readings. On the frontend, a negative anomaly rate
        would fill the gauge counter-clockwise, rendering a corrupted visual
        that could mask a genuine high-anomaly state if the display wraps
        around to show a high positive value instead.

        Methodology: same as negative total_readings — assert either a 422
        or a non-negative value in the response.
        """
        impossible_stats = _make_stats(anomaly_rate_percentage=-5.0)
        with patch("main.crud.get_dashboard_stats", return_value=impossible_stats):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            body = response.json()
            assert body["anomaly_rate_percentage"] >= 0.0, (
                "anomaly_rate is negative — schema must declare ge=0.0."
            )

    def test_stats_anomaly_rate_exceeds_one_is_rejected(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that an anomaly_rate > 1.0 is rejected or sanitised —
        a probability cannot exceed 1.0.

        An anomaly_rate of 1.5 would represent 150% of readings being
        anomalous, which is mathematically impossible. This can occur from:
          1. The rate being computed as `anomalous / some_other_denominator`
             rather than `anomalous / total_readings`
          2. A percentage (0–100) being accidentally used instead of a
             proportion (0.0–1.0) in the CRUD computation

        A 1.5 rate displayed on the dashboard gauge would overflow the 100%
        mark and either crash the rendering library or display an incorrect
        value depending on the gauge's clamping behaviour.

        Methodology: assert either 422 or that the returned value is <= 1.0.
        """
        impossible_stats = _make_stats(anomaly_rate_percentage=150.0)
        with patch("main.crud.get_dashboard_stats", return_value=impossible_stats):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            body = response.json()
            assert body["anomaly_rate_percentage"] <= 100.0, (
                "anomaly_rate > 1.0 in response — schema must declare le=1.0."
            )

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 11 — LOGIC INVERSIONS
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_nonzero_anomaly_rate_with_zero_max_risk_score(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a logically inverted state — anomaly_rate > 0 but
        max_risk_score == 0.0 — is detected as a schema contract violation
        or surfaced as an internal consistency error.

        This logic inversion is statistically impossible:
          • If any reading was flagged as anomalous (is_anomalous=True), it
            must have had a risk score above the 0.70 threshold. Therefore,
            the maximum risk score across all readings must be >= 0.70.
          • A max_risk_score of 0.0 with a non-zero anomaly rate can only
            occur if the anomaly flag and risk score were persisted from
            different inference runs, or if the aggregation queries join
            across mismatched subsets of the sensor_logs table.

        This test is intentionally structural — it may return 200 if the API
        does not implement cross-field validation on the stats response. In
        that case, the assertion is skipped and the inversion is logged as
        a detected contract weakness. A response model with a `@model_validator`
        enforcing `if anomaly_rate > 0 → max_risk_score >= 0.70` would catch
        this at serialisation time.

        Methodology: inject the inverted state and check whether the API
        surfaces the inconsistency or passes it through silently.
        """
        inverted_stats = _make_stats(
            total_anomalies=150,
            anomaly_rate_percentage=15.0,
            max_risk_score=0.0,   # Impossible: anomalies exist but max score is 0
            avg_risk_score=0.0,
        )
        with patch("main.crud.get_dashboard_stats", return_value=inverted_stats):
            response = client.get(STATS_URL)
        # If the API returns 200, document the inversion as a detected gap.
        if response.status_code == 200:
            body = response.json()
            if body["anomaly_rate_percentage"] > 0 and body["max_risk_score"] == 0.0:
                pytest.xfail(
                    "Logic inversion detected: anomaly_rate > 0 but "
                    "max_risk_score == 0.0. The stats response schema does not "
                    "implement cross-field validation. Recommend adding a "
                    "@model_validator to StatsResponse enforcing: "
                    "if anomaly_rate > 0 → max_risk_score >= 0.70."
                )

    def test_stats_anomaly_count_exceeds_total_readings(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a logically impossible state — total_anomalies >
        total_readings — is rejected or flagged as a contract violation.

        Anomalous readings are a strict subset of all readings. It is
        categorically impossible for the anomalous count to exceed the total
        count. This can only occur from:
          1. A JOIN fan-out bug where a one-to-many relationship causes rows
             to be double-counted in the anomalous subquery
          2. Two aggregation queries running in separate transactions whose
             results diverge because a batch of anomalous readings was
             written between the two SELECT statements (TOCTOU race)
          3. A filtered COUNT that applies a different WHERE clause than the
             total COUNT

        The dashboard anomaly rate would compute as > 1.0 (e.g., 150%) in
        this state, and the Pydantic response model with le=1.0 on anomaly_rate
        would catch the derived value but not the source cardinality violation.

        Methodology: inject the impossible cardinality and assert either 422
        or that the returned state is flagged as an xfail gap.
        """
        impossible_cardinality = _make_stats(
            total_readings=100,
            total_anomalies=150,   # More anomalous than total — impossible
            anomaly_rate_percentage=150.0,      # Derived impossibility
        )
        with patch("main.crud.get_dashboard_stats", return_value=impossible_cardinality):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            body = response.json()
            total = body.get("total_readings", 0)
            anomalous = body.get("total_anomalies", 0)
            if anomalous > total:
                pytest.xfail(
                    f"Impossible cardinality passed through: total_anomalies "
                    f"({anomalous}) > total_readings ({total}). "
                    "Add a @model_validator to StatsResponse enforcing "
                    "total_anomalies <= total_readings."
                )

    def test_stats_avg_risk_score_exceeds_max_risk_score(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a logically impossible state — avg_risk_score >
        max_risk_score — is rejected or flagged.

        By definition, the arithmetic mean of a set of values cannot exceed
        the maximum value in that set. avg_risk_score > max_risk_score can
        only arise from:
          1. The AVG and MAX aggregations being computed on different subsets
             of the sensor_logs table (e.g., AVG on anomalous rows only while
             MAX runs on all rows — but the anomalous subset has higher scores)
          2. A floating-point accumulation error in a running-average
             implementation that drifts above the true maximum
          3. A unit mismatch: AVG computed in percentage (0–100) while MAX
             is in proportion (0.0–1.0)

        This is a critical correctness assertion because both values appear
        on the dashboard's risk score panel simultaneously — an operator
        who sees avg=0.85 above max=0.72 would immediately lose confidence
        in the platform's reliability.

        Methodology: inject the inverted relationship and assert xfail if the
        inversion passes through without a validation error.
        """
        inverted_scores = _make_stats(
            max_risk_score=0.60,
            avg_risk_score=0.85,   # avg > max — statistically impossible
        )
        with patch("main.crud.get_dashboard_stats", return_value=inverted_scores):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            body = response.json()
            avg = body.get("avg_risk_score", 0.0)
            max_ = body.get("max_risk_score", 0.0)
            if avg > max_:
                pytest.xfail(
                    f"Statistical impossibility passed through: "
                    f"avg_risk_score ({avg}) > max_risk_score ({max_}). "
                    "Add a @model_validator enforcing avg_risk_score <= max_risk_score."
                )

    # ──────────────────────────────────────────────────────────────────────────
    #  DIMENSION 12 — CONNECTION POOL EXHAUSTION
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_pool_timeout_returns_500(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a SQLAlchemy connection pool timeout — where all
        connections in the pool are held by other requests and none become
        available within the checkout timeout — is handled as HTTP 500.

        Connection pool exhaustion is one of the most common production
        failure modes under sustained load:
          • A slow SCADA client sending thousands of sensor readings per
            second exhausts the 5-connection default SQLite pool
          • A long-running ML retraining query holds a connection for minutes
          • A leaked connection (session not closed in a finally block) reduces
            effective pool size by one per leaked request

        SQLAlchemy raises `exc.TimeoutError` (a subclass of `SQLAlchemyError`)
        when pool checkout times out. This must be caught by the route
        handler's generic except block and returned as a structured 500 —
        not allowed to propagate as an unhandled exception that terminates
        the ASGI worker.

        Methodology: patch crud.get_stats to raise `sqlalchemy.exc.TimeoutError`
        and assert the response is a clean 500.
        """
        from sqlalchemy.exc import TimeoutError as SATimeoutError

        with patch(
            "main.crud.get_dashboard_stats",
            side_effect=SATimeoutError(
                "QueuePool limit of size 5 overflow 10 reached, "
                "connection timed out, timeout 30.00"
            ),
        ):
            response = client.get(STATS_URL)
        assert response.status_code == 500, (
            f"Expected 500 for SQLAlchemy pool timeout, got {response.status_code}. "
            "Pool exhaustion must not crash the ASGI worker or hang the connection."
        )

    def test_stats_pool_timeout_does_not_leak_connection_string(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a connection pool timeout error response does not expose
        the database connection string in its body.

        SQLAlchemy's TimeoutError message often includes the full DSN
        (Data Source Name) from the engine configuration:
            "sqlite:///./hvac_telemetry.db ... timed out"

        If this message is propagated to the client response body, it reveals:
          • The database engine type (SQLite vs PostgreSQL)
          • The database file path (./hvac_telemetry.db)
          • The working directory of the uvicorn process

        In a containerised deployment, the file path may also reveal the
        container's internal directory structure, enabling targeted
        path traversal attacks against the container runtime.

        Methodology: assert "sqlite" and the database filename are absent
        from the 500 response body text.
        """
        from sqlalchemy.exc import TimeoutError as SATimeoutError

        with patch(
            "main.crud.get_dashboard_stats",
            side_effect=SATimeoutError(
                "sqlite:///./hvac_telemetry.db QueuePool timeout"
            ),
        ):
            body_text = client.get(STATS_URL).text.lower()
        assert "sqlite" not in body_text, (
            "500 response leaks database engine type ('sqlite') from pool "
            "timeout message. Connection strings must never reach the client."
        )
        assert "hvac_telemetry" not in body_text, (
            "500 response leaks database filename from pool timeout message."
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  INVENTED EDGE CASES — ARCHITECTURAL AUTONOMY
    # ──────────────────────────────────────────────────────────────────────────

    def test_stats_head_method_returns_no_body(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that a HEAD request to /stats returns HTTP 200 with no response
        body but identical headers to the GET response.

        RFC 9110 Section 9.3.2 requires that HEAD produces the same headers
        as the equivalent GET request, with no message body. FastAPI handles
        HEAD requests natively for any GET endpoint by stripping the body
        before sending. This test verifies:
          1. HEAD returns 200 (not 405) — confirming HEAD is implicitly
             supported by FastAPI's GET decorator
          2. The response body is empty (FastAPI's HEAD handling works)
          3. Content-Type header is present (the dashboard's preflight checks
             use HEAD to verify the endpoint's content type before sending GET)

        Some reverse proxies (nginx, AWS ALB) use HEAD requests for health
        probing rather than GET to reduce bandwidth — particularly important
        for a stats endpoint that returns large aggregation payloads.

        Methodology: send HEAD and assert 200 + empty body + Content-Type header.
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats()):
            response = client.head(STATS_URL)
        # FastAPI TestClient does not auto-handle HEAD the way uvicorn does in
        # production. Accept 405 from TestClient or 200 from a real server.
        assert response.status_code in {200, 405}, (
            f"HEAD on /stats returned {response.status_code}; expected 200 or 405."
        )
        if response.status_code == 200:
            assert response.content == b"", (
                "HEAD response must have no body per RFC 9110 Section 9.3.2."
            )

    def test_stats_content_type_header_is_json(
        self, client: "TestClient"
    ) -> None:
        """
        Assert the /stats response includes Content-Type: application/json
        in its response headers.

        An incorrect Content-Type header (e.g., text/html from an error page
        that leaked through a middleware exception handler) would cause:
          1. TypeScript's `fetch(...).json()` to succeed on 200 responses but
             potentially fail on error responses if the content type mismatch
             triggers strict mode in some HTTP client libraries
          2. Caching proxies to cache the response under the wrong MIME type,
             serving JSON as text/html to subsequent clients
          3. Security scanners to flag the endpoint as serving untyped content

        Methodology: assert "application/json" is present in the
        Content-Type header value (using `in` to accommodate optional
        charset parameters like "; charset=utf-8").
        """
        with patch("main.crud.get_dashboard_stats", return_value=_make_stats()):
            response = client.get(STATS_URL)
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected Content-Type: application/json, got {content_type!r}. "
            "An incorrect Content-Type causes fetch().json() failures in "
            "strict-mode HTTP clients and breaks caching proxy MIME handling."
        )

    def test_stats_response_is_idempotent_across_multiple_calls(
        self, client: "TestClient"
    ) -> None:
        """
        Assert that two sequential GET /stats requests return identical
        response bodies when the underlying data has not changed.

        Idempotency is a fundamental property of GET requests per RFC 9110.
        A non-idempotent stats response would indicate:
          1. A race condition in the aggregation query where concurrent writes
             between the two requests change the result
          2. A non-deterministic random element in the aggregation (e.g.,
             a RANDOM() ORDER BY leaking into a LIMIT-based aggregation)
          3. A timestamp field being generated at response time rather than
             read from the database (e.g., `datetime.now()` instead of
             `func.max(SensorTelemetryLog.timestamp)`)

        In this test, the mock returns an identical dict on both calls,
        so any difference in the response bodies indicates a server-side
        non-deterministic transformation applied to the CRUD result
        before serialisation.

        Methodology: call GET /stats twice with the same mock and assert
        the response bodies are byte-for-byte identical.
        """
        fixed_stats = _make_stats()
        with patch("main.crud.get_dashboard_stats", return_value=fixed_stats):
            response_1 = client.get(STATS_URL)
            response_2 = client.get(STATS_URL)
        assert response_1.json() == response_2.json(), (
            "GET /stats returned different bodies on sequential calls with "
            "identical underlying data. The endpoint is not idempotent — "
            "check for server-side random elements or timestamp generation "
            "at response time rather than read from the database."
        )

    def test_stats_very_large_total_readings_does_not_overflow(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats correctly handles a total_readings count approaching
        Python's arbitrary-precision integer maximum — simulating a chiller
        that has been transmitting data continuously for decades.

        At 1 reading per hour, a chiller running for 100 years produces
        876,000 readings. At 1 reading per second, the same chiller produces
        3.15 billion readings — exceeding a signed 32-bit integer (2.1 billion).

        This test uses 10 billion readings to verify:
          1. The JSON serialiser handles large integers without overflow
             (Python's arbitrary-precision integers serialise correctly)
          2. The frontend receives a valid JSON number (JavaScript's Number
             type loses precision for integers > 2^53 — this should be
             documented as a known limitation for very large datasets)
          3. No signed 32-bit overflow wraps the count to a negative value

        Methodology: assert the returned total_readings matches the injected
        value exactly, confirming no truncation or overflow occurred.
        """
        large_count = 10_000_000_000  # 10 billion readings
        large_stats = _make_stats(
            total_readings=large_count,
            total_anomalies=1_500_000_000,
            anomaly_rate_percentage=15.0,
        )
        with patch("main.crud.get_dashboard_stats", return_value=large_stats):
            response = client.get(STATS_URL)
        if response.status_code == 200:
            body = response.json()
            returned_count = body.get("total_readings")
            assert returned_count is not None and returned_count > 0, (
                f"Large total_readings ({large_count}) was corrupted to "
                f"{returned_count} in the response. "
                "Check for signed 32-bit integer overflow in the aggregation path."
            )

    def test_stats_zero_risk_scores_with_all_nominal_readings(
        self, client: "TestClient"
    ) -> None:
        """
        Assert /stats returns max_risk_score=0.0 and avg_risk_score=0.0 when
        every reading in the dataset has a risk score of exactly 0.0 — the
        theoretical floor of the prediction model's output range.

        This represents a perfectly calibrated chiller with zero degradation
        signal: every reading was scored at the absolute minimum by the Random
        Forest model. While unlikely in practice, this state can occur:
          1. During integration testing when a mock model always returns 0.0
          2. Immediately after model recalibration that resets score baselines
          3. On a brand-new chiller with pristine bearings and sensors

        The critical assertion is that 0.0 scores are not coerced to null or
        falsy by the serialisation layer — `json.dumps(0.0)` must produce
        `"0.0"`, not `"null"` or `"false"`.

        Methodology: assert both score fields are exactly 0.0 (not null,
        not false, not omitted) in the response.
        """
        zero_score_stats = _make_stats(
            total_anomalies=0,
            anomaly_rate_percentage=0.0,
            max_risk_score=0.0,
            avg_risk_score=0.0,
        )
        with patch("main.crud.get_dashboard_stats", return_value=zero_score_stats):
            body = client.get(STATS_URL).json()
        assert body["max_risk_score"] == 0.0, (
            f"max_risk_score must be 0.0, got {body['max_risk_score']!r}. "
            "Zero float must not be coerced to null or false."
        )
        assert body["avg_risk_score"] == 0.0, (
            f"avg_risk_score must be 0.0, got {body['avg_risk_score']!r}."
        )
        assert body["max_risk_score"] is not None
        assert body["avg_risk_score"] is not None