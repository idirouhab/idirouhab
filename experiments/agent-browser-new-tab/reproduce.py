#!/usr/bin/env python3
"""Local regression reproduction for agent-browser #1777. No account or external page."""
import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
VERSIONS = {
    "0.36.0": {"sha256": "b2106ab39db0838e7b1772f7f26f760518de56d09053150c56f9dddf15af997d", "tag_commit": "eb05921bad874cd2a1b4fa5d1149f1ed26576cae"},
    "0.37.0": {"sha256": "da5a2b4ef7be8ba279b1258c542c33877f480b1951d0d94de607fc1528edd380", "tag_commit": "471ab3852b47b98847f1d9c855c272bb62d0d50b"},
}
UA = "ab-tab-new-test/1.0"
HEADER = "global"

def utc():
    return datetime.now(timezone.utc).isoformat()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chromium-path", type=Path, required=True, help="Absolute path to a separate test Chromium executable; never a personal browser profile")
    parser.add_argument("--download", action="store_true", help="Download only the two pinned official binaries before verification")
    parser.add_argument("--seconds", type=int, default=600, help="Total execution deadline, including cleanup reserve")
    args = parser.parse_args()
    CHROMIUM = args.chromium_path.expanduser().resolve()
    started = time.monotonic()
    deadline = started + min(max(args.seconds, 60), 900)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / ("run-" + run_id)
    run_dir.mkdir()
    sockets = Path(tempfile.mkdtemp(prefix="ab1777-", dir="/private/tmp"))
    config = run_dir / "config.json"
    config.write_text("{}\n")
    results = {"started_at": utc(), "scope": "Two official CLI releases, one isolated cached Chromium, loopback-only test pages", "chromium": str(CHROMIUM), "run_dir": str(run_dir), "socket_dir": str(sockets), "commands": [], "requests": [], "versions": {}, "cleanup": [], "status": "running"}
    result_path = run_dir / "results.json"
    requests_lock = threading.Lock()
    owned_daemons = {}
    contexts = []
    server = None
    server_thread = None
    # Retain original HOME unchanged. No agent-browser/proxy/provider environment survives.
    child_env = {key: os.environ[key] for key in ("HOME", "USER", "LOGNAME", "PATH", "TMPDIR", "LANG") if key in os.environ}
    child_env["AGENT_BROWSER_SOCKET_DIR"] = str(sockets)
    child_env["NO_COLOR"] = "1"

    def save():
        result_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    def command(argv, timeout=25, cleanup=False):
        remaining = deadline - time.monotonic()
        if not cleanup and remaining < 35:
            raise TimeoutError("Execution deadline reached; reserving time for cleanup")
        limit = min(timeout, max(1, remaining)) if not cleanup else min(timeout, 10)
        event = {"at": utc(), "argv": [str(a) for a in argv]}
        process = subprocess.Popen(event["argv"], cwd=str(run_dir), env=child_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        event["pid"] = process.pid
        try:
            out, err = process.communicate(timeout=limit)
            event.update(returncode=process.returncode, stdout=out, stderr=err)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                out, err = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                out, err = process.communicate()
            event.update(returncode=process.returncode, stdout=out, stderr=err, timeout=True)
        results["commands"].append(event)
        save()
        return event

    def remember_daemon(context):
        path = sockets / (context["session"] + ".pid")
        if path.exists():
            try:
                pid = int(path.read_text().strip())
                if pid > 1:
                    owned_daemons[pid] = str(context["binary"])
            except (ValueError, OSError):
                pass

    def ab(context, *argv, cleanup=False):
        fixed = [context["binary"], "--config", config, "--session", context["session"], "--executable-path", CHROMIUM, "--profile", context["profile"], "--headed", "false", "--auto-connect", "false", "--no-webmcp", "--idle-timeout", "60s", "--user-agent", UA]
        outcome = command(fixed + list(argv), cleanup=cleanup)
        remember_daemon(context)
        if outcome["returncode"] != 0 and not cleanup:
            raise RuntimeError("CLI failed: " + json.dumps({"version": context["version"], "argv": list(argv), "returncode": outcome["returncode"], "stderr": outcome.get("stderr", "")}))
        return outcome

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            payload = {"path": self.path, "headers": {"user-agent": self.headers.get("User-Agent"), "x-global": self.headers.get("X-Global")}}
            with requests_lock:
                record = {"sequence": len(results["requests"]) + 1, "at": utc(), **payload}
                results["requests"].append(record)
                with (run_dir / "requests.jsonl").open("a") as log:
                    log.write(json.dumps(record) + "\n")
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *unused):
            pass

    try:
        if not CHROMIUM.is_file():
            raise RuntimeError("Pinned cached Chromium executable is unavailable")
        for version, metadata in VERSIONS.items():
            binary = ROOT / ("agent-browser-v" + version + "-darwin-arm64")
            url = "https://github.com/vercel-labs/agent-browser/releases/download/v" + version + "/agent-browser-darwin-arm64"
            if args.download and not binary.exists():
                event = command(["/usr/bin/curl", "--fail", "--location", "--proto", "=https", "--tlsv1.2", "--max-time", "90", "--output", binary, url], timeout=95)
                if event["returncode"] != 0:
                    raise RuntimeError("Official binary download failed")
            if not binary.is_file():
                raise RuntimeError("Required binary missing: " + str(binary))
            actual = digest(binary)
            results["versions"][version] = {"source_url": url, **metadata, "actual_sha256": actual, "verified": actual == metadata["sha256"]}
            save()
            if actual != metadata["sha256"]:
                raise RuntimeError("Binary SHA-256 mismatch for " + version)
            binary.chmod(binary.stat().st_mode | 0o100)
            profile = run_dir / ("profile-v" + version)
            profile.mkdir()
            context = {"version": version, "binary": binary, "profile": profile, "session": "v" + version.replace(".", "")}
            contexts.append(context)
            version_result = command([binary, "--version"])
            results["versions"][version]["reported_version"] = version_result["stdout"].strip()
            if version_result["returncode"] != 0 or version not in version_result["stdout"]:
                raise RuntimeError("Version check failed; do not bypass operating-system protections")

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        origin = "http://127.0.0.1:" + str(server.server_port)
        results["origin"] = origin
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        for context in contexts:
            prefix = "/" + context["session"]
            try:
                ab(context, "open", origin + prefix + "/start")
                ab(context, "set", "headers", '{"X-Global":"global"}')
                ab(context, "open", origin + prefix + "/baseline")
                ab(context, "wait", "--load", "load")
                ab(context, "eval", "JSON.parse(document.body.innerText).headers")
                ab(context, "tab", "new", origin + prefix + "/first-new-tab")
                ab(context, "wait", "--load", "load")
                ab(context, "eval", "JSON.parse(document.body.innerText).headers")
            finally:
                context["close_attempted"] = True
                close_result = ab(context, "close", cleanup=True)
                results["cleanup"].append({"session": context["session"], "close_returncode": close_result["returncode"]})
            with requests_lock:
                first = {}
                for suffix in ("baseline", "first-new-tab"):
                    first[suffix] = next((r for r in results["requests"] if r["path"] == prefix + "/" + suffix), None)
            if any(value is None for value in first.values()):
                raise RuntimeError("Expected first GET absent: " + context["version"])
            results["versions"][context["version"]]["first_requests"] = first
            baseline = first["baseline"]["headers"]
            probe = first["first-new-tab"]["headers"]
            results["versions"][context["version"]]["baseline_valid"] = baseline == {"user-agent": UA, "x-global": HEADER}
            results["versions"][context["version"]]["new_tab_inherits_both"] = probe == {"user-agent": UA, "x-global": HEADER}
            save()
        before = results["versions"]["0.36.0"]
        after = results["versions"]["0.37.0"]
        results["regression_reproduced"] = before["baseline_valid"] and after["baseline_valid"] and not before["new_tab_inherits_both"] and after["new_tab_inherits_both"]
        results["status"] = "reproduced" if results["regression_reproduced"] else "observed_different_result"
    except Exception as exc:
        results["status"] = "failed"
        results["error"] = str(exc)
    finally:
        # Close only named sessions whose own PID files were created under our dedicated socket dir.
        for context in contexts:
            if not context.get("close_attempted") and (sockets / (context["session"] + ".pid")).exists():
                try:
                    event = ab(context, "close", cleanup=True)
                    results["cleanup"].append({"session": context["session"], "final_close_returncode": event["returncode"]})
                except Exception as exc:
                    results["cleanup"].append({"session": context["session"], "error": str(exc)})
        # If a daemon remains, verify its command references our local versioned binary before SIGTERM.
        for pid, binary in owned_daemons.items():
            check = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
            if check.returncode == 0 and binary in check.stdout:
                os.kill(pid, signal.SIGTERM)
                results["cleanup"].append({"owned_daemon_pid": pid, "action": "SIGTERM after verified local binary"})
        # A stale PID file must never trigger a second CLI close, which can start a new daemon.
        # Inspect only processes carrying this run's absolute fresh profile path or dedicated binary.
        def remaining_owned_processes():
            scan = subprocess.run(["/bin/ps", "-axo", "pid=,command="], capture_output=True, text=True)
            if scan.returncode != 0:
                return None
            matches = []
            for line in scan.stdout.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) != 2:
                    continue
                pid, cmd = int(parts[0]), parts[1]
                own_browser = any("--user-data-dir=" + str(c["profile"]) in cmd for c in contexts)
                own_daemon = pid in owned_daemons and owned_daemons[pid] in cmd
                if pid != os.getpid() and (own_browser or own_daemon):
                    matches.append({"pid": pid, "command": cmd})
            return matches
        residual = remaining_owned_processes()
        for item in residual or []:
            try:
                os.kill(item["pid"], signal.SIGTERM)
                results["cleanup"].append({"pid": item["pid"], "action": "SIGTERM after own profile or daemon verification"})
            except ProcessLookupError:
                pass
        if residual:
            time.sleep(0.5)
        results["remaining_owned_processes"] = remaining_owned_processes()
        if server:
            server.shutdown()
            server.server_close()
        if server_thread:
            server_thread.join(timeout=2)
        results["finished_at"] = utc()
        results["duration_seconds"] = round(time.monotonic() - started, 3)
        results["socket_directory_remaining_files"] = [p.name for p in sockets.iterdir()] if sockets.exists() else []
        save()
        (ROOT / "latest-results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"status": results["status"], "error": results.get("error"), "result_path": str(result_path), "duration_seconds": results["duration_seconds"]}, ensure_ascii=False))
    return 0 if results["status"] == "reproduced" else 1

if __name__ == "__main__":
    raise SystemExit(main())
