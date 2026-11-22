"""`vnotes notes`: run the skill headless in an installed Claude Code or Codex."""
import contextlib
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .core import SKILL, Fail, fetch, frames, save_notes

# codex features switched off for a headless run, so that view_image is what remains
CODEX_OFF = ('shell_tool', 'unified_exec', 'apps', 'plugins', 'remote_plugin', 'browser_use',
             'browser_use_external', 'computer_use', 'image_generation', 'in_app_browser', 'hooks',
             'skill_search', 'tool_suggest', 'multi_agent', 'goals', 'sleep_tool')


def ask(agent, message, out):
    """Runs one headless turn in which the agent can look at files and do nothing else.

    Args:
        agent: `claude` or `codex`.
        message: The whole prompt.
        out: The notes folder, used as the working folder.

    Returns:
        The agent's final reply.

    Raises:
        Fail: If the harness fails or says nothing.
    """
    if agent == 'claude':
        # Read is the only tool, confined to the folder; no user settings, plugins, hooks or MCP servers
        done = subprocess.run(['claude', '-p', '--tools', 'Read', '--restricted', '--safe-mode',
                               '--strict-mcp-config', '--no-session-persistence'],
                              cwd=out, input=message, stdout=subprocess.PIPE, text=True)
        reply = done.stdout
    else:
        with tempfile.TemporaryDirectory() as tmp:
            last = Path(tmp, 'reply.md')
            done = subprocess.run(['codex', 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                                   '-s', 'read-only', *(flag for name in CODEX_OFF for flag in ('--disable', name)),
                                   '-c', 'web_search="disabled"', '-o', str(last), '-'],
                                  cwd=out, input=message, stdout=subprocess.DEVNULL, text=True)
            reply = last.read_text() if last.is_file() else ''
    if done.returncode or not reply.strip():
        # the harness prints its own error (login, refusal, rate limit) where the reply would be
        said = ' It said: ' + ' '.join(reply.split())[:300] if reply.strip() else ''
        raise Fail(f'{agent} gave no reply (exit code {done.returncode}).{said}')
    return reply.strip()


def notes(url, request, agent, out):
    """Fetches a video, then runs the skill headless in an installed harness.

    The transcript and the pictures are untrusted text, so the agent can only
    read. It replies with either a frame request or the finished notes; this
    function pulls the frames and writes the notes itself.

    Args:
        url: The video page.
        request: What the reader wants from the notes, or None.
        agent: `claude` or `codex`; uses that CLI's existing login.
        out: Folder to write into, or None for the default.

    Raises:
        Fail: If the harness is missing or never returns usable notes.
    """
    if not shutil.which(agent):
        raise Fail(f'{agent} is not installed or not on PATH.')
    out = fetch(url, out).resolve()
    meta = (out / 'meta.json').read_text()
    filename = json.loads(meta).get('notes_file', 'notes.md')
    sheets = '\n'.join(str(sheet) for sheet in sorted((out / 'index').glob('*.jpg'))) or 'none: the video has no picture'
    brief = (f'Write video notes by following the skill at the end of this message.\n\nURL: {url}\n'
             f'What the reader asked for: {request or "thorough study notes"}\n\n'
             f'You are running headless. You can look at files in {out} and do nothing else: '
             'no commands, no writing, no network.\n'
             'Step 1 is done. meta.json and transcript.txt are copied below. The index sheets are:\n'
             f'{sheets}\n\n'
             'A program reads your reply, in one of two ways:\n'
             '- To get frames (step 3), make the first line of your reply `FRAMES:` followed by the times, for '
             'example `FRAMES: 1:22 3:54 12:40`. Under that line write a handover: the outline of the notes '
             'so far and what each requested frame should show. A fresh session will be given that handover '
             'and the frames. Ask for the bracketing call the same way.\n'
             '- When the notes are finished (step 4), reply with the complete Markdown notes and nothing '
             'else: no preamble and no code fence. Your reply is saved word for word. Link images '
             'as `frames/01-22.jpg`.\n\n')
    material = (f"## meta.json\n\n{meta}\n"
                f"## transcript.txt\n\n{(out / 'transcript.txt').read_text()}\n"
                + SKILL.read_text())
    progress = ''
    # ponytail: every turn is a fresh session that reads the material again, because not every
    # harness can resume one. Resume the session instead if the repeated reading costs too much.
    for turn in range(1, 7):
        reply = ask(agent, brief + progress + material, out)
        first, _, rest = reply.partition('\n')
        if first.upper().startswith('FRAMES:'):
            report = io.StringIO()
            try:
                with contextlib.redirect_stdout(report):
                    frames(out, first[len('FRAMES:'):].split(), url)
                outcome = report.getvalue()
            except Fail as error:
                outcome = f'The request did not work: {error}'
            print(outcome)
            progress += f'## Progress: turn {turn}\n\nYou replied:\n\n{reply}\n\nWhat happened:\n\n{outcome}\n\n'
            continue
        missing = save_notes(out, reply, filename)
        if not missing:
            return
        outcome = f'Your notes were not saved. They link to images that do not exist: {", ".join(missing)}.'
        print(outcome)
        progress += (f'## Progress: turn {turn}\n\n{outcome} Ask for them with FRAMES:, or reply with the '
                     'full notes again without those links.\n\n')
    raise Fail(f'{agent} did not return usable notes in six turns.')
