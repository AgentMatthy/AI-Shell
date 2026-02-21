#!/usr/bin/env python

"""
Command safety checker for auto-approving read-only commands.

Parses shell commands (including chained, piped, and nested commands) to determine
if ALL sub-commands are in the safe (read-only) list. Any output redirection to files
or unsafe sub-command causes the entire command to require user confirmation.

Design principle: fail closed. Any parsing error or ambiguity = require confirmation.
"""

import os
import re
import shlex
from typing import List, Set


# Shell operators that separate commands into independent units
PIPE_AND_CHAIN_OPERATORS = {'&&', '||', ';', '|', '|&', '&'}

# Tokens that indicate the next token should be a new command
COMMAND_STARTERS = PIPE_AND_CHAIN_OPERATORS | {'('}

# Benign command prefixes that don't change the safety of the underlying command
# NOTE: sudo, doas, nohup are intentionally excluded - they change execution context
COMMAND_PREFIXES = {'time', 'timeout', 'nice', 'ionice', 'env', 'stdbuf', 'chrt', 'taskset'}

# Output redirection operators that write to files (unsafe)
OUTPUT_REDIRECT_OPERATORS = {'>', '>>', '&>', '&>>'}

# All redirection operators (for skipping during command extraction)
ALL_REDIRECT_OPERATORS = {'>', '>>', '<', '<<', '<<<', '&>', '&>>', '>&', '<&'}


def is_safe_command(command: str, safe_commands: Set[str]) -> bool:
    """
    Check if a shell command (potentially chained/piped) is safe to auto-execute.

    A command is safe only if ALL of the following are true:
    - Every individual command in the chain/pipe is in the safe_commands set
    - No output redirections to files (>, >>, &>, etc.) — except to /dev/null
    - All command substitutions ($(...) and `...`) contain only safe commands
    - No process substitution with >(...) (writes to a process)

    Returns False (unsafe/require confirmation) on any parsing error — fail closed.
    """
    if not command or not command.strip():
        return True

    try:
        return _check_safety(command.strip(), safe_commands)
    except Exception:
        # Any error whatsoever = require confirmation
        return False


def _check_safety(command: str, safe_commands: Set[str]) -> bool:
    """Internal safety check implementation."""

    # Step 1: Recursively check all command substitutions
    for inner_cmd in _extract_command_substitutions(command):
        if not _check_safety(inner_cmd, safe_commands):
            return False

    # Step 2: Tokenize
    try:
        tokens = _tokenize(command)
    except ValueError:
        return False  # Unparseable = unsafe

    if not tokens:
        return True

    # Step 3: Check for unsafe output redirections
    if _has_unsafe_redirections(tokens):
        return False

    # Step 4: Extract all command names and verify they're in the safe set
    commands = _extract_command_names(tokens)

    if not commands:
        # Couldn't identify any commands — could be a complex construct
        return False

    for cmd in commands:
        # Handle full paths: /usr/bin/cat -> cat
        base_cmd = os.path.basename(cmd)
        if base_cmd not in safe_commands:
            return False

    return True


