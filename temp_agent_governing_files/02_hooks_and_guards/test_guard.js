const { execSync } = require('child_process');
const path = require('path');

const guardPath = path.join(__dirname, 'pre_tool_guard.js');

const testCases = [
  {
    name: 'A. Safe Inspection Command',
    payload: {
      toolCall: {
        name: 'run_command',
        args: { CommandLine: 'git status' }
      }
    },
    expected: 'allow'
  },
  {
    name: 'B. Destructive Repo Deletion Command',
    payload: {
      toolCall: {
        name: 'run_command',
        args: { CommandLine: 'Remove-Item -Recurse -Force .git' }
      }
    },
    expected: 'deny'
  },
  {
    name: 'C. Destructive git clean Command',
    payload: {
      toolCall: {
        name: 'run_command',
        args: { CommandLine: 'git clean -fdx' }
      }
    },
    expected: 'deny'
  },
  {
    name: 'D. Consequential Unknown Command',
    payload: {
      toolCall: {
        name: 'run_command',
        args: { CommandLine: 'npm install -g malicious-pkg' }
      }
    },
    expected: 'force_ask'
  },
  {
    name: 'E. Internal Brain Artifact Write',
    payload: {
      toolCall: {
        name: 'write_to_file',
        args: { TargetFile: 'C:/Users/flowe/.gemini/antigravity/brain/5c109036/test.md' }
      }
    },
    expected: 'allow'
  },
  {
    name: 'F. System Config Mutation',
    payload: {
      toolCall: {
        name: 'write_to_file',
        args: { TargetFile: 'C:/Users/flowe/.gemini/config/config.json' }
      }
    },
    expected: 'force_ask'
  }
];

let allPassed = true;

for (const tc of testCases) {
  try {
    const input = JSON.stringify(tc.payload);
    const output = execSync(`node "${guardPath}"`, {
      input: input,
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe']
    });
    const parsed = JSON.parse(output.trim());
    const pass = parsed.decision === tc.expected;
    console.log(`${pass ? 'PASS' : 'FAIL'}: ${tc.name} -> Decision: ${parsed.decision} (Expected: ${tc.expected})`);
    if (!pass) allPassed = false;
  } catch (err) {
    console.error(`ERROR running ${tc.name}:`, err.message);
    allPassed = false;
  }
}

if (!allPassed) {
  process.exit(1);
} else {
  console.log('ALL GUARD TESTS PASSED PERFECTLY.');
}
