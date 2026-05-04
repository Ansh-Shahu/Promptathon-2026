"""
client_simulator.py
─────────────────────────────────────────────────────────────────────────────
Simulates a live IoT SCADA edge device streaming HVAC chiller sensor
telemetry from `hvac_sensor_data.csv` to the FastAPI prediction endpoint.

Features
────────
  • Flicker-free, in-place Rich terminal dashboard (no scrolling spam)
  • Exponential backoff retry loop — survives server restarts gracefully
  • Seamless infinite loop across CSV rows to simulate 24/7 operation
  • Explicit NumPy → Python type coercion before JSON serialisation
  • Graceful handling of HTTP 422 (schema rejection) per row

Usage
─────
  # Default: infinite loop, 1-second delay
  python client_simulator.py

  # Custom: single pass, 0.5s delay, different endpoint
  python client_simulator.py --url http://10.0.0.5:8000/api/v1/predict \\
                              --delay 0.5 \\
                              --no-loop

Dependencies
────────────
  pip install pandas requests rich
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from itertools import cycle
from typing import Optional

import pandas as pd
import requests
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout as ReqTimeout
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_API_URL: str = "http://127.0.0.1:8000/api/v1/predict"
DEFAULT_DELAY_SECONDS: float = 1.0
DEFAULT_INFINITE_LOOP: bool = True

# ISO 10816-3 vibration threshold — mirrors the value used in the API mock
ISO_10816_THRESHOLD_MMS: float = 4.5

# Exponential backoff config for server-down retries
BACKOFF_BASE_SECONDS: float = 1.0
BACKOFF_MAX_SECONDS: float = 30.0
BACKOFF_MULTIPLIER: float = 2.0

# How many response rows to keep in the scrolling history table
MAX_HISTORY_ROWS: int = 20

# CSV source
CSV_FILE: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "ml_pipeline",
    "hvac_sensor_data.csv"
)

# Request timeout (connect_timeout, read_timeout)
REQUEST_TIMEOUT: tuple[float, float] = (5.0, 10.0)


# ══════════════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SessionStats:
    """Accumulates running totals displayed in the stats panel."""
    total_sent: int = 0
    total_anomalous: int = 0
    total_nominal: int = 0
    total_errors: int = 0
    total_skipped: int = 0
    loop_count: int = 1
    session_start: datetime = field(default_factory=datetime.now)

    @property
    def uptime(self) -> str:
        delta = datetime.now() - self.session_start
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def anomaly_rate(self) -> str:
        if self.total_sent == 0:
            return "0.0%"
        return f"{(self.total_anomalous / self.total_sent) * 100:.1f}%"


@dataclass
class HistoryRow:
    """One entry in the scrolling response history table."""
    timestamp: str
    vibration_rms: float
    discharge_temp: float
    risk_score: float
    is_anomalous: bool
    alert_snippet: str
    row_index: int


# ══════════════════════════════════════════════════════════════════════════════
#  ARGUMENT PARSING
# ══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HVAC Chiller IoT SCADA Simulator — streams CSV rows to FastAPI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_API_URL,
        dest="api_url",
        help="FastAPI prediction endpoint URL.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        dest="delay_seconds",
        help="Seconds to wait between each sensor reading POST.",
    )
    parser.add_argument(
        "--no-loop",
        action="store_false",
        dest="infinite_loop",
        default=DEFAULT_INFINITE_LOOP,
        help="Exit after one pass through the CSV instead of looping infinitely.",
    )
    return parser.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
#  PAYLOAD BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_payload(row: pd.Series) -> dict:
    """
    Map a Pandas DataFrame row to a JSON-serialisable dict matching
    the SensorPayload schema.

    All NumPy scalar types (np.int64, np.float32, etc.) are explicitly
    cast to native Python int / float. Without this, `requests` will
    raise a `TypeError: Object of type int64 is not JSON serializable`.

    Parameters
    ----------
    row : pd.Series
        A single row from the hvac_sensor_data.csv DataFrame.

    Returns
    -------
    dict
        Clean Python-native dict ready for `requests.post(json=...)`.
    """
    return {
        "timestamp":       str(row["timestamp"]),
        "suction_temp":    float(row["suction_temp"]),
        "discharge_temp":  float(row["discharge_temp"]),
        "suction_press":   float(row["suction_press"]),
        "discharge_press": float(row["discharge_press"]),
        "vibration_rms":   float(row["vibration_rms"]),
        "power_draw":      float(row["power_draw"]),
        "oil_pressure":    float(row["oil_pressure"]),
        "runtime_hours":   int(row["runtime_hours"]),
        "ambient_temp":    float(row["ambient_temp"]),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NETWORK LAYER — POST WITH EXPONENTIAL BACKOFF
# ══════════════════════════════════════════════════════════════════════════════

def post_with_retry(
    api_url: str,
    payload: dict,
    stats: SessionStats,
    live: Live,
    layout: Layout,
    history: list[HistoryRow],
) -> Optional[dict]:
    """
    POST a sensor payload to the API with exponential backoff retry logic.

    Exception Tiers
    ───────────────
    Tier 1 — ConnectionError / Timeout:
        Server is unreachable. Enter exponential backoff loop.
        The dashboard updates in place while waiting — no line spam.
        Never propagates; retries until the server comes back.

    Tier 2 — HTTP 422 Unprocessable Entity:
        Schema validation rejected this specific row.
        Log the error detail, increment skip counter, return None.
        The main loop moves to the next row immediately.

    Tier 3 — Any other HTTP error (500, 503, etc.):
        Server-side fault unrelated to our payload.
        Log it, increment error counter, return None.

    Parameters
    ----------
    api_url  : str
    payload  : dict             Clean JSON-serialisable sensor payload.
    stats    : SessionStats     Mutable session counters (updated in place).
    live     : Live             Rich Live context (used to refresh during backoff).
    layout   : Layout           Rich Layout (updated with waiting status).
    history  : list[HistoryRow] Scrolling history (not modified here).

    Returns
    -------
    dict | None
        Parsed JSON response body, or None if the row should be skipped.
    """
    attempt: int = 0

    while True:
        try:
            response = requests.post(
                api_url,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

        except (ReqConnectionError, ReqTimeout):
            # ── Tier 1: Server unreachable — backoff and retry ────────────────
            wait: float = min(
                BACKOFF_BASE_SECONDS * (BACKOFF_MULTIPLIER ** attempt),
                BACKOFF_MAX_SECONDS,
            )
            attempt += 1
            stats.total_errors += 1

            # Update dashboard in place with waiting status
            waiting_msg = (
                f"[bold yellow]⚡ Server unreachable — retrying in "
                f"{wait:.0f}s (attempt #{attempt})...[/bold yellow]"
            )
            layout["footer"].update(Panel(waiting_msg, style="yellow"))
            live.refresh()
            time.sleep(wait)
            # Reset attempt counter so backoff doesn't grow forever across
            # multiple disconnects in the same session
            if attempt > 5:
                attempt = 5

        except requests.exceptions.HTTPError as exc:
            status_code: int = exc.response.status_code

            if status_code == 422:
                # ── Tier 2: Schema rejection — skip this row ─────────────────
                stats.total_skipped += 1
                try:
                    detail = exc.response.json().get("detail", "No detail provided.")
                except Exception:
                    detail = str(exc)
                layout["footer"].update(Panel(
                    f"[bold orange1]⚠ Row skipped (HTTP 422) — "
                    f"Validation error: {str(detail)[:120]}[/bold orange1]",
                    style="orange1",
                ))
                live.refresh()
                return None

            else:
                # ── Tier 3: Other server error — skip this row ────────────────
                stats.total_errors += 1
                layout["footer"].update(Panel(
                    f"[bold red]✗ HTTP {status_code} error — "
                    f"{exc.response.text[:120]}[/bold red]",
                    style="red",
                ))
                live.refresh()
                return None


# ══════════════════════════════════════════════════════════════════════════════
#  RICH UI BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def build_history_table(history: list[HistoryRow]) -> Table:
    """
    Construct a new Rich Table from the current history list.

    A brand-new Table is built on every render cycle. Rich diffs renderables
    and redraws only what has changed, so this pattern produces smooth,
    flicker-free updates without any manual cursor management.
    """
    table = Table(
        title="📡  Live Sensor Stream  ─  HVAC Chiller P-F Curve Monitor",
        title_style="bold white on dark_blue",
        border_style="bright_blue",
        header_style="bold cyan",
        show_lines=True,
        expand=True,
    )

    table.add_column("#",              style="dim",          width=6,  justify="right")
    table.add_column("Timestamp",      style="white",        width=22)
    table.add_column("Vibration RMS",  style="white",        width=16, justify="right")
    table.add_column("Discharge Temp", style="white",        width=16, justify="right")
    table.add_column("Risk Score",     style="white",        width=12, justify="right")
    table.add_column("Status",         style="white",        width=12, justify="center")
    table.add_column("Alert",          style="white",        min_width=30)

    for entry in history:
        is_anom = entry.is_anomalous

        # ── Vibration cell: red + bold if above ISO threshold ─────────────────
        vib_val = f"{entry.vibration_rms:.4f} mm/s"
        vib_cell = (
            Text(vib_val, style="bold red blink") if is_anom
            else Text(vib_val, style="bright_green")
        )

        # ── Discharge temp cell: orange on degraded readings ──────────────────
        dtemp_val = f"{entry.discharge_temp:.2f} °F"
        dtemp_cell = (
            Text(dtemp_val, style="bold orange1") if entry.discharge_temp > 110.0
            else Text(dtemp_val, style="bright_green")
        )

        # ── Risk score cell ───────────────────────────────────────────────────
        risk_val = f"{entry.risk_score:.4f}"
        if entry.risk_score >= 0.75:
            risk_cell = Text(risk_val, style="bold red")
        elif entry.risk_score >= 0.40:
            risk_cell = Text(risk_val, style="bold yellow")
        else:
            risk_cell = Text(risk_val, style="bright_green")

        # ── Status badge ──────────────────────────────────────────────────────
        status_cell = (
            Text("⚠ ANOMALY", style="bold red blink") if is_anom
            else Text("✓ NOMINAL", style="bold bright_green")
        )

        # ── Alert snippet (truncated for table width) ─────────────────────────
        alert_style = "red" if is_anom else "green"
        alert_cell = Text(entry.alert_snippet[:80], style=alert_style)

        table.add_row(
            str(entry.row_index),
            entry.timestamp,
            vib_cell,
            dtemp_cell,
            risk_cell,
            status_cell,
            alert_cell,
        )

    return table


def build_stats_panel(stats: SessionStats, api_url: str) -> Panel:
    """Render the summary statistics panel shown above the history table."""
    content = (
        f"[bold]Endpoint :[/bold]  [cyan]{api_url}[/cyan]\n"
        f"[bold]Uptime   :[/bold]  [white]{stats.uptime}[/white]    "
        f"[bold]Loop     :[/bold]  [white]#{stats.loop_count}[/white]\n"
        f"[bold]Sent     :[/bold]  [white]{stats.total_sent}[/white]    "
        f"[bold]Anomalous:[/bold]  [red]{stats.total_anomalous}[/red]    "
        f"[bold]Nominal  :[/bold]  [green]{stats.total_nominal}[/green]    "
        f"[bold]Skipped  :[/bold]  [yellow]{stats.total_skipped}[/yellow]    "
        f"[bold]Errors   :[/bold]  [red]{stats.total_errors}[/red]    "
        f"[bold]Anomaly Rate:[/bold]  [bold magenta]{stats.anomaly_rate}[/bold magenta]"
    )
    return Panel(
        content,
        title="[bold white]🌡  Session Statistics[/bold white]",
        border_style="bright_blue",
        style="on grey7",
    )


def build_layout() -> Layout:
    """
    Define the terminal layout structure.

    ┌─────────────────────────────────┐
    │  header (stats panel)           │
    ├─────────────────────────────────┤
    │  body  (scrolling history)      │
    ├─────────────────────────────────┤
    │  footer (status / error msg)    │
    └─────────────────────────────────┘
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    return layout


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN SIMULATION LOOP
# ══════════════════════════════════════════════════════════════════════════════

