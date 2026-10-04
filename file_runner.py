import unittest
import os

loader = unittest.TestLoader()
test_dir = os.path.join(os.path.dirname(__file__), "tests")
failed_files = []
passed_files = []

for fname in sorted(os.listdir(test_dir)):
    if fname.startswith("test_") and fname.endswith(".py"):
        try:
            suite = loader.loadTestsFromName(f"tests.{fname[:-3]}")
        except Exception as e:
            failed_files.append((fname, f"IMPORT ERROR: {e}"))
            continue
        if suite.countTestCases() == 0:
            continue
        runner = unittest.TextTestRunner(verbosity=0)
        res = runner.run(suite)
        if res.wasSuccessful():
            passed_files.append((fname, res.testsRun))
        else:
            failed_files.append((fname, f"failures={len(res.failures)}, errors={len(res.errors)}"))

print(f"PASSED FILES: {len(passed_files)}")
print(f"FAILED FILES: {len(failed_files)}")
for f, info in failed_files:
    print(f"  {f}: {info}")
