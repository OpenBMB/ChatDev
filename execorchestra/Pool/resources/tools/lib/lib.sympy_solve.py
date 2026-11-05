from _liblib import a, err, ok
import sympy


try:
    raw = a(1).strip()
    if "=" in raw and not raw.lstrip().startswith("Eq("):
        lhs, rhs = raw.split("=", 1)
        expression = sympy.sympify(lhs) - sympy.sympify(rhs)
    else:
        expression = sympy.sympify(raw)
    ok(
        "lib.sympy_solve",
        input=raw,
        simplified=str(sympy.simplify(expression)),
        solved=str(sympy.solve(expression)),
    )
except Exception as ex:
    err("lib.sympy_solve", str(ex))
