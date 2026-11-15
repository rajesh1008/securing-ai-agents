"""Chapter 27: running code the agent wrote without trusting it.  Pieces:
  Limits           wall seconds, CPU seconds, address space, file size, open files, process count, captured-output cap
  RUNGS            R0 bare (same user, inherited environment), R1 process (scrubbed env, copy of the task directory, rlimits, own session, wall kill),
                   R2 namespaces (bwrap: new user, pid, net, ipc, uts, mount namespaces; read-only /usr; nothing of the host home), R3 narrowed (R2 plus only the named inputs
                   read-only, a size-limited tmpfs for output, no nested user namespaces, capabilities dropped, a seccomp deny-list)
  run_code         run one Python program on a rung and return Result (exit code, capped stdout/stderr, timed_out, truncated, wall_ms, killed_group)
  Manifest         what the host will mount for a task: inputs (read-only), output directory, network (none or named broker), environment names; mount_args() renders it for bwrap
  plan_for         pick the lowest rung that satisfies a code-origin class (own / reviewed / agent-written / third-party), refusing to run when the host cannot provide it
The model is not asked anything here.  The boundary is the kernel's, the manifest is the host's, and a failure to build the boundary is an error, not a downgrade."""
from __future__ import annotations
import ctypes, os, resource, shutil, signal, subprocess, sys, tempfile, threading, time
from dataclasses import dataclass, field

@dataclass
class Limits:
    wall: float = 5.0
    cpu: int = 5
    mem_mb: int = 512
    fsize_mb: int = 20
    nofile: int = 64
    extra_procs: int = 100          # NPROC is per real user: the cap is set relative to the processes the user already has
    out_cap: int = 1_000_000

@dataclass
class Result:
    rung: str; code: int | None; stdout: bytes; stderr: bytes; timed_out: bool; truncated: bool; wall_ms: float; out_total: int = 0
    def text(self) -> str: return self.stdout.decode("utf-8", "replace")

@dataclass
class Manifest:
    inputs: dict = field(default_factory=dict)      # host path -> path in the box, read-only
    output: str = "/out"                            # a size-limited tmpfs; nothing in it survives the run: results leave through stdout, which the host caps
    output_mb: int = 16
    network: str = "none"                           # "none" is the only value this module builds; "broker:<name>" is left to the egress layer (Ch12)
    env: dict = field(default_factory=dict)         # name -> value, explicit; nothing else is passed
    libs: list = field(default_factory=list)        # host directories of third-party Python packages, mounted read-only at the same path and put on PYTHONPATH (R2, R3)

RUNGS = ("R0", "R1", "R2", "R3")
DENY = ["ptrace", "mount", "umount2", "pivot_root", "chroot", "unshare", "setns", "keyctl", "add_key", "request_key", "bpf", "perf_event_open", "userfaultfd",
        "kexec_load", "init_module", "finit_module", "delete_module", "open_by_handle_at", "io_uring_setup", "io_uring_enter", "io_uring_register",
        "process_vm_readv", "process_vm_writev", "reboot", "swapon", "swapoff", "acct", "name_to_handle_at", "move_mount", "open_tree", "fsopen", "fsmount", "fspick"]
LAUNCHER = r'''
import ctypes, os, resource, sys
lim = [int(x) for x in sys.argv[1:7]]
resource.setrlimit(resource.RLIMIT_CPU, (lim[0], lim[0])); resource.setrlimit(resource.RLIMIT_AS, (lim[1] << 20, lim[1] << 20))
resource.setrlimit(resource.RLIMIT_FSIZE, (lim[2] << 20, lim[2] << 20)); resource.setrlimit(resource.RLIMIT_NOFILE, (lim[3], lim[3]))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); resource.setrlimit(resource.RLIMIT_NPROC, (lim[4], lim[4]))
if lim[5]:
    sc = ctypes.CDLL("libseccomp.so.2"); sc.seccomp_init.restype = ctypes.c_void_p; ctx = sc.seccomp_init(ctypes.c_uint32(0x7fff0000))
    EPERM = ctypes.c_uint32(0x00050000 | 1); ENOSYS = ctypes.c_uint32(0x00050000 | 38)
    for name in os.environ["DENY"].split(","):
        n = sc.seccomp_syscall_resolve_name(name.encode())
        if n >= 0: sc.seccomp_rule_add(ctypes.c_void_p(ctx), EPERM, n, 0)
    n = sc.seccomp_syscall_resolve_name(b"clone3"); sc.seccomp_rule_add(ctypes.c_void_p(ctx), ENOSYS, n, 0)
    class Cmp(ctypes.Structure): _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int), ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]
    cmp = Cmp(0, 6, 0x10000000, 0x10000000)   # SCMP_CMP_MASKED_EQ on clone flags: CLONE_NEWUSER
    n = sc.seccomp_syscall_resolve_name(b"clone"); sc.seccomp_rule_add_array(ctypes.c_void_p(ctx), EPERM, n, 1, ctypes.byref(cmp))
    if sc.seccomp_load(ctypes.c_void_p(ctx)) != 0: sys.exit(97)
os.environ.pop("DENY", None)
os.execv("/usr/bin/python3", ["python3", "/code.py"])
'''