def _tokenize(command: str) -> List[str]:
    """
    Tokenize a shell command using shlex with punctuation awareness.

    punctuation_chars=True makes shlex treat |, &, ;, <, >, (, ) as
    punctuation and groups consecutive punctuation chars (e.g., && , >>, |&).
    Quoting is handled properly (content inside quotes is a single token).
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        return list(lexer)
    except ValueError:
        raise


def _has_unsafe_redirections(tokens: List[str]) -> bool:
    """
    Check if the token list contains output redirections to files.

    Safe redirections (not flagged):
    - FD-to-FD: >&1, >&2, 2>&1
    - To /dev/null: > /dev/null, 2> /dev/null
    - Input redirections: <, <<, <<<

    Unsafe redirections (flagged):
    - To files: > file, >> file, &> file, &>> file
    - Process substitution output: >(cmd)
    """
    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Process substitution with output: >(...)
        if token == '>(':
            return True

        # Standard output redirections: >, >>, &>, &>>
        if token in OUTPUT_REDIRECT_OPERATORS:
            next_idx = i + 1
            if next_idx < len(tokens):
                next_token = tokens[next_idx]

                # Safe: redirect to /dev/null
                if next_token == '/dev/null':
                    i = next_idx + 1
                    continue

                # Safe: FD-to-FD redirect (>&1, >&2, etc.)
                # This handles the case where > is followed by &N
                if token == '>' and next_token.startswith('&'):
                    fd_part = next_token[1:]
                    if fd_part.isdigit():
                        i = next_idx + 1
                        continue

            # Any other output redirection = writing to a file
            return True

        # Handle >& operator (FD redirect or file redirect)
        if token == '>&':
            next_idx = i + 1
            if next_idx < len(tokens):
                next_token = tokens[next_idx]
                # Safe: >&1, >&2 (FD-to-FD)
                if next_token.isdigit():
                    i = next_idx + 1
                    continue
                # Safe: >& /dev/null
                if next_token == '/dev/null':
                    i = next_idx + 1
                    continue
            # >& file = unsafe
            return True

        # Numeric file descriptor redirections as combined tokens (rare with shlex but handle it)
        # e.g., 2> or 1>> when tokenized as a single token
        if re.match(r'^\d+>{1,2}$', token):
            next_idx = i + 1
            if next_idx < len(tokens):
                next_token = tokens[next_idx]
                if next_token == '/dev/null':
                    i = next_idx + 1
                    continue
            return True

        i += 1

    return False


def _extract_command_names(tokens: List[str]) -> List[str]:
    """
    Extract all command names from a tokenized shell command.

    Handles:
    - Chained commands: cmd1 && cmd2 || cmd3 ; cmd4
    - Piped commands: cmd1 | cmd2
    - Background: cmd1 & cmd2
    - Subshells: (cmd1; cmd2)
    - Command prefixes: time cmd, env VAR=val cmd
    - Environment variable assignments: VAR=val cmd
    """
    commands = []
    expect_command = True
    i = 0

    while i < len(tokens):
        token = tokens[i]

        # Operators signal the start of a new command
        if token in COMMAND_STARTERS:
            expect_command = True
            i += 1
            continue

        # Closing paren — just skip
        if token == ')':
            i += 1
            continue

        if expect_command:
            # Skip command prefixes (time, env, nice, etc.)
            while i < len(tokens) and tokens[i] in COMMAND_PREFIXES:
                i += 1

            # Skip environment variable assignments: VAR=value
            while i < len(tokens) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', tokens[i]):
                i += 1

            # The next non-operator, non-redirection token is the command
            if i < len(tokens):
                t = tokens[i]
                if t not in COMMAND_STARTERS and t != ')' and not _is_redirection(t):
                    commands.append(t)
                    expect_command = False

            i += 1
            continue

        # Skip redirection operators and their targets
        if _is_redirection(token):
            i += 2  # Skip operator + target
            continue

        # Regular argument — skip
        i += 1

    return commands


def _is_redirection(token: str) -> bool:
    """Check if a token is any type of redirection operator."""
    if token in ALL_REDIRECT_OPERATORS:
        return True
    # Numeric FD redirections: 2>, 1>>, etc.
    if re.match(r'^\d+[<>]{1,2}$', token):
        return True
    # Combined FD redirects: >&, <&
    if token in ('>&', '<&', '>|', '>(',):
        return True
    return False


def _extract_command_substitutions(command: str) -> List[str]:
    """
    Extract inner commands from $(...) and `...` command substitutions.

    Handles nested $(...) correctly. Respects single-quoted strings
    (no substitution inside single quotes).
    """
    results = []

    # Extract $(...) with proper nesting
    results.extend(_extract_dollar_parens(command))

    # Extract `...` (backtick substitution — no nesting in backticks)
    for match in re.finditer(r'`([^`]+)`', command):
        inner = match.group(1)
        # Only add if not inside single quotes (rough check)
        before = command[:match.start()]
        if before.count("'") % 2 == 0:
            results.append(inner)

    return results


def _extract_dollar_parens(command: str) -> List[str]:
    """
    Extract commands from $(...), handling nested parentheses and quoting.
    """
    results = []
    i = 0
    in_single_quote = False

    while i < len(command):
        c = command[i]

        # Track single quotes (no substitution inside them)
        if c == "'" and not in_single_quote:
            in_single_quote = True
            i += 1
            while i < len(command) and command[i] != "'":
                i += 1
            i += 1  # skip closing quote
            continue

        # Found $( — extract the inner command
        if not in_single_quote and i + 1 < len(command) and command[i:i + 2] == '$(':
            depth = 1
            start = i + 2
            j = start
            sq = False
            dq = False

            while j < len(command) and depth > 0:
                ch = command[j]
                if ch == "'" and not dq:
                    sq = not sq
                elif ch == '"' and not sq:
                    dq = not dq
                elif not sq and not dq:
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                j += 1

            if depth == 0:
                results.append(command[start:j - 1])
            i = j
            continue

        i += 1

    return results
