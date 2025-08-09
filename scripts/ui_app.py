from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import threading
try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency at runtime
    psutil = None  # type: ignore
import boto3
from botocore.exceptions import ClientError

from core.config_loader import load_config
from core.smoothing import exponential_moving_average
from core.sync_engine import SyncEngine, EngineConfig, FileToSync
from core.auto_tune import SystemSnapshot, estimate_worker_counts
from tui.dashboard import FullScreenDashboard, DashboardLogHandler
from scripts.logger import SyncLogger
# Identity will be fetched directly via STS to avoid extra noise


@dataclass
class RunOptions:
    config_file: str | None
    profile: str | None
    bucket_name: str | None
    local_path: str | None
    dry_run: bool = False
    no_confirm: bool = False
    max_concurrent_uploads: int = 0
    max_concurrent_checks: int = 0


class SyncTUI:
    def __init__(self, options: RunOptions):
        self.project_root = Path(__file__).parent.parent
        self.config = load_config(self.project_root, options.config_file)
        self.profile = options.profile or self.config.get("aws", {}).get("profile", "default")
        self.bucket_name = options.bucket_name or self.config.get("s3", {}).get("bucket_name")
        self.local_path = Path(options.local_path or self.config.get("sync", {}).get("local_path", "./data"))
        sync_cfg = self.config.get("sync", {})
        s3_cfg = self.config.get("s3", {})

        # Auto-tune workers if user passes 0 via CLI (or config later)
        cpu_count = os.cpu_count() or 1
        try:
            import psutil as _ps  # type: ignore  # reuse if available
        except Exception:  # pragma: no cover
            _ps = None  # type: ignore
        total_mem = getattr(_ps.virtual_memory(), 'total', None) if _ps else None
        avail_mem = getattr(_ps.virtual_memory(), 'available', None) if _ps else None
        chunk_size_mb = sync_cfg.get("chunk_size_mb", 100)
        sys_snap = SystemSnapshot(cpu_count_logical=cpu_count, total_memory_bytes=total_mem, available_memory_bytes=avail_mem)
        # CLI value 0 triggers estimation; otherwise use provided value
        cli_uploads = int(getattr(options, 'max_concurrent_uploads', 20) or 20)
        cli_checks = int(getattr(options, 'max_concurrent_checks', 20) or 20)
        if cli_uploads == 0 or cli_checks == 0:
            est_uploads, est_checks = estimate_worker_counts(chunk_size_mb, sys_snap)
            if cli_uploads == 0:
                options.max_concurrent_uploads = est_uploads
            if cli_checks == 0:
                options.max_concurrent_checks = est_checks

        # Auto-tune workers by default; explicit CLI values override
        cpu_count = os.cpu_count() or 1
        try:
            import psutil as _ps  # type: ignore  # reuse if available
        except Exception:  # pragma: no cover
            _ps = None  # type: ignore
        mem_info = _ps.virtual_memory() if _ps else None
        total_mem = getattr(mem_info, 'total', None)
        avail_mem = getattr(mem_info, 'available', None)
        chunk_size_mb = sync_cfg.get("chunk_size_mb", 100)
        sys_snap = SystemSnapshot(
            cpu_count_logical=cpu_count,
            total_memory_bytes=total_mem,
            available_memory_bytes=avail_mem,
        )
        cli_uploads = int(getattr(options, 'max_concurrent_uploads', 0) or 0)
        cli_checks = int(getattr(options, 'max_concurrent_checks', 0) or 0)
        if cli_uploads > 0 and cli_checks > 0:
            chosen_uploads = cli_uploads
            chosen_checks = cli_checks
            self._worker_source = "manual"
        else:
            est_uploads, est_checks = estimate_worker_counts(chunk_size_mb, sys_snap)
            chosen_uploads = cli_uploads if cli_uploads > 0 else est_uploads
            chosen_checks = cli_checks if cli_checks > 0 else est_checks
            self._worker_source = "auto"
        # Persist chosen values back to options
        options.max_concurrent_uploads = chosen_uploads
        options.max_concurrent_checks = chosen_checks

        self.engine = SyncEngine(
            EngineConfig(
                profile=self.profile,
                bucket_name=self.bucket_name,
                local_path=self.local_path,
                storage_class=s3_cfg.get("storage_class", "STANDARD"),
                verify_upload=sync_cfg.get("verify_upload", True),
                hash_algorithm=sync_cfg.get("hash_algorithm", "sha256"),
                max_retries=sync_cfg.get("max_retries", 3),
                retry_delay_base=sync_cfg.get("retry_delay_base", 1),
                retry_delay_max=sync_cfg.get("retry_delay_max", 60),
                chunk_size_mb=sync_cfg.get("chunk_size_mb", 100),
                include_patterns=sync_cfg.get("include_patterns", ["*"]),
                exclude_patterns=sync_cfg.get("exclude_patterns", []),
                max_concurrent_uploads=chosen_uploads,
                max_concurrent_checks=chosen_checks,
            )
        )
        self.console = FullScreenDashboard()
        # Attach dashboard log handler to SyncLogger's logger and suppress stdout handler
        self.logger = SyncLogger('s3-sync', self.config)
        # Remove any console/stream handlers that write directly to stdout to prevent
        # terminal output from disrupting the full-screen Live display
        try:
            for h in list(self.logger.logger.handlers):
                if isinstance(h, logging.StreamHandler) and getattr(h, 'stream', None) is sys.stdout:
                    self.logger.logger.removeHandler(h)
        except Exception:
            pass
        handler = DashboardLogHandler(self.console)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        self.logger.logger.addHandler(handler)

        # Prepare stdout/stderr redirection so stray prints go to the dashboard log
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        class _DashboardWriter:
            def __init__(self, dashboard: FullScreenDashboard):
                self.dashboard = dashboard
                self._buffer = ""
            def write(self, s: str):
                if not isinstance(s, str):
                    s = str(s)
                self._buffer += s
                while "\n" in self._buffer:
                    line, self._buffer = self._buffer.split("\n", 1)
                    if line:
                        try:
                            self.dashboard.add_log(line)
                        except Exception:
                            pass
            def flush(self):
                if self._buffer:
                    try:
                        self.dashboard.add_log(self._buffer)
                    except Exception:
                        pass
                    self._buffer = ""
        self._dashboard_writer = _DashboardWriter(self.console)

        # Log the chosen worker configuration and the inputs used
        try:
            total_gb = (total_mem or 0) / (1024 * 1024 * 1024)
            avail_gb = (avail_mem or 0) / (1024 * 1024 * 1024)
            self.logger.log_info(
                f"WORKERS: uploads={chosen_uploads} checks={chosen_checks} "
                f"source={self._worker_source} cpu={cpu_count} "
                f"mem_total={total_gb:.1f}GB mem_avail={avail_gb:.1f}GB chunk={chunk_size_mb}MB"
            )
        except Exception:
            # Best-effort logging; continue silently on failure
            pass

        # Initialize network bandwidth sampling state (system-wide)
        try:
            self._net_prev = psutil.net_io_counters() if psutil else None  # type: ignore[attr-defined]
        except Exception:
            self._net_prev = None
        self._net_prev_time = time.monotonic()
        # Moving average for network bandwidth (MB/s)
        self._net_bw_ema_mb_s: float | None = None
        # Time constant for EMA smoothing (seconds). Higher = smoother, slower to react.
        self._net_bw_tau_seconds: float = 5.0

        # Moving averages for CPU and memory utilization (%) using same EMA method
        self._cpu_pct_ema: float | None = None
        self._mem_pct_ema: float | None = None
        # Use same default time constant as network to keep behavior consistent
        self._cpu_pct_tau_seconds: float = self._net_bw_tau_seconds
        self._mem_pct_tau_seconds: float = self._net_bw_tau_seconds
        self._cpu_prev_time = time.monotonic()
        self._mem_prev_time = time.monotonic()

    # ---------- Small helpers for concise overview formatting ----------
    @staticmethod
    def _human_bytes(num_bytes: int | None) -> str:
        if not num_bytes or num_bytes <= 0:
            return "0.0 GB"
        gb = num_bytes / (1024 * 1024 * 1024)
        return f"{gb:.1f} GB"

    @staticmethod
    def build_overview_line(local_path: Path, bucket_name: str | None, identity: dict | None = None,
                             file_count: int | None = None, total_bytes: int | None = None,
                             status: str | None = None) -> List[str]:
        # Compose a single concise BBS-style line
        bucket_display = bucket_name or "(unknown)"
        left = f"Sync: [{str(local_path)}] => [s3://{bucket_display}]"
        if identity:
            acct = identity.get('account_alias') or identity.get('account_id') or 'account?'
            user = identity.get('username') or '-'
            region = identity.get('region') or '-'
            mid = f"AWS: {acct}/{user} @{region}"
        else:
            mid = "AWS: unknown"
        if file_count is not None or total_bytes is not None:
            right = f"Files: {file_count or 0} | Size: {SyncTUI._human_bytes(total_bytes or 0)}"
        else:
            right = "Files: … | Size: …"
        pieces = [left, mid, right]
        line = " | ".join(pieces)
        if status:
            return [line, f"Status: {status}"]
        return [line]

    def _bucket_file_age(self, file_path: Path) -> str:
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        except Exception:
            return ">=1y"
        days = (datetime.now() - mtime).days
        if days < 1:
            return "<1d"
        if days < 7:
            return "<1w"
        if days < 30:
            return "<1m"
        if days < 180:
            return "<6m"
        if days < 365:
            return "<1y"
        return ">=1y"

    def _wait_for_enter(self) -> bool:
        try:
            input()
            return True
        except EOFError:
            try:
                with open('/dev/tty') as tty:
                    tty.readline()
                    return True
            except Exception:
                time.sleep(2.0)
                return False
        except KeyboardInterrupt:
            raise

    def _read_line(self) -> str:
        # Prefer the controlling TTY for input so we work even if stdin is redirected
        try:
            with open('/dev/tty') as tty:
                return tty.readline().strip()
        except Exception:
            try:
                return input()
            except Exception:
                time.sleep(2.0)
                return ""

    def _read_key_blocking(self) -> str:
        """Read a single key from /dev/tty or stdin without requiring Enter.
        Falls back to line-read if raw mode unsupported."""
        try:
            import termios, tty, select, os
            fd = None
            fobj = None
            try:
                fobj = open('/dev/tty')
                fd = fobj.fileno()
            except Exception:
                if sys.stdin.isatty():
                    fd = sys.stdin.fileno()
                else:
                    ln = self._read_line()
                    return ln[:1] if ln else ""
            old = termios.tcgetattr(fd)
            try:
                # Enter cbreak and disable echo to avoid visible keystrokes
                tty.setcbreak(fd)
                attrs = termios.tcgetattr(fd)
                attrs[3] = attrs[3] & ~termios.ECHO  # lflag: disable ECHO
                termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
                while True:
                    r, _, _ = select.select([fd], [], [], 0.25)
                    if r:
                        ch = os.read(fd, 1)
                        try:
                            return ch.decode(errors='ignore')
                        except Exception:
                            return ""
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
                try:
                    if fobj:
                        fobj.close()
                except Exception:
                    pass
        except Exception:
            ln = self._read_line()
            return ln[:1] if ln else ""

    def _current_net_bandwidth_mb_s(self) -> float:
        """Return smoothed system network throughput in MB/s (send+recv).
        Uses psutil if available; returns 0.0 if unavailable. The instantaneous
        measurement is smoothed with an exponential moving average to reduce noise.
        """
        try:
            if not psutil:
                return 0.0
            now = time.monotonic()
            counters = psutil.net_io_counters()
            prev = getattr(self, "_net_prev", None)
            prev_time = getattr(self, "_net_prev_time", now)
            # Update state for next call
            self._net_prev = counters
            self._net_prev_time = now
            if not prev:
                # Seed EMA on first valid sample
                self._net_bw_ema_mb_s = 0.0
                return 0.0
            dt = max(1e-6, now - prev_time)
            cur_bytes = (counters.bytes_sent + counters.bytes_recv) - (prev.bytes_sent + prev.bytes_recv)
            inst_mb_s = (cur_bytes / (1024 * 1024)) / dt
            self._net_bw_ema_mb_s = exponential_moving_average(
                previous_value=self._net_bw_ema_mb_s,
                sample_value=inst_mb_s,
                delta_seconds=dt,
                time_constant_seconds=self._net_bw_tau_seconds,
            )
            return float(self._net_bw_ema_mb_s or 0.0)
        except Exception:
            return 0.0

    def _current_cpu_percent(self) -> float:
        """Return smoothed CPU utilization percentage (0-100).
        Uses EMA with the same time-constant approach as network bandwidth.
        """
        try:
            if not psutil:
                return 0.0
            now = time.monotonic()
            prev_time = getattr(self, "_cpu_prev_time", now)
            # Update time state for next call
            self._cpu_prev_time = now
            inst_pct = float(psutil.cpu_percent(interval=None))
            # Seed EMA on first valid sample to 0.0 for consistency with net behavior
            if self._cpu_pct_ema is None:
                self._cpu_pct_ema = 0.0
                return 0.0
            dt = max(1e-6, now - prev_time)
            self._cpu_pct_ema = exponential_moving_average(
                previous_value=self._cpu_pct_ema,
                sample_value=inst_pct,
                delta_seconds=dt,
                time_constant_seconds=self._cpu_pct_tau_seconds,
            )
            return float(self._cpu_pct_ema or 0.0)
        except Exception:
            return 0.0

    def _current_mem_percent(self) -> float:
        """Return smoothed memory utilization percentage (0-100).
        Uses EMA with the same time-constant approach as network bandwidth.
        """
        try:
            if not psutil:
                return 0.0
            now = time.monotonic()
            prev_time = getattr(self, "_mem_prev_time", now)
            # Update time state for next call
            self._mem_prev_time = now
            vm = psutil.virtual_memory()
            inst_pct = float(getattr(vm, 'percent', 0.0))
            # Seed EMA on first valid sample to 0.0 for consistency with net behavior
            if self._mem_pct_ema is None:
                self._mem_pct_ema = 0.0
                return 0.0
            dt = max(1e-6, now - prev_time)
            self._mem_pct_ema = exponential_moving_average(
                previous_value=self._mem_pct_ema,
                sample_value=inst_pct,
                delta_seconds=dt,
                time_constant_seconds=self._mem_pct_tau_seconds,
            )
            return float(self._mem_pct_ema or 0.0)
        except Exception:
            return 0.0

    def _confirm_in_log(self, question: str) -> bool:
        # Show colored prompt in log area and clear highlight when answered
        prompt_index = self.console.add_log_colored(f"PROMPT: {question} (y/n)", style="bold yellow")
        while True:
            # Read a single key without requiring Enter
            try:
                import termios, tty, select, os
                fd = None
                fobj = None
                try:
                    fobj = open('/dev/tty')
                    fd = fobj.fileno()
                except Exception:
                    if sys.stdin.isatty():
                        fd = sys.stdin.fileno()
                    else:
                        ans = (self._read_line() or "").strip().lower()
                        decision = ans.startswith('y')
                        self.console.update_log(prompt_index, f"PROMPT: {question} ({'yes' if decision else 'no'})", colored=False)
                        return decision
                old = termios.tcgetattr(fd)
                try:
                    # Enter cbreak and disable echo so the 'y'/'n' keystroke doesn't print to terminal
                    tty.setcbreak(fd)
                    attrs = termios.tcgetattr(fd)
                    attrs[3] = attrs[3] & ~termios.ECHO
                    termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
                    while True:
                        r, _, _ = select.select([fd], [], [], 0.1)
                        if r:
                            ch = os.read(fd, 1).decode(errors='ignore').lower()
                            if ch in ('y', 'n'):
                                decision = (ch == 'y')
                                self.logger.log_info("CONFIRM: yes" if decision else "CONFIRM: no")
                                self.console.update_log(prompt_index, f"PROMPT: {question} ({'yes' if decision else 'no'})", colored=False)
                                return decision
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                    try:
                        if fobj:
                            fobj.close()
                    except Exception:
                        pass
            except Exception:
                ans = (self._read_line() or "").strip().lower()
                decision = ans.startswith('y')
                self.console.update_log(prompt_index, f"PROMPT: {question} ({'yes' if decision else 'no'})", colored=False)
                return decision

    def _wait_for_quit(self):
        self.console.set_footer("Press q to quit…")
        while True:
            ans = (self._read_key_blocking() or "").strip().lower()
            if ans == "q":
                return

    def _get_current_costs(self) -> float | None:
        try:
            session = boto3.Session(profile_name=self.profile)
            ce = session.client('ce')
            now = datetime.now()
            start_date = now.replace(day=1).strftime('%Y-%m-%d')
            end_date = (now.replace(day=1) + timedelta(days=32)).replace(day=1).strftime('%Y-%m-%d')
            resp = ce.get_cost_and_usage(
                TimePeriod={'Start': start_date, 'End': end_date},
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}],
                Filter={'Dimensions': {'Key': 'SERVICE', 'Values': ['Amazon Simple Storage Service']}}
            )
            s3_cost = 0.0
            if resp.get('ResultsByTime') and resp['ResultsByTime'][0].get('Groups'):
                for g in resp['ResultsByTime'][0]['Groups']:
                    if 'Amazon Simple Storage Service' in g.get('Keys', []):
                        s3_cost = float(g['Metrics']['BlendedCost']['Amount'])
                        break
            return s3_cost
        except Exception as e:
            self.logger.log_warning(f"COSTS: unavailable ({e})")
            return None

    def _extract_username_from_arn(self, arn: str) -> str:
        try:
            if '/user/' in arn:
                return arn.split('/user/')[-1]
            if 'assumed-role' in arn:
                parts = arn.split('/')
                if len(parts) >= 2:
                    return parts[-2]
            return arn.split('/')[-1] if '/' in arn else arn
        except Exception:
            return 'unknown'

    def _get_identity_info(self) -> dict | None:
        # Direct STS + optional alias (no extra wrappers/noise)
        try:
            session = boto3.Session(profile_name=self.profile)
            sts = session.client('sts')
            resp = sts.get_caller_identity()
            alias = None
            try:
                iam = session.client('iam')
                r = iam.list_account_aliases()
                alias = (r.get('AccountAliases') or [None])[0]
            except Exception:
                alias = None
            region = session.region_name or os.environ.get('AWS_DEFAULT_REGION') or 'us-east-1'
            return {
                'account_id': resp.get('Account'),
                'user_id': resp.get('UserId'),
                'arn': resp.get('Arn'),
                'username': self._extract_username_from_arn(resp.get('Arn', '')),
                'account_alias': alias,
                'region': region,
            }
        except Exception as e:
            self.logger.log_warning(f"IDENTITY fallback failed: {e}")
            return None

    def run(self) -> int:
        self.console.start()
        # Overview
        self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, None, None, None, status="preparing"))
        self.logger.log_info("Initialized full-screen interface")

        # Identity check → log to log pane (no modal)
        try:
            info = self._get_identity_info()
            if not info:
                raise RuntimeError("identity-unavailable")
            self.logger.log_info(
                f"IDENTITY: account={info.get('account_id')} alias={info.get('account_alias') or '-'} "
                f"user={info.get('username')} region={info.get('region')}"
            )
            self.logger.log_info(f"ARN: {info.get('arn')}")
            self.logger.log_info(f"Target bucket: {self.bucket_name}")
            # Reflect identity into overview
            self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, info, None, None, status="awaiting confirmation"))
            # Confirmation to proceed with this account/bucket
            if not self._confirm_in_log("Proceed with this AWS account and bucket?"):
                self.console.set_summary(["Cancelled by user before checking."])
                self._wait_for_quit()
                self.console.stop()
                return 1
        except Exception as e:
            self.logger.log_warning(f"IDENTITY: unavailable ({e})")
            self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, None, None, None, status="awaiting confirmation (identity unavailable)"))
            if not self._confirm_in_log("Proceed without identity details?"):
                self.console.set_summary(["Cancelled by user before checking."])
                self._wait_for_quit()
                self.console.stop()
                return 1

        # Discover
        discover_start = datetime.now()
        all_candidates = self.engine.discover_all_files()
        total_all = len(all_candidates)
        # Determine total bytes across all discovered files
        total_bytes_all = 0
        for it in all_candidates:
            try:
                total_bytes_all += it.local_path.stat().st_size
            except Exception:
                pass
        elapsed_discover = (datetime.now() - discover_start).total_seconds()
        rate = total_all / elapsed_discover if elapsed_discover > 0 else 0.0
        self.console.set_discovery([f"Files found: {total_all}", f"Elapsed: {elapsed_discover:.1f}s  Rate: {rate:.1f} files/s"], percent=100.0)
        self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, info if 'info' in locals() else None, total_all, total_bytes_all, status="discovery complete"))
        self.logger.log_info(f"Discovered {total_all} files in {elapsed_discover:.1f}s")

        # Check which need sync
        checked_done = 0
        check_start = datetime.now()
        def on_check_progress(done, total):
            nonlocal checked_done
            checked_done = done
            pct = (done / total * 100.0) if total else 0.0
            elapsed = (datetime.now() - check_start).total_seconds()
            files_per_s = done / elapsed if elapsed > 0 else 0.0
            # Metrics
            workers = getattr(self.engine.config, 'max_concurrent_checks', 0)
            active_threads = threading.active_count()
            cpu_pct = self._current_cpu_percent()
            mem_pct = self._current_mem_percent()
            net_mbps = self._current_net_bandwidth_mb_s()
            self.console.set_checking([
                f"Checked: {done}/{total}",
                f"Elapsed: {elapsed:.1f}s  Files/s: {files_per_s:.1f}",
                f"Workers: {workers}  Threads: {active_threads}  CPU: {cpu_pct:.0f}%  Mem: {mem_pct:.0f}%  Net: {net_mbps:.2f} MB/s",
            ], percent=pct)
        to_sync = self.engine.check_files_to_sync(all_candidates, on_progress=on_check_progress)
        elapsed_check = (datetime.now() - check_start).total_seconds()
        self.logger.log_info(f"Check phase completed: {len(to_sync)} need upload (from {total_all}) in {elapsed_check:.1f}s")
        self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, info if 'info' in locals() else None, total_all, total_bytes_all, status=f"check complete (to upload: {len(to_sync)})"))

        if not to_sync:
            # Show costs and summary, and wait for user to quit
            current_s3_cost = self._get_current_costs()
            if current_s3_cost is not None:
                self.logger.log_info(f"COSTS: current_month_to_date=${current_s3_cost:.2f}")
            head_cost_per_1000 = float(self.config.get('pricing', {}).get('head_per_1000', 0.0004))
            est_head = (len(all_candidates) / 1000.0) * head_cost_per_1000
            self.logger.log_info(f"ESTIMATES: to_upload=0 head_cost≈${est_head:.3f}")
            self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, info if 'info' in locals() else None, total_all, total_bytes_all, status="check complete (up to date)"))
            self.console.set_summary([
                "Everything is up to date.",
                f"Checked files: {total_all}",
                (f"Current S3 MTD: ${current_s3_cost:.2f}" if current_s3_cost is not None else "Current S3 MTD: n/a"),
                f"Estimated HEAD cost for checks: ${est_head:.3f}",
            ])
            self._wait_for_quit()
            self.console.stop()
            return 0

        # Confirmation (simple, full-screen)
        sample = [f"{i+1:2d}. {it.local_path.name} -> s3://{self.bucket_name}/{it.s3_key}" for i, it in enumerate(to_sync[:10])]
        more = [f"... and {len(to_sync) - 10} more files"] if len(to_sync) > 10 else []
        # Cost estimate → log to log pane (no modal)
        total_size = 0
        for it in to_sync:
            try:
                total_size += it.local_path.stat().st_size
            except Exception:
                pass
        gb = total_size / (1024*1024*1024)
        # Very rough estimates (can be refined from config later)
        storage_per_gb_month = float(self.config.get('s3', {}).get('storage_class_rate_per_gb', 0.023))
        head_cost_per_1000 = float(self.config.get('pricing', {}).get('head_per_1000', 0.0004))
        est_head = (len(all_candidates) / 1000.0) * head_cost_per_1000
        est_storage_monthly = gb * storage_per_gb_month
        current_s3_cost = self._get_current_costs()
        if current_s3_cost is not None:
            self.logger.log_info(f"COSTS: current_month_to_date=${current_s3_cost:.2f}")
        self.logger.log_info(
            f"ESTIMATES: to_check={len(all_candidates)} to_upload={len(to_sync)} size_gb={gb:.3f} "
            f"head_cost≈${est_head:.3f} storage_monthly≈${est_storage_monthly:.3f}"
        )
        for line in sample:
            self.logger.log_info(f"FILE: {line}")
        if more:
            self.logger.log_info(more[0])
        # Confirmation to proceed with upload
        if not self._confirm_in_log("Proceed with upload?"):
            self.console.set_summary(["Cancelled by user before upload."])
            self._wait_for_quit()
            self.console.stop()
            return 1
        self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, info if 'info' in locals() else None, 0, 0, status=f"uploading (0/{len(to_sync)})"))
        self.console.set_upload([f"Starting upload of {len(to_sync)} files…"], percent=0)

        # Give user a beat to cancel
        time.sleep(1.0)

        # Upload
        uploaded_done = 0
        bytes_uploaded = 0
        failed_count = 0
        # Precompute age buckets and prepare type counter
        ordered_age = ["<1d","<1w","<1m","<6m","<1y",">=1y"]
        age_counts = Counter()
        for item in to_sync:
            try:
                age_counts[self._bucket_file_age(item.local_path)] += 1
            except Exception:
                age_counts[">=1y"] += 1
        filetype_counts = Counter()
        start = datetime.now()
        def on_file_done(item: FileToSync, ok: bool, size: int):
            nonlocal uploaded_done, bytes_uploaded
            uploaded_done += 1
            if ok:
                bytes_uploaded += size
                ext = (item.local_path.suffix or '').lower() or 'noext'
                filetype_counts[ext] += 1
            else:
                nonlocal failed_count
                failed_count += 1
        def on_upload_progress(done: int, total: int):
            elapsed = (datetime.now() - start).total_seconds()
            mbps = (bytes_uploaded / (1024*1024)) / elapsed if elapsed > 0 else 0.0
            pct = (done / total * 100.0) if total else 0.0
            gb_uploaded = bytes_uploaded / (1024*1024*1024)
            ver_total = self.engine.stats.verifications_total
            ver_pass = self.engine.stats.verifications_passed
            ver_pct = (ver_pass / ver_total * 100.0) if ver_total else 0.0
            top_types = ", ".join(f"{ext}:{cnt}" for ext, cnt in filetype_counts.most_common(3)) or "-"
            age_line = ", ".join(f"{k}:{age_counts.get(k,0)}" for k in ordered_age)
            # Metrics
            workers = getattr(self.engine.config, 'max_concurrent_uploads', 0)
            active_threads = threading.active_count()
            cpu_pct = self._current_cpu_percent()
            mem_pct = self._current_mem_percent()
            net_mbps = self._current_net_bandwidth_mb_s()
            self.console.set_upload([
                f"Files: {done}/{total}   Failed: {failed_count}",
                f"Throughput: {mbps:.2f} MB/s  Uploaded: {gb_uploaded:.2f} GB",
                f"Workers: {workers}  Threads: {active_threads}  CPU: {cpu_pct:.0f}%  Mem: {mem_pct:.0f}%  Net: {net_mbps:.2f} MB/s",
                f"Verify: {ver_pass}/{ver_total} ({ver_pct:.1f}%)",
                f"Top Types: {top_types}",
                f"Age: {age_line}",
            ], percent=pct)
            self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, info if 'info' in locals() else None, done, bytes_uploaded, status=f"uploading ({done}/{total}, failed: {failed_count})"))
        self.engine.upload_files(to_sync, on_file_done=on_file_done, on_progress=on_upload_progress)

        # Summary
        duration = datetime.now() - start
        self.console.set_summary([
            f"Duration: {duration}",
            f"Uploaded files: {uploaded_done}",
            f"Bytes uploaded: {bytes_uploaded:,}",
        ])
        self.console.set_overview(self.build_overview_line(self.local_path, self.bucket_name, info if 'info' in locals() else None, uploaded_done, bytes_uploaded, status="completed"))
        # Hold the screen until user quits
        self._wait_for_quit()
        self.console.stop()
        return 0


def main():
    import argparse
    p = argparse.ArgumentParser(description="Unified full-screen TUI for S3 Sync")
    p.add_argument('--config')
    p.add_argument('--profile')
    p.add_argument('--bucket-name')
    p.add_argument('--local-path')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--no-confirm', action='store_true')
    p.add_argument('--max-concurrent-uploads', type=int, default=0, help='0 = auto-tune based on system')
    p.add_argument('--max-concurrent-checks', type=int, default=0, help='0 = auto-tune based on system')
    args = p.parse_args()

    opts = RunOptions(
        config_file=args.config,
        profile=args.profile,
        bucket_name=args.bucket_name,
        local_path=args.local_path,
        dry_run=args.dry_run,
        no_confirm=args.no_confirm,
        max_concurrent_uploads=args.max_concurrent_uploads,
        max_concurrent_checks=args.max_concurrent_checks,
    )
    app = SyncTUI(opts)
    sys.exit(app.run())


if __name__ == "__main__":
    main()