def _nproc_count() -> int:
    return int(subprocess.run(["ps", "-u", str(os.getuid()), "-L", "--no-headers"], capture_output=True).stdout.count(b"\n"))

def _capture(p: subprocess.Popen, cap: int | None, deadline: float | None):
    bufs = {"o": bytearray(), "e": bytearray()}; tot = {"o": 0, "e": 0}; trunc = [False]
    def rd(stream, k):
        while True:
            chunk = stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)
            if not chunk: break
            tot[k] += len(chunk)
            if cap is None or len(bufs[k]) < cap: bufs[k] += chunk[: (None if cap is None else cap - len(bufs[k]))]
            else: trunc[0] = True
            if cap is not None and tot[k] > cap * 4:
                trunc[0] = True
                try: os.killpg(p.pid, signal.SIGKILL)
                except Exception: pass
                break
    ts = [threading.Thread(target=rd, args=(p.stdout, "o")), threading.Thread(target=rd, args=(p.stderr, "e"))]
    for t in ts: t.start()
    return bufs, tot, trunc, ts

def run_code(rung: str, code: str, workdir: str, lim: Limits | None = None, env: dict | None = None, manifest: Manifest | None = None, host_env: dict | None = None) -> Result:
    """Run `code` (a Python program) on `rung`.  `workdir` is the task directory on the host.  `env` is what the box is explicitly given (R1-R3);
    `host_env` is the environment R0 inherits (what a process started by the agent runtime would have)."""
    lim = lim or Limits(); env = env or {}; t0 = time.time(); tmp = tempfile.mkdtemp(prefix="sbx_"); timed = False; killed_group = False
    codefile = os.path.join(tmp, "code.py"); open(codefile, "w").write(code)
    if rung == "R0":
        cmd = [sys.executable, codefile]; cwd = workdir; e = dict(host_env if host_env is not None else os.environ); pre = None; wall = 40.0; cap = None
    elif rung == "R1":
        cwd = os.path.join(tmp, "task"); shutil.copytree(workdir, cwd, symlinks=True); e = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", **env}
        base = _nproc_count()
        def pre():
            os.setsid(); resource.setrlimit(resource.RLIMIT_CPU, (lim.cpu, lim.cpu)); resource.setrlimit(resource.RLIMIT_AS, (lim.mem_mb << 20, lim.mem_mb << 20))
            resource.setrlimit(resource.RLIMIT_FSIZE, (lim.fsize_mb << 20, lim.fsize_mb << 20)); resource.setrlimit(resource.RLIMIT_NOFILE, (lim.nofile, lim.nofile))
            resource.setrlimit(resource.RLIMIT_NPROC, (base + lim.extra_procs, base + lim.extra_procs))
        cmd = [sys.executable, codefile]; wall = lim.wall; cap = lim.out_cap
    elif rung in ("R2", "R3"):
        e = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/tmp/home", **env}; cwd = tmp
        launcher = os.path.join(tmp, "launch.py"); open(launcher, "w").write(LAUNCHER)
        a = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
             "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/tmp/home", "--ro-bind", codefile, "/code.py", "--ro-bind", launcher, "/launch.py", "--hostname", "box"]
        for k, v in {**e}.items(): a += ["--setenv", k, v]
        mm = manifest or Manifest()
        if mm.libs:
            for lb in mm.libs: a += ["--ro-bind", lb, lb]
            a += ["--setenv", "PYTHONPATH", ":".join(mm.libs)]
        if rung == "R2":
            a += ["--bind", workdir, "/work", "--chdir", "/work"]
        else:
            man = manifest or Manifest()
            a += ["--unshare-user", "--cap-drop", "ALL", "--disable-userns", "--size", str(man.output_mb << 20), "--tmpfs", man.output, "--perms", "0555", "--dir", "/work"]
            for src, dst in man.inputs.items(): a += ["--ro-bind", src, dst]
            a += ["--chdir", man.output, "--setenv", "DENY", ",".join(DENY)]
            if man.network == "host": a += ["--share-net"]       # deliberately unfiltered: used only to show that an address-level allowance is a channel
        a += ["python3", "/launch.py", str(lim.cpu), str(lim.mem_mb), str(lim.fsize_mb), str(lim.nofile), str(lim.extra_procs), "1" if rung == "R3" else "0"]
        cmd = a; e = dict(os.environ); pre = lambda: os.setsid(); wall = lim.wall; cap = lim.out_cap
    else:
        raise ValueError(rung)
    p = subprocess.Popen(cmd, cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=pre if rung != "R0" else os.setsid)
    bufs, tot, trunc, ts = _capture(p, cap, None)
    try: p.wait(timeout=wall)
    except subprocess.TimeoutExpired:
        timed = True
        try: os.killpg(p.pid, signal.SIGKILL); killed_group = True
        except Exception: p.kill()
        p.wait()
    if rung == "R1":                      # a harness that kills the session when the run ends: a child that called setsid() is no longer in it
        try: os.killpg(p.pid, signal.SIGKILL)
        except Exception: pass
    for t in ts: t.join(timeout=5)
    wall_ms = (time.time() - t0) * 1000
    shutil.rmtree(tmp, ignore_errors=True)
    return Result(rung, p.returncode, bytes(bufs["o"]), bytes(bufs["e"]), timed, trunc[0], wall_ms, tot["o"] + tot["e"])

