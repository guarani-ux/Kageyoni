/**
 * Antigravity PreToolUse Mechanical Guard
 * Enforces the 3-Tier Reversibility Matrix for Kageyoni & Software 3.0
 */

const fs = require('fs');
const path = require('path');

const AUDIT_LOG = 'C:/Users/flowe/.gemini/antigravity/scratch/guard_audit.log';

function readStdin() {
  try { return fs.readFileSync(0, 'utf-8'); } catch (e) { return ''; }
}

function appendAudit(entry) {
  try {
    fs.appendFileSync(AUDIT_LOG, JSON.stringify(entry) + '\n', 'utf-8');
  } catch (e) {}
}

const PROTECTED_CONFIG_PATHS = [
  'pre_tool_guard.js',
  'agents.md',
  'gemini.md',
  'hooks.json',
  '.env',
  '.git/config',
  '.git/hooks'
];

const TIER_1_DESTRUCTIVE_PATTERNS = [
  /\b(?:rmdir|Remove-Item|rm|del|unlink)\b/i,
  /\bgit\s+(?:clean\s+-[a-zA-Z]*[fF]|reset\s+--hard|restore\s+\.|checkout\s+--\s+\.|branch\s+-[a-zA-Z]*[dD])\b/i,
  /\bformat\s+[a-zA-Z]:/i,
  /\bdiskpart\b/i,
  /\bDROP\s+(?:DATABASE|SCHEMA|TABLE)\b/i,
  /\b(?:pip\s+install|npm\s+(?:install|i|uninstall|remove)|poetry\s+add)\b/i
];

const TIER_2_IRREVERSIBLE_PATTERNS = [
  /\bgit\s+push\b/i,
  /\bgh\s+pr\s+merge\b/i,
  /\bgh\s+release\b/i,
  /\bnpm\s+publish\b/i,
  /\btwine\s+upload\b/i,
  /\bterraform\s+apply\b/i,
  /\bkubectl\s+(?:apply|delete|create)\b/i
];

const TIER_0_SAFE_COMMANDS = [
  /^git\s+(?:status|diff|log|branch(\s+-[a-ce-z]+)?)(\s+.*)?$/i,
  /^python\s+(?:-m\s+unittest|-m\s+pytest|--version)(\s+.*)?$/i,
  /^pytest(\s+.*)?$/i,
  /^(?:dir|ls|Get-ChildItem|Get-Content|cat|type|Select-String|findstr|grep|pwd|Get-Location|Test-Path)(\s+.*)?$/i,
  /^(?:node\s+-v|python\s+--version|pwsh\s+-v)$/i
];

function containsChainedExecution(cmd) {
  return /[;&|`]|(\$\()/.test(cmd);
}

function evaluate(payload) {
  if (!payload || !payload.toolCall) return { decision: 'allow' };

  const rawTool = payload.toolCall.name || '';
  const args = payload.toolCall.args || {};

  let tool = rawTool;
  if (tool === 'command') tool = 'run_command';
  if (tool === 'write_file') tool = 'write_to_file';
  if (tool === 'edit_file') tool = 'replace_file_content';

  // 1. Terminal Execution Gate
  if (tool === 'run_command') {
    const cmd = (args.CommandLine || args.command || args.cmd || '').trim();

    // Check compound chaining injection
    if (containsChainedExecution(cmd)) {
      return {
        decision: 'force_ask',
        reason: `CHAINED_EXECUTION: Compound shell operators require Tier 1 human confirmation: "${cmd}"`
      };
    }

    // Check Tier 2 (Irreversible External Gate)
    for (const pattern of TIER_2_IRREVERSIBLE_PATTERNS) {
      if (pattern.test(cmd)) {
        return {
          decision: 'force_ask',
          reason: `TIER_2_GATE: Irreversible remote or external mutation requires sovereign human confirmation: "${cmd}"`
        };
      }
    }

    // Check Tier 1 (Local Destructive Gate)
    for (const pattern of TIER_1_DESTRUCTIVE_PATTERNS) {
      if (pattern.test(cmd)) {
        return {
          decision: 'force_ask',
          reason: `TIER_1_GATE: Potentially destructive local action requires human confirmation: "${cmd}"`
        };
      }
    }

    // Check interactive shell escape flags (Pytest Trojan mitigation)
    if (/\b(?:--pdb|--capture=no)\b/i.test(cmd)) {
      return {
        decision: 'force_ask',
        reason: `INTERACTIVE_FLAG_GATE: Shell escape flag requires confirmation: "${cmd}"`
      };
    }

    // Check Tier 0 Autonomous Fast Loop Whitelist
    for (const pattern of TIER_0_SAFE_COMMANDS) {
      if (pattern.test(cmd)) {
        return { decision: 'allow', reason: `TIER_0_FAST_LOOP: Whitelisted autonomous verification: "${cmd}"` };
      }
    }

    // Commands executing strictly inside internal scratch sandbox
    const cwd = (args.Cwd || args.cwd || '').replace(/\\/g, '/').toLowerCase();
    if (cwd.includes('/scratch')) {
      return { decision: 'allow', reason: `TIER_0_SANDBOX: Command in scratch sandbox: "${cmd}"` };
    }

    // Default: Unclassified commands default to Tier 1 human authorization
    return {
      decision: 'force_ask',
      reason: `UNCLASSIFIED_COMMAND: Command requires Tier 1 human authorization: "${cmd}"`
    };
  }

  // 2. File Mutation Gate
  if (tool === 'write_to_file' || tool === 'replace_file_content') {
    const rawTarget = args.TargetFile || args.file_path || args.path || args.AbsolutePath || '';
    const target = rawTarget.toLowerCase().replace(/\\/g, '/');

    // Protected system configuration files
    if (PROTECTED_CONFIG_PATHS.some(p => target.endsWith(p) || target.includes('/' + p))) {
      return {
        decision: 'force_ask',
        reason: `PROTECTED_CONFIG_GATE: Direct mutation of system configuration requires human confirmation: ${rawTarget}`
      };
    }

    // Destructive truncation check for write_to_file
    if (tool === 'write_to_file') {
      const content = args.CodeContent || args.content || '';
      if (!content || content.trim().length === 0) {
        return {
          decision: 'force_ask',
          reason: `DESTRUCTIVE_TRUNCATION: Emptying a file requires Tier 1 confirmation: ${rawTarget}`
        };
      }
    }

    // Workspace & Internal Sandbox writes (Tier 0 Fast Loop)
    if (
      target.startsWith('c:/kageyoni/') ||
      target.includes('/.gemini/antigravity/brain/') ||
      target.includes('/scratch/')
    ) {
      return { decision: 'allow', reason: `TIER_0_FAST_LOOP: Non-destructive workspace edit permitted: ${rawTarget}` };
    }

    // External mutations outside workspace
    return {
      decision: 'force_ask',
      reason: `EXTERNAL_MUTATION_GATE: File target outside workspace requires human confirmation: ${rawTarget}`
    };
  }

  // 3. Read-only Inspections (Tier 0)
  return { decision: 'allow' };
}

function main() {
  const raw = readStdin();
  let payload = {};
  try { payload = JSON.parse(raw); } catch (e) {}

  const result = evaluate(payload);
  appendAudit({
    timestamp: new Date().toISOString(),
    rawTool: payload.toolCall ? payload.toolCall.name : null,
    stepIdx: payload.stepIdx,
    args: payload.toolCall ? payload.toolCall.args : null,
    result
  });

  process.stdout.write(JSON.stringify(result));
  process.exit(0);
}

main();
