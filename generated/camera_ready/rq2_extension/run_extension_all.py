"""Combined runner: executes p1 then p2 in the same namespace."""
exec(open(__file__.replace("run_extension_all.py","run_extension_p1.py"), encoding="utf-8").read())
exec(open(__file__.replace("run_extension_all.py","run_extension_p2.py"), encoding="utf-8").read())
