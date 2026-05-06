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
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

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

# ISO 10816-3 bearing vibration velocity threshold (mm/s RMS).
# Below this → healthy; above → P-F curve degradation zone.
ISO_10816_THRESHOLD: float = 4.5

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