def run_simulator(
    api_url: str,
    delay_seconds: float,
    infinite_loop: bool,
) -> None:
    """
    Core simulation loop: reads CSV, posts payloads, updates Rich dashboard.

    Parameters
    ----------
    api_url        : str   FastAPI endpoint URL.
    delay_seconds  : float Sleep between each POST (simulates sensor interval).
    infinite_loop  : bool  If True, wraps around to row 0 after row 999.
    """
    console = Console()

    # ── Load CSV ──────────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(CSV_FILE)
    except FileNotFoundError:
        console.print(
            f"[bold red]✗ CSV file not found: '{CSV_FILE}'. "
            "Run simulate_pf_curve_data.py first.[/bold red]"
        )
        sys.exit(1)

    console.print(
        f"[bold green]✓ Loaded {len(df):,} rows from '{CSV_FILE}'.[/bold green]"
    )

    stats = SessionStats()
    history: list[HistoryRow] = []
    layout = build_layout()

    # ── Row iterator: finite or infinite cycle ─────────────────────────────────
    def row_generator():
        if infinite_loop:
            # cycle() seamlessly wraps the index list forever
            for idx in cycle(range(len(df))):
                if idx == 0 and stats.total_sent > 0:
                    stats.loop_count += 1
                yield idx, df.iloc[idx]
        else:
            for idx, row in df.iterrows():
                yield idx, row

    # ── Rich Live: single context manager owns the entire session ─────────────
    # refresh_per_second=4 caps the render rate to prevent CPU thrash.
    # transient=False keeps the final dashboard state visible after Ctrl+C.
    with Live(
        layout,
        console=console,
        refresh_per_second=4,
        vertical_overflow="visible",
        transient=False,
    ) as live:

        # Initialise layout slots before first update
        layout["header"].update(build_stats_panel(stats, api_url))
        layout["body"].update(build_history_table(history))
        layout["footer"].update(Panel(
            "[dim]Initialising stream...[/dim]",
            border_style="bright_blue",
        ))
        live.refresh()

        try:
            for row_idx, row in row_generator():

                payload = build_payload(row)
                vibration: float = payload["vibration_rms"]

                # ── POST with retry / backoff ─────────────────────────────────
                result = post_with_retry(
                    api_url=api_url,
                    payload=payload,
                    stats=stats,
                    live=live,
                    layout=layout,
                    history=history,
                )

                if result is None:
                    # Row was skipped (422 or server error) — update and continue
                    layout["header"].update(build_stats_panel(stats, api_url))
                    live.refresh()
                    time.sleep(delay_seconds)
                    continue

                # ── Update session stats ──────────────────────────────────────
                stats.total_sent += 1
                is_anom: bool = result.get("is_anomalous", False)
                if is_anom:
                    stats.total_anomalous += 1
                else:
                    stats.total_nominal += 1

                # ── Append to scrolling history (keep last N rows) ────────────
                ts_raw: str = payload["timestamp"]
                # Trim to HH:MM:SS for table readability
                try:
                    ts_display = datetime.fromisoformat(ts_raw).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    ts_display = ts_raw[:19]

                alert_full: str = result.get("actionable_alert", "")
                history.append(HistoryRow(
                    timestamp=ts_display,
                    vibration_rms=vibration,
                    discharge_temp=payload["discharge_temp"],
                    risk_score=float(result.get("failure_risk_score", 0.0)),
                    is_anomalous=is_anom,
                    alert_snippet=alert_full,
                    row_index=row_idx + 1,
                ))
                # Trim history to the last N rows
                if len(history) > MAX_HISTORY_ROWS:
                    history.pop(0)

                # ── Rebuild dashboard panels ──────────────────────────────────
                layout["header"].update(build_stats_panel(stats, api_url))
                layout["body"].update(build_history_table(history))

                status_style = "bold red" if is_anom else "bold green"
                status_icon = "⚠" if is_anom else "✓"
                layout["footer"].update(Panel(
                    f"[{status_style}]{status_icon} Row {row_idx + 1:>4} | "
                    f"vib={vibration:.4f} mm/s | "
                    f"risk={result.get('failure_risk_score', 0):.4f} | "
                    f"loop=#{stats.loop_count}[/{status_style}]",
                    border_style="bright_blue",
                ))

                # live.refresh() is called automatically at refresh_per_second
                # rate; explicit call here ensures the footer updates immediately
                # after each row regardless of the refresh timer.
                live.refresh()
                time.sleep(delay_seconds)

        except KeyboardInterrupt:
            layout["footer"].update(Panel(
                "[bold yellow]⏹  Stream stopped by user (Ctrl+C).[/bold yellow]",
                border_style="yellow",
            ))
            live.refresh()

    # ── Final summary (printed after Live context exits) ─────────────────────
    console.print()
    console.rule("[bold bright_blue]Session Complete[/bold bright_blue]")
    console.print(
        f"  [bold]Total sent    :[/bold] {stats.total_sent}\n"
        f"  [bold]Anomalous     :[/bold] [red]{stats.total_anomalous}[/red]\n"
        f"  [bold]Nominal       :[/bold] [green]{stats.total_nominal}[/green]\n"
        f"  [bold]Skipped (422) :[/bold] [yellow]{stats.total_skipped}[/yellow]\n"
        f"  [bold]Errors        :[/bold] [red]{stats.total_errors}[/red]\n"
        f"  [bold]Loops         :[/bold] {stats.loop_count}\n"
        f"  [bold]Uptime        :[/bold] {stats.uptime}"
    )
    console.rule()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = parse_args()
    run_simulator(
        api_url=args.api_url,
        delay_seconds=args.delay_seconds,
        infinite_loop=args.infinite_loop,
    )


if __name__ == "__main__":
    main()