"""
Shared helpers for idea-mcp enforcement hooks.

Provides:
  is_code_symbol(pattern)      — True if a Grep pattern is a naked code symbol
  glob_contains_symbol(pattern) — True if a Glob pattern encodes a code symbol
  extract_grep_pattern(cmd)    — extract search term from a shell grep command
  is_subagent(payload)         — True when a hook call originates inside a subagent
  has_idea_project(cwd)        — True if cwd is inside a JetBrains project (.idea/ or *.iml)
  get_flag_path(cwd)           — path to the per-project evidence flag file
  is_idea_active(cwd, sid)     — True if idea MCP proved active for this session
  deny(reason)                 — build the PreToolUse deny-response dict
  ask(reason)                  — build the PreToolUse ask-response dict (confirmation prompt)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex

# ── Regex patterns ────────────────────────────────────────────────────────────

# Characters that mark a deliberately-constructed regex (not a plain identifier).
# We intentionally exclude '.' — it also appears in PHP namespaces / method chains.
_STRONG_META = re.compile(r'[*+?\[\]()^${}|]')

# SCREAMING_SNAKE (env vars, constants): API_KEY, NEXT_PUBLIC_URL
_SCREAMING = re.compile(r'^[A-Z][A-Z0-9_]+$')

# PascalCase (two or more capitalised word parts): UserService, OrderItemDto
_PASCAL = re.compile(r'^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+$')

# Single capitalised word — only meaningful inside a namespace / dotted path:
# App, Service, Foo in App\Service\Foo; Controller in App\Controller
_CAP_WORD = re.compile(r'^[A-Z][a-z0-9]+$')

# camelCase (starts lowercase, contains an uppercase): getUserById, handleSubmit
_CAMEL = re.compile(r'^[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$')

# snake_case with 3+ parts: write_audit_log, get_user_by_id
_SNAKE3 = re.compile(r'^[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}$')

# File extensions that are never code symbols
_EXT = re.compile(
    r'^(ts|tsx|js|jsx|mjs|cjs|php|py|go|rs|java|kt|swift|vue|svelte|'
    r'json|yaml|yml|md|txt|sql|sh|css|scss|html|env|toml|xml|lock|ini|'
    r'cfg|conf|rb|cs|cpp|c|h|hpp|bash|zsh|fish|ps1)$',
    re.IGNORECASE,
)

# Keywords / markers that look like symbols but should be allowed
_KEYWORDS = frozenset({
    'TODO', 'FIXME', 'HACK', 'NOTE', 'XXX', 'BUG', 'NOQA',
    'MARK', 'WARN', 'ERROR', 'INFO', 'DEBUG', 'TRACE',
})

# ── Core symbol detection ─────────────────────────────────────────────────────

def _is_simple_token(t: str) -> bool:
    """Return True if t (no separators) looks like a code symbol."""
    if len(t) < 3:
        return False
    if t in _KEYWORDS:
        return False
    if _SCREAMING.match(t):  # env var / constant — allow Grep
        return False
    if _EXT.match(t):        # file extension
        return False
    return bool(_PASCAL.match(t) or _CAMEL.match(t) or _SNAKE3.match(t))


def is_code_symbol(pattern: str) -> bool:
    """
    Return True if the Grep pattern looks like a naked code symbol that
    should use mcp__idea__search_symbol instead.

    Conservative: when ambiguous, returns False (allow Grep).
    """
    if not pattern or len(pattern) < 3:
        return False

    # Strip leading/trailing whitespace and common word-boundary anchors
    stripped = re.sub(r'^\\b|\\b$', '', pattern.strip())
    if not stripped:
        return False

    # Strong regex metacharacters → deliberate pattern → allow
    if _STRONG_META.search(stripped):
        return False

    # Whitespace inside → multi-word pattern → allow
    if re.search(r'\s', stripped):
        return False

    # Backslash-separated (PHP namespace: App\Service\Foo)
    # or dot-separated (e.g. some.ClassName reference)
    # Any capitalized segment is evidence of a class/namespace symbol.
    if '.' in stripped or '\\' in stripped:
        parts = re.split(r'[.\\]', stripped)
        return any(_CAP_WORD.match(p) or _is_simple_token(p) for p in parts if p)

    return _is_simple_token(stripped)


def glob_contains_symbol(pattern: str) -> bool:
    """
    Return True if a Glob pattern encodes a symbol search
    (e.g. *UserService*, **/AuthProvider.tsx, *createOrder*).

    Allows: *.ts, src/**/*.php, *service*, **/middleware*, tsconfig.json.
    Blocks: *UserService*, *handleSubmit*, *get_user_sessions*.
    """
    # Extract all alphabetic/underscore tokens from the glob
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', pattern)
    for tok in tokens:
        if not tok or len(tok) < 4:
            continue
        if _EXT.match(tok):
            continue
        # Delegate to full symbol detection (handles PascalCase, camelCase,
        # snake_case-3+ correctly; short lowercase concepts like "service"
        # or "auth" return False naturally)
        if _is_simple_token(tok):
            return True
    return False


# ── Bash-grep pattern extractor ───────────────────────────────────────────────

# Grep flags that consume the NEXT argument as their value
_VALUE_FLAGS = frozenset('-A -B -C -m -e -f --file --include --exclude '
                         '--include-from --exclude-from --max-count'.split())


def extract_grep_pattern(cmd: str) -> str | None:
    """
    Parse a shell command that contains grep/rg/ag/ack and return
    the search pattern (first non-flag positional argument), or None.
    """
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return None

    # Find the grep-family command position
    grep_re = re.compile(r'\b(grep|rg|ag|ack)\b', re.IGNORECASE)
    cmd_idx = next(
        (i for i, p in enumerate(parts) if grep_re.fullmatch(os.path.basename(p))),
        None,
    )
    if cmd_idx is None:
        return None

    skip_next = False
    for arg in parts[cmd_idx + 1:]:
        if skip_next:
            skip_next = False
            continue
        # Long flag with no inline value → next arg is the value
        if arg.startswith('--'):
            if '=' not in arg and arg in _VALUE_FLAGS:
                skip_next = True
            continue
        # Short flag bundle
        if arg.startswith('-') and len(arg) > 1 and not arg[1:].lstrip('0123456789'):
            # Numeric arg (e.g. -3 for context lines) → skip
            continue
        if arg.startswith('-') and len(arg) > 1:
            # Flags that take a value: -A, -B, -C, -m, -e, -f
            if any(f in arg for f in ('A', 'B', 'C', 'm', 'e', 'f')):
                skip_next = True
            continue
        # First positional → pattern
        return arg

    return None


# ── Subagent + project detection ─────────────────────────────────────────────

def is_subagent(payload: dict) -> bool:
    """True when this hook call originates inside a subagent.

    Claude Code includes `agent_id` (and `agent_type`) on the hook input ONLY when the call fires
    inside a subagent (or via `--agent`). Subagents do not receive `mcp__idea__*` tools, so
    enforcing idea-first inside them can only deadlock — guards call this first and short-circuit.

    Note: a custom subagent whose frontmatter genuinely declares `mcp__idea__*` would also be
    carved out, but the payload exposes no tool-availability field, so this pragmatic check is the
    best available signal; the cost of a false carve-out (minor token waste) is far less than a
    deadlock.
    """
    return bool(payload.get('agent_id') or payload.get('agent_type'))


def has_idea_project(cwd: str) -> bool:
    """True if cwd is inside a JetBrains project the IDE could be serving.

    Walks up from cwd to root, checking each level for either a `.idea/` dir or a top-level `*.iml`
    module file. The `*.iml` marker covers JetBrains Gateway / remote-dev where `.idea/` lives on the
    backend but an `.iml` is present locally; checking it at every walk level (not just cwd) lets a
    subdir of such a project resolve correctly. Used to gate idea-first mode / the activation nudge:
    a project the IDE doesn't serve shouldn't be gated or nudged.
    """
    d = os.path.abspath(cwd)
    while True:
        if os.path.isdir(os.path.join(d, '.idea')):
            return True
        try:
            if any(name.endswith('.iml') for name in os.listdir(d)):
                return True
        except OSError:
            pass
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


# ── Evidence flag helpers ─────────────────────────────────────────────────────

_STATE_DIR = os.path.expanduser('~/.claude/state')
_ENFORCE_CONFIG = os.path.expanduser('~/.claude/hooks/idea-enforce.json')


def get_flag_path(cwd: str) -> str:
    """Return the path of the per-project evidence flag file."""
    digest = hashlib.md5(cwd.encode()).hexdigest()
    return os.path.join(_STATE_DIR, f'idea-active-{digest}')


def _enforcement_enabled(cwd: str) -> bool:
    """
    Return False when enforcement is globally disabled or cwd is excluded.

    Reads ~/.claude/hooks/idea-enforce.json (optional file).
    Missing / unreadable / invalid JSON → fail-open (return True).

    Config shape:
        {"enabled": true, "exclude_path_prefixes": ["/path/to/project"]}

    Use exclude_path_prefixes for projects whose language is not semantically
    indexed by the IDE (e.g. a Swift project opened as a generic WEB_MODULE).
    """
    try:
        with open(_ENFORCE_CONFIG) as f:
            cfg = json.load(f)
    except Exception:
        return True  # missing / unreadable → full enforcement

    if not cfg.get('enabled', True):
        return False

    for prefix in cfg.get('exclude_path_prefixes', []):
        if cwd.startswith(prefix):
            return False

    return True


def is_idea_active(cwd: str, session_id: str) -> bool:
    """
    Return True only if:
      1. enforcement is not globally disabled and cwd is not excluded, AND
      2. idea MCP has successfully answered for this project in the current session.

    Cross-session stale flags are ignored via session_id keying.
    """
    if not _enforcement_enabled(cwd):
        return False
    try:
        with open(get_flag_path(cwd)) as f:
            flag = json.load(f)
        return (
            flag.get('active') is True
            and flag.get('session_id') == session_id
        )
    except Exception:
        return False


# ── Proactive (fail-closed) activation + self-heal ────────────────────────────

# How many blocks a TENTATIVE (proactively-forced) flag may cause before it self-heals to native.
# A real idea call confirms the flag and resets this, so reasonable agents never hit it; it only
# saves a session where idea was forced ON but isn't actually reachable (e.g. Claude run outside the
# IDE), so the guards can't trap it.
_TENTATIVE_DENY_LIMIT = 3


def _denial_count_path(session_id: str) -> str:
    return os.path.join('/tmp', f'idea-tentative-denials-{session_id or "unknown"}')


def _read_flag(cwd: str):
    try:
        with open(get_flag_path(cwd)) as f:
            return json.load(f)
    except Exception:
        return None


def write_flag(cwd: str, session_id: str, tentative: bool) -> None:
    """Write the per-project active flag. tentative=True is a proactive (forced) activation not yet
    confirmed by a real idea call; tentative=False means idea answered for real."""
    flag = {'session_id': session_id, 'cwd': cwd, 'active': True, 'tentative': bool(tentative)}
    try:
        os.makedirs(_STATE_DIR, exist_ok=True)
        p = get_flag_path(cwd)
        tmp = p + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(flag, f)
        os.replace(tmp, p)
    except Exception:
        pass


def clear_flag(cwd: str) -> None:
    try:
        os.unlink(get_flag_path(cwd))
    except FileNotFoundError:
        pass
    except Exception:
        pass


def reset_denials(session_id: str) -> None:
    try:
        os.unlink(_denial_count_path(session_id))
    except FileNotFoundError:
        pass
    except Exception:
        pass


def register_block(cwd: str, session_id: str) -> bool:
    """Call immediately before a guard emits its deny. Returns True if the deny should proceed.

    Returns False (and SELF-HEALS: clears the flag → native tools allowed) when a TENTATIVE
    proactively-forced flag has caused repeated blocks WITHOUT idea ever confirming — i.e. idea
    isn't actually answering this session, so the guards must not trap it. A CONFIRMED flag (idea
    answered for real) always proceeds: its denials are legitimate "use idea instead".
    """
    flag = _read_flag(cwd)
    if not flag or flag.get('session_id') != session_id:
        return True
    if not flag.get('tentative'):
        return True  # confirmed -> legitimate deny
    p = _denial_count_path(session_id)
    try:
        n = int(open(p).read().strip())
    except Exception:
        n = 0
    n += 1
    if n >= _TENTATIVE_DENY_LIMIT:
        clear_flag(cwd)
        reset_denials(session_id)
        return False  # self-healed -> allow native this session
    try:
        with open(p, 'w') as f:
            f.write(str(n))
    except Exception:
        pass
    return True


# ── Response builder ──────────────────────────────────────────────────────────

def deny(reason: str) -> dict:
    """Build the PreToolUse deny-response payload."""
    return {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason,
        }
    }


def ask(reason: str) -> dict:
    """Build the PreToolUse ask-response payload (surfaces a confirmation prompt instead of a hard
    deny). Used by idea-agent-guard: a delegation that merely looks like local code search gets
    confirmed by the user rather than hard-blocked, so legitimate external-research delegations
    (which can't self-escape via IDEA_GATE_OFF — it doesn't propagate through the Agent tool) are
    not trapped."""
    return {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'ask',
            'permissionDecisionReason': reason,
        }
    }


# ── Self-test (run directly) ──────────────────────────────────────────────────

if __name__ == '__main__':
    cases: list[tuple[str, bool, str]] = [
        # (input, expected, label)
        ('UserService',         True,  'PascalCase class'),
        ('OrderItemDto',        True,  'PascalCase DTO'),
        ('getUserById',         True,  'camelCase method'),
        ('handleSubmit',        True,  'camelCase handler'),
        ('write_audit_log',     True,  'snake_case 3-part'),
        ('get_user_sessions',   True,  'snake_case 3-part'),
        ('App\\Service\\Foo',    True,  'PHP namespace'),
        ('router.refresh',      False, 'dotted lowercase (not PHP-typical; allow)'),
        ('TODO',                False, 'keyword'),
        ('FIXME',               False, 'keyword'),
        ('API_KEY',             False, 'SCREAMING_SNAKE'),
        ('NEXT_PUBLIC_URL',     False, 'SCREAMING_SNAKE env'),
        ('flex-col',            False, 'CSS class'),
        ('auth',                False, 'too short / lowercase'),
        ('*.php',               False, 'glob with meta'),
        ('src/**',              False, 'path glob'),
        ('.task',               False, 'dotfile path'),
        ('getUserById.*',       False, 'regex with meta'),
        ('UserService.*users',  False, 'regex with meta'),
    ]

    glob_cases: list[tuple[str, bool, str]] = [
        ('*UserService*',       True,  'symbol glob'),
        ('**/AuthProvider.tsx', True,  'PascalCase in path'),
        ('*createOrder*',       True,  'camelCase glob'),
        ('*get_user_sessions*', True,  'snake_case glob'),
        ('*.ts',                False, 'extension glob'),
        ('src/**/*.php',        False, 'path + ext glob'),
        ('*service*',           False, 'lowercase concept'),
        ('*auth*',              False, 'lowercase concept'),
        ('**/middleware*',      False, 'lowercase concept'),
        ('tsconfig.json',       False, 'config file'),
        ('README.md',           False, 'docs'),
    ]

    ok = True
    print('is_code_symbol() tests:')
    for inp, expected, label in cases:
        result = is_code_symbol(inp)
        status = '✓' if result == expected else '✗ FAIL'
        if result != expected:
            ok = False
        print(f'  {status}  is_code_symbol({inp!r}) = {result}  ({label})')

    print('\nglob_contains_symbol() tests:')
    for inp, expected, label in glob_cases:
        result = glob_contains_symbol(inp)
        status = '✓' if result == expected else '✗ FAIL'
        if result != expected:
            ok = False
        print(f'  {status}  glob_contains_symbol({inp!r}) = {result}  ({label})')

    print('\nextract_grep_pattern() tests:')
    grep_cases = [
        ('grep UserService src/', 'UserService'),
        ('grep -r handleSubmit .', 'handleSubmit'),
        ('rg write_audit_log --type php', 'write_audit_log'),
        ('ag "UserService" src/', 'UserService'),
        ('grep -E "UserService|OrderItem" .', 'UserService|OrderItem'),
        ('git grep UserService', 'UserService'),   # extracted but git grep is allowed separately
    ]
    for cmd, expected in grep_cases:
        result = extract_grep_pattern(cmd)
        status = '✓' if result == expected else '✗ FAIL'
        if result != expected:
            ok = False
        print(f'  {status}  extract_grep_pattern({cmd!r}) = {result!r}')

    print('\nis_subagent() tests:')
    sub_cases: list[tuple[dict, bool, str]] = [
        ({'agent_id': 'abc-123'},                      True,  'agent_id present'),
        ({'agent_type': 'Explore'},                    True,  'agent_type present'),
        ({'agent_id': 'x', 'agent_type': 'Plan'},      True,  'both present'),
        ({},                                           False, 'no agent fields'),
        ({'session_id': 's', 'cwd': '/p'},             False, 'session fields only'),
        ({'agent_id': ''},                             False, 'empty agent_id'),
    ]
    for payload, expected, label in sub_cases:
        result = is_subagent(payload)
        status = '✓' if result == expected else '✗ FAIL'
        if result != expected:
            ok = False
        print(f'  {status}  is_subagent({payload!r}) = {result}  ({label})')

    print('\nhas_idea_project() tests:')
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        d_idea = os.path.join(tmp, 'proj-idea')          # has .idea/
        os.makedirs(os.path.join(d_idea, '.idea'))
        d_iml = os.path.join(tmp, 'proj-iml')            # *.iml at root, no .idea/
        os.makedirs(d_iml)
        open(os.path.join(d_iml, 'app.iml'), 'w').close()
        d_iml_sub = os.path.join(d_iml, 'src', 'svc')    # subdir of an .iml-only project
        os.makedirs(d_iml_sub)
        d_plain = os.path.join(tmp, 'proj-plain')        # no markers
        os.makedirs(d_plain)
        d_sub = os.path.join(d_idea, 'src', 'foo')       # .idea/ found by walking up
        os.makedirs(d_sub)
        dir_cases: list[tuple[str, bool, str]] = [
            (d_idea,    True,  '.idea/ present'),
            (d_iml,     True,  '*.iml at root, no .idea/'),
            (d_iml_sub, True,  '*.iml found by walking up (remote-dev subdir)'),
            (d_plain,   False, 'no markers'),
            (d_sub,     True,  '.idea/ found by walking up'),
        ]
        for d, expected, label in dir_cases:
            result = has_idea_project(d)
            status = '✓' if result == expected else '✗ FAIL'
            if result != expected:
                ok = False
            print(f'  {status}  has_idea_project({os.path.basename(d)!r}) = {result}  ({label})')

    print('\n' + ('All tests passed.' if ok else 'SOME TESTS FAILED.'))
    raise SystemExit(0 if ok else 1)
