import unittest

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    with open("/tmp/diag_result.txt", "w") as out:
        out.write(f"TOTAL RAN: {result.testsRun}\n")
        out.write(f"FAILURES: {len(result.failures)}\n")
        for f in result.failures:
            out.write(f"FAIL IN: {f[0]}\n{f[1]}\n")
        out.write(f"ERRORS: {len(result.errors)}\n")
        for e in result.errors:
            out.write(f"ERROR IN: {e[0]}\n{e[1]}\n")
    print("DIAGNOSTIC FINISHED AND WRITTEN TO /tmp/diag_result.txt", flush=True)
