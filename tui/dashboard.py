from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Tuple

from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
import logging


@dataclass
class UploadProgress:
    processed: int
    total: int
    failed: int
    mb_per_second: float
    recent_bandwidth_mb_s: float
    bytes_uploaded: int
    verifications_total: int
    verifications_passed: int
    elapsed_seconds: float
    eta_seconds: float


class FullScreenDashboard:
    """Full-screen dashboard with persistent panes for each step and a live log."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console(force_terminal=True)
        self._live: Live | None = None
        self._layout: Layout | None = None
        # Store log as list of (line, is_colored_markup)
        self._log: List[tuple[str, bool]] = []
        self._max_log = 2000
        # Pane contents
        self._overview: List[str] = []
        self._discovery: List[str] = ["Waiting..."]
        self._checking: List[str] = ["Waiting..."]
        self._upload: List[str] = ["Waiting..."]
        self._summary: List[str] = ["Pending..."]
        self._footer_text: str = "Press Ctrl+C to cancel at any time"
        # Optional progress bars per pane
        self._progress: Dict[str, float | None] = {
            "discovery": None,
            "checking": None,
            "upload": None,
        }
        # Modal overlay
        self._modal: Dict[str, List[str]] | None = None  # keys: title, lines, prompt

    def start(self):
        if self._live is None:
            # Build persistent layout once and update contents incrementally
            if self._modal:
                renderable = self._modal_renderable()
                self._live = Live(renderable, console=self.console, refresh_per_second=8, transient=False, screen=True)
                self._live.start()
                return
            if self._layout is None:
                self._layout = self._build_layout()
            self._update_layout_contents(self._layout)
            self._live = Live(self._layout, console=self.console, refresh_per_second=8, transient=False, screen=True)
            self._live.start()

    def stop(self):
        if self._live is not None:
            try:
                self._live.stop()
            finally:
                self._live = None

    # --- public pane setters ---
    def set_overview(self, lines: List[str]):
        self._overview = [str(x) for x in lines]
        self.refresh()

    # Back-compat alias
    def set_header(self, lines: List[str]):
        self.set_overview(lines)

    def set_discovery(self, lines: List[str], percent: float | None = None):
        self._discovery = [str(x) for x in lines]
        self._progress["discovery"] = percent
        self.refresh()

    def set_checking(self, lines: List[str], percent: float | None = None):
        self._checking = [str(x) for x in lines]
        self._progress["checking"] = percent
        self.refresh()

    def set_upload(self, lines: List[str], percent: float | None = None):
        self._upload = [str(x) for x in lines]
        self._progress["upload"] = percent
        self.refresh()

    def set_summary(self, lines: List[str]):
        self._summary = [str(x) for x in lines]
        self.refresh()

    def set_footer(self, text: str):
        self._footer_text = str(text)
        self.refresh()

    def add_log(self, line: str):
        self._log.append((str(line), False))
        if len(self._log) > self._max_log:
            self._log = self._log[-self._max_log:]
        self.refresh()

    def add_log_colored(self, line: str, style: str = "bold yellow") -> int:
        """Append a colored log line using rich markup and return its index."""
        colored_line = f"[{style}]{str(line)}[/]"
        self._log.append((colored_line, True))
        if len(self._log) > self._max_log:
            self._log = self._log[-self._max_log:]
        self.refresh()
        return len(self._log) - 1

    def update_log(self, index: int, new_line: str, colored: bool = False):
        """Update an existing log line by index, optionally keeping color markup."""
        try:
            self._log[index] = (str(new_line), bool(colored))
            self.refresh()
        except Exception:
            # Ignore out of range or other issues
            pass

    # --- internal rendering ---
    def _panel(self, title: str, lines: List[str], bar_percent: float | None = None) -> Panel:
        table = Table.grid(padding=(0, 1), expand=True)
        if bar_percent is not None:
            table.add_row(ProgressBar(total=100, completed=max(0, min(100, int(bar_percent))), pulse=False))
        for line in lines:
            # Ensure strings are treated as literal text (no Rich markup parsing)
            # so content like "[s3://bucket]" renders correctly.
            table.add_row(Text(str(line)))
        return Panel(Align.left(table), title=title, padding=(0, 1), expand=True)

    def _build_layout(self) -> Layout:
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=1),
        )
        layout["body"].split_row(
            Layout(name="main", ratio=3),
            Layout(name="logs", ratio=2),
        )
        layout["main"].split(
            Layout(name="discovery", ratio=1),
            Layout(name="checking", ratio=1),
            Layout(name="upload", ratio=2),
            Layout(name="summary", ratio=1),
        )
        return layout

    def _update_layout_contents(self, layout: Layout) -> None:
        # Panels
        layout["header"].update(self._panel("OVERVIEW", self._overview))
        layout["discovery"].update(self._panel("DISCOVERY", self._discovery, self._progress.get("discovery")))
        layout["checking"].update(self._panel("CHECKING", self._checking, self._progress.get("checking")))
        layout["upload"].update(self._panel("UPLOAD", self._upload, self._progress.get("upload")))
        layout["summary"].update(self._panel("SUMMARY", self._summary))
        # Logs (render only tail)
        tail_entries = self._log[-25:] if self._log else [("No logs yet...", False)]
        log_table = Table.grid(padding=(0, 1), expand=True)
        for entry in tail_entries:
            try:
                text, is_colored = entry
            except Exception:
                text, is_colored = (str(entry), False)
            if is_colored:
                log_table.add_row(Text.from_markup(text))
            else:
                log_table.add_row(str(text))
        layout["logs"].update(Panel(Align.left(log_table), title="LOG", padding=(0, 1), expand=True))
        layout["footer"].update(Text(self._footer_text, style="bold"))

    def refresh(self):
        if self._modal:
            # Render modal overlay only
            outer = self._modal_renderable()
            if self._live is None:
                self.start()
            self._live.update(outer)
            return
        # Normal refresh path updates in-place
        if self._layout is None:
            self._layout = self._build_layout()
        self._update_layout_contents(self._layout)
        if self._live is None:
            self.start()
        else:
            self._live.update(self._layout)

    # --- modal API ---
    def show_modal(self, title: str, lines: List[str], prompt: str = ""):
        self._modal = {"title": [title][0], "lines": [str(x) for x in lines], "prompt": prompt}
        self.refresh()

    def clear_modal(self):
        self._modal = None
        self.refresh()

    # --- helpers ---
    def _modal_renderable(self):
        title = self._modal.get("title", "") if self._modal else ""
        lines = self._modal.get("lines", []) if self._modal else []
        prompt = self._modal.get("prompt", "") if self._modal else ""
        content = Table.grid(padding=(0, 1), expand=False)
        for ln in lines:
            content.add_row(ln)
        if prompt:
            content.add_row("")
            content.add_row(prompt)
        panel = Panel(Align.center(content), title=title, padding=(1, 2), expand=False)
        outer = Table.grid(expand=True)
        outer.add_row(Align.center(panel))
        return outer


class DashboardLogHandler(logging.Handler):
    """A logging handler that forwards messages into the dashboard's log pane."""

    def __init__(self, dashboard: FullScreenDashboard, level=logging.INFO):
        super().__init__(level)
        self.dashboard = dashboard

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.dashboard.add_log(msg)
        except Exception:
            pass


