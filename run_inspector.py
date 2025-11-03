# run_inspector.py
import os, re, sys, shlex, subprocess, webbrowser, shutil

REQUIRED_NODE_MAJOR = 22
CANDIDATE_SERVER_SCRIPTS = [
    os.path.join("Database", "mcp_data_characters.py"),         # fallback
]

def which(cmd: str) -> str | None:
    return shutil.which(cmd)

def find_server_script() -> str:
    for p in CANDIDATE_SERVER_SCRIPTS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"Could not find server script. Tried: {', '.join(CANDIDATE_SERVER_SCRIPTS)}")

def check_node_ok() -> tuple[bool,str]:
    node = which("node")
    npm  = which("npm")
    if not node or not npm:
        return False, "Node and/or npm not found in PATH"
    try:
        out = subprocess.check_output([node, "-v"], text=True).strip()  # e.g. v22.8.0
        m = re.match(r"v(\d+)", out)
        if not m or int(m.group(1)) < REQUIRED_NODE_MAJOR:
            return False, f"Node {REQUIRED_NODE_MAJOR}+ required (found {out})"
    except Exception as e:
        return False, f"Failed to run 'node -v': {e}"
    return True, ""

def build_inspector_cmd(server_script: str) -> list[str]:
    npx_path = which("npx")
    if npx_path:
        return [npx_path, "-y", "@modelcontextprotocol/inspector", "--", "python", server_script]
    npm_path = which("npm")
    if npm_path:
        return [npm_path, "exec", "-y", "@modelcontextprotocol/inspector", "--", "python", server_script]
    raise FileNotFoundError("Neither 'npx' nor 'npm' found in PATH")

def main():
    server_script = find_server_script()

    ok, msg = check_node_ok()
    if not ok:
        print("ERROR:", msg, file=sys.stderr)
        print("Install Node 22+ and open a NEW terminal so PATH updates.", file=sys.stderr)
        sys.exit(1)

    # Ensure PG_DSN (localhost since MCP server runs on host)
    os.environ.setdefault("PG_DSN", "postgresql://postgres:postgres@localhost:5432/dmai")

    # Make 'python' resolve to THIS interpreter (your venv) inside Inspector
    py_dir = os.path.dirname(sys.executable)
    os.environ["PATH"] = py_dir + os.pathsep + os.environ.get("PATH", "")

    argv = build_inspector_cmd(server_script)

    print("Launching MCP Inspector…")
    print(" Command:", " ".join(shlex.quote(a) for a in argv))
    print(" Working dir:", os.getcwd())
    print(" Server:", server_script)
    print(" PG_DSN:", os.environ["PG_DSN"])
    print()

    # Read Inspector output as UTF-8 so Windows consoles don’t choke on emojis/UTF-8
    url_re = re.compile(r"http://localhost:\d+/\?MCP_PROXY_AUTH_TOKEN=[A-Za-z0-9]+")
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",     # <-- important
        errors="replace",     # <-- don’t crash on odd bytes
        bufsize=1,
        universal_newlines=True,
        shell=False,
    )

    opened = False
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            if not opened:
                m = url_re.search(line)
                if m:
                    url = m.group(0)
                    try:
                        webbrowser.open(url)
                        print(f"\nOpened MCP Inspector in your browser:\n  {url}\n")
                    except Exception as e:
                        print(f"\nCopy this URL into your browser:\n  {url}\n(auto-open failed: {e})\n")
                    opened = True
        proc.wait()
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        sys.exit(130)

if __name__ == "__main__":
    main()
