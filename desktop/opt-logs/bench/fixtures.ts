// 10 representative log shapes the optimizer is judged against. Mix of:
// npm test output, cargo build, kubectl logs, stack traces, generic noise.

export interface Fixture {
  name: string;
  text: string;
  /** Human-marked "what the agent actually needs from this dump." Bench
   *  asserts the summarizer keeps these lines. */
  expected_keep: string[];
}

function repeat(line: string, n: number): string {
  return new Array(n).fill(line).join("\n");
}

export const FIXTURES: Fixture[] = [
  {
    name: "npm-test-pass",
    text:
      "> jest\n" +
      repeat("PASS  src/utils/format.test.ts", 200) +
      "\nTest Suites: 200 passed, 200 total\n" +
      "Tests:       2400 passed, 2400 total\n",
    expected_keep: ["Test Suites: 200 passed", "Tests:"],
  },
  {
    name: "npm-test-fail",
    text:
      "> jest\n" +
      repeat("PASS  src/utils/format.test.ts", 150) +
      "\nFAIL src/api/auth.test.ts\n" +
      "  AuthService › verifyToken\n" +
      "    Error: token expired\n" +
      "      at AuthService.verifyToken (src/api/auth.ts:42:9)\n" +
      "      at Object.<anonymous> (src/api/auth.test.ts:12:30)\n" +
      "Test Suites: 1 failed, 150 passed, 151 total\n",
    expected_keep: ["FAIL src/api/auth.test.ts", "Error: token expired", "auth.ts:42"],
  },
  {
    name: "cargo-build-warn",
    text:
      repeat("   Compiling crate-name v0.1.0", 60) +
      "\nwarning: unused variable: `foo`\n" +
      "  --> src/main.rs:10:9\n" +
      "   |\n" +
      "10 |     let foo = 1;\n" +
      "   |         ^^^ help: prefix with underscore: `_foo`\n" +
      "    Finished dev [unoptimized + debuginfo] target(s) in 18.42s\n",
    expected_keep: ["warning: unused variable", "Finished dev"],
  },
  {
    name: "kubectl-logs-pod-crash",
    text:
      repeat("INFO worker-pool: drained 1 task", 400) +
      "\nERROR worker-pool: panic in handler: nil pointer dereference\n" +
      "  goroutine 31 [running]:\n" +
      "  main.handle(0xc0000a8000)\n" +
      "    /app/handler.go:142 +0x1f8\n" +
      "  created by main.main\n" +
      "    /app/main.go:24 +0x65\n" +
      "INFO worker-pool: restarting\n",
    expected_keep: ["ERROR", "nil pointer dereference", "handler.go:142"],
  },
  {
    name: "python-traceback",
    text:
      repeat("INFO __main__: loading config", 100) +
      "\nTraceback (most recent call last):\n" +
      '  File "/app/cli.py", line 33, in <module>\n' +
      "    main()\n" +
      '  File "/app/cli.py", line 21, in main\n' +
      "    handler(args)\n" +
      "KeyError: 'database_url'\n",
    expected_keep: ["Traceback", "KeyError: 'database_url'", "/app/cli.py", "line 33"],
  },
  {
    name: "long-info-only",
    text: repeat("INFO ready", 5000),
    expected_keep: [],
  },
  {
    name: "tsc-noEmit",
    text:
      repeat("src/foo.ts:1:1 - no errors found.", 1) +
      repeat("\nsrc/bar.ts:1:1 - no errors found.", 100) +
      "\nsrc/baz.ts(42,5): error TS2345: Argument of type 'string' is not assignable to parameter of type 'number'.\n",
    expected_keep: ["error TS2345", "baz.ts(42"],
  },
  {
    name: "k8s-events-mixed",
    text:
      repeat("normal Pulling: pulling image \"app:latest\"", 150) +
      "\nWarning Unhealthy: Liveness probe failed: Get http://10.0.0.1:8080/healthz: dial tcp: i/o timeout\n" +
      "Normal Killing: Stopping container app\n" +
      repeat("\nnormal Created: Created container app", 200),
    expected_keep: ["Warning Unhealthy", "Liveness probe failed"],
  },
  {
    name: "stack-only",
    text:
      "Exception in thread \"main\" java.lang.NullPointerException\n" +
      repeat("    at com.example.Foo.bar(Foo.java:42)", 30),
    expected_keep: ["NullPointerException"],
  },
  {
    name: "git-merge-conflict",
    text:
      "Auto-merging src/index.ts\n" +
      "CONFLICT (content): Merge conflict in src/index.ts\n" +
      "Auto-merging README.md\n" +
      "Automatic merge failed; fix conflicts and then commit the result.\n",
    expected_keep: ["CONFLICT", "Automatic merge failed"],
  },
];
