"""Shared fixture for the Chapter 27 labs: a fake developer/host world with canaries, and two host listeners (TCP on loopback, a unix socket).
Every secret here is a made-up canary string; nothing real is stored.  The host environment given to R0 carries a fake API key canary."""
import os, subprocess, socket, threading, tempfile, shutil, csv, random
CAN = dict(home="CANARY-HOME-7f3a91", env="CANARY-ENV-b20c4d", tenant="CANARY-TENANTB-5e118a")
STAGE2 = "open('stage2_ran','w').write('yes')\n"

class World:
    def __init__(self, base=None):
        self.root = base or tempfile.mkdtemp(prefix="ch27world_")
        self.home = os.path.join(self.root, "home"); self.task = os.path.join(self.root, "task"); self.tenb = os.path.join(self.root, "tenants", "B")
        for d in (os.path.join(self.home, ".aws"), self.task, self.tenb, os.path.join(self.root, "run")): os.makedirs(d, exist_ok=True)
        open(os.path.join(self.home, ".aws", "credentials"), "w").write(f"[default]\naws_secret_access_key = {CAN['home']}\n")
        open(os.path.join(self.tenb, "invoices.csv"), "w").write(f"id,customer,amount\nB-1,Other Bakery,{CAN['tenant']}\n")
        rnd = random.Random(7); rows = [("id", "customer", "amount", "note")]
        for i in range(24): rows.append((f"INV-{3000+i}", rnd.choice(["Lone Star Paper", "Riverside Office", "Hill Foods", "Cedar Mill"]), round(rnd.uniform(40, 900), 2), ""))
        with open(os.path.join(self.task, "invoices.csv"), "w", newline="") as f: csv.writer(f).writerows(rows)
        self.host_env = {**os.environ, "HOME": self.home, "FAKE_API_KEY": CAN["env"]}
        self.neighbour = subprocess.Popen(['sleep', '3600'], env={**os.environ, 'NEIGHBOUR_KEY': CAN['env']})   # another process of the same user (another agent, an MCP server) holding a secret
        self.hits = []; self.served = []; self._stop = False
        self.tcp = socket.socket(); self.tcp.bind(("127.0.0.1", 0)); self.tcp.listen(32); self.port = self.tcp.getsockname()[1]
        self.sockpath = os.path.join(self.root, "run", "docker.sock"); self.us = socket.socket(socket.AF_UNIX); self.us.bind(self.sockpath); self.us.listen(8)
        threading.Thread(target=self._loop, args=(self.tcp, "tcp"), daemon=True).start(); threading.Thread(target=self._loop, args=(self.us, "unix"), daemon=True).start()
    def _loop(self, srv, kind):
        srv.settimeout(0.2)
        while not self._stop:
            try: c, _ = srv.accept()
            except socket.timeout: continue
            except OSError: return
            try:
                c.settimeout(0.5); buf = b""
                try:
                    while len(buf) < 65536:
                        ch = c.recv(8192)
                        if not ch: break
                        buf += ch
                        if b"\r\n\r\n" in buf and b"Content-Length" not in buf: break
                except socket.timeout: pass
                data = buf.decode("utf-8", "replace"); self.hits.append((kind, data[:8000]))
                if data.startswith("GET /stage2"): self.served.append(1); c.sendall(("HTTP/1.0 200 OK\r\n\r\n" + STAGE2).encode())
                else: c.sendall(b"HTTP/1.0 200 OK\r\n\r\nok")
            except Exception: pass
            finally: c.close()
    def reset(self):
        self.hits.clear(); self.served.clear()
        for f in ("persist_marker", "stage2_ran", "big.bin", "report_link"):
            p = os.path.join(self.task, f)
            if os.path.lexists(p): os.remove(p)
        p = os.path.join(self.home, ".bashrc_pwn")
        if os.path.exists(p): os.remove(p)
    def close(self): self.neighbour.kill(); self._stop = True; self.tcp.close(); self.us.close(); shutil.rmtree(self.root, ignore_errors=True)
