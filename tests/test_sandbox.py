import os, tempfile, shutil
import pytest
from bulwark.sandbox import *
HAVE = available()
needs = pytest.mark.skipif(not HAVE["R3"], reason="bwrap not usable here")
def task():
    d = tempfile.mkdtemp(); open(os.path.join(d, "a.txt"), "w").write("hello"); return d
def test_r0_inherits_environment_and_r1_scrubs_it():
    d = task(); code = "import os;print(os.environ.get('SECRET_X'))"
    assert run_code("R0", code, d, host_env={**os.environ, "SECRET_X": "s"}).text().strip() == "s"
    assert run_code("R1", code, d, host_env={"SECRET_X": "s"}).text().strip() == "None"
def test_r1_copies_task_directory():
    d = task(); run_code("R1", "open('new.txt','w').write('x')", d); assert not os.path.exists(os.path.join(d, "new.txt"))
def test_wall_timeout_kills_and_reports():
    d = task(); r = run_code("R1", "while True: pass", d, Limits(wall=1, cpu=30)); assert r.timed_out or r.code not in (0, None)
def test_output_cap_truncates():
    d = task(); r = run_code("R1", "print('x'*5000000)", d, Limits(out_cap=1000)); assert len(r.stdout) <= 1000 and r.truncated
@needs
def test_r2_hides_host_home_and_network():
    d = task(); h = tempfile.mkdtemp(); open(os.path.join(h, "k"), "w").write("S")
    r = run_code("R2", f"import os,socket\nprint(os.path.exists({h!r}+'/k'))\ntry: socket.create_connection(('127.0.0.1',9),1)\nexcept OSError as e: print('neterr')", d); assert r.text().split() == ["False", "neterr"]
@needs
def test_r3_mounts_only_named_inputs_read_only():
    d = task(); open(os.path.join(d, "other.txt"), "w").write("o")
    r = run_code("R3", "import os\nprint(sorted(os.listdir('/work')))\ntry: open('/work/a.txt','w')\nexcept OSError: print('ro')", d, manifest=Manifest(inputs={os.path.join(d, "a.txt"): "/work/a.txt"}))
    assert r.text().split("\n")[:2] == ["['a.txt']", "ro"]
@needs
def test_r3_blocks_nested_userns_r2_does_not():
    d = task(); code = "import ctypes;print(ctypes.CDLL(None).unshare(0x10000000))"
    assert run_code("R2", code, d).text().strip() == "0" and run_code("R3", code, d).text().strip() == "-1"
@needs
def test_r2_kills_leftover_processes():
    d = task(); code = "import os\nif os.fork()==0:\n    os.setsid()\n    os.execv('/usr/bin/sleep',['sleep-T27A','6'])\nprint('x')"
    import subprocess, time
    run_code("R2", code, d); time.sleep(0.5); assert subprocess.run(["pgrep", "-f", "sleep-T27A"], capture_output=True).stdout.strip() == b""
@needs
def test_process_count_is_capped_in_boxes():
    d = task(); code = "import subprocess\nn=0\nps=[]\nfor i in range(300):\n    try: ps.append(subprocess.Popen(['sleep','2']));n+=1\n    except OSError: break\nprint(n)"
    assert int(run_code("R3", code, d, Limits(extra_procs=50)).text()) < 60
def test_plan_for_refuses_instead_of_downgrading():
    assert plan_for("agent-written", {"R3": True}) == "R3"
    with pytest.raises(RuntimeError): plan_for("agent-written", {"R0": True, "R1": True, "R3": False})
    with pytest.raises(KeyError): plan_for("mystery", {"R3": True})
def test_manifest_from_declaration_and_gaps():
    m = manifest_from_declaration({"network": [], "fs": ["invoices.csv"], "env": ["TZ"]}, "/t", {"TZ": "UTC", "SECRET": "s"})
    assert m.inputs == {"/t/invoices.csv": "/work/invoices.csv"} and m.env == {"TZ": "UTC"} and m.network == "none"
    with pytest.raises(ValueError): manifest_from_declaration({"network": ["api.example"]}, "/t")
    assert box_covers(m, {"network": ["x.example"], "env": ["TZ", "HOME"]}) == ["network:x.example", "env:HOME"]
@needs
def test_libs_are_mounted_read_only_and_importable():
    d = task(); lib = tempfile.mkdtemp(); open(os.path.join(lib, "mylib27.py"), "w").write("X = 7\n")
    assert run_code("R3", "import mylib27;print(mylib27.X)", d, manifest=Manifest(libs=[lib])).text().strip() == "7"
    assert "ModuleNotFoundError" in run_code("R3", "import mylib27", d, manifest=Manifest()).stderr.decode()