CLASSES = {"own": "R0", "reviewed": "R1", "agent-written": "R3", "third-party": "R3"}
def available() -> dict:
    """What this host can really provide.  A rung that cannot be built is absent; callers must not substitute a lower one."""
    have = {"R0": True, "R1": True, "R2": False, "R3": False}
    if shutil.which("bwrap"):
        r = subprocess.run(["bwrap", "--unshare-all", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "true"], capture_output=True)
        have["R2"] = have["R3"] = r.returncode == 0
    return have

def plan_for(origin: str, have: dict | None = None) -> str:
    """Lowest rung allowed for an origin class.  Raises when the host cannot provide it: refusing is the contract."""
    have = have or available()
    if origin not in CLASSES: raise KeyError(origin)
    r = CLASSES[origin]
    if not have.get(r): raise RuntimeError(f"rung {r} required for {origin!r} code is not available on this host; refusing to run")
    return r

def manifest_from_declaration(perms: dict, task_dir: str, inbox: dict | None = None) -> Manifest:
    """Chapter 26's declaration is the specification of the box.  fs entries name files under task_dir that are mounted read-only at /work/<name>; env entries are passed
    by name from `inbox` (the host's own values); shell is true only if the declaration says so and then the box still has no way out.  A declared network host cannot be built
    here (an address allowance is a channel: see Lab 3), so it raises and the caller must route the call through the egress layer instead."""
    if perms.get("network"): raise ValueError("declared network access: route through the egress broker (Chapter 12); this module builds boxes with no network")
    inputs = {os.path.join(task_dir, f): "/work/" + f for f in perms.get("fs", [])}
    env = {k: (inbox or {})[k] for k in perms.get("env", []) if k in (inbox or {})}
    return Manifest(inputs=inputs, network="none", env=env)

def box_covers(manifest: Manifest, observed: dict) -> list[str]:
    """Observed capabilities (from supplychain.observed_permissions) that the box does not provide.  An empty list means the box is at least as tight as the code's need."""
    gaps = []
    if observed.get("network"): gaps.append("network:" + ",".join(sorted(observed["network"])))
    for k in observed.get("env", []):
        if k not in manifest.env: gaps.append("env:" + k)
    return gaps
