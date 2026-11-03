import difflib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

TITLE = "### 📝 Complete TODO List"
TODO_RE = re.compile(r"^\s*#\s*TODO\b\s*:?\s*(?P<text>.*?)\s*$")
README_RE = re.compile(r"^- \[ \] \*\*(?P<path>.*?):(?P<line>\d+)\*\* - (?P<text>.*)$")


def git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=check)


def git_out(*args, cwd=None):
    return git(*args, cwd=cwd).stdout


def scan_ref(ref):
    paths = [p for p in git_out("ls-tree", "-r", "--name-only", ref).splitlines() if p.endswith(".py")]
    entries = []
    for path in paths:
        try:
            content = git_out("show", f"{ref}:{path}")
        except subprocess.CalledProcessError as exc:
            print(f"Failed to read {path} at {ref}: {exc.stderr}", file=sys.stderr)
            raise
        for line_number, line in enumerate(content.splitlines(), 1):
            match = TODO_RE.match(line)
            if match:
                entries.append({"path": path, "line": line_number, "text": match.group("text")})
    entries.sort(key=lambda item: (item["path"], item["line"]))
    return entries


def format_entries(entries):
    return [f"- [ ] **{e['path']}:{e['line']}** - {e['text']}" for e in entries]


def parse_readme_entries(readme):
    if readme.count(TITLE) != 1:
        raise RuntimeError(f"Expected exactly one TODO title, found {readme.count(TITLE)}")
    start = readme.index(TITLE) + len(TITLE)
    end = readme.index("\n\n## ", start)
    section = readme[start:end]
    entries = []
    for line in section.splitlines():
        if not line.strip():
            continue
        match = README_RE.match(line)
        if not match:
            raise RuntimeError(f"Unexpected README TODO line format: {line!r}")
            continue
        entries.append({"path": match.group("path"), "line": int(match.group("line")), "text": match.group("text")})
    return entries


def replace_readme_todos(readme, entries):
    if readme.count(TITLE) != 1:
        raise RuntimeError("TODO title must occur exactly once")
    start = readme.index(TITLE) + len(TITLE)
    end = readme.index("\n\n## ", start)
    return readme[:start] + "\n\n" + "\n".join(format_entries(entries)) + readme[end:]


def print_diff(old_lines, new_lines, fromfile, tofile):
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=fromfile, tofile=tofile, lineterm=""))
    print("\n".join(diff) if diff else "(no differences)")
    return diff


def main():
    main_readme = git_out("show", "origin/main:README.md")
    dev_readme = git_out("show", "origin/dev:README.md")
    baseline_entries = parse_readme_entries(main_readme)
    main_entries = scan_ref("origin/main")
    print(f"Baseline README entries: {len(baseline_entries)}")
    print(f"Scanned main TODO entries: {len(main_entries)}")
    if main_entries != baseline_entries:
        print("VALIDATION FAILED: scanner does not reproduce the main baseline", file=sys.stderr)
        print_diff(format_entries(baseline_entries), format_entries(main_entries), "README-baseline", "scanned-main")
        return 1
    print("VALIDATION PASSED: scanner exactly reproduces the main README baseline.")

    dev_entries = scan_ref("origin/dev")
    old_section = format_entries(baseline_entries)
    new_section = format_entries(dev_entries)
    print(f"Scanned dev TODO entries: {len(dev_entries)}")
    print_diff(old_section, new_section, "main-README", "dev-scan")
    print("\nDEV SECTION BEGIN")
    print(TITLE)
    print()
    print("\n".join(new_section))
    print("DEV SECTION END")

    expected_dev_readme = replace_readme_todos(dev_readme, dev_entries)
    # Ensure only the TODO section changes.
    if replace_readme_todos(dev_readme, baseline_entries) != dev_readme:
        print("WARNING: current dev README differs from the main baseline outside the TODO section?", file=sys.stderr)
    apply = os.environ.get("APPLY", "").lower() == "true"
    if not apply:
        print("Dry run only; set apply=true to commit.")
        return 0

    tempdir = tempfile.mkdtemp(prefix="luffy-dev-")
    try:
        git("worktree", "add", "--detach", tempdir, "origin/dev")
        (Path(tempdir) / "README.md").write_text(expected_dev_readme, encoding="utf-8")
        status = git("status", "--short", cwd=tempdir).stdout
        print(f"Worktree changes:\n{status}")
        if not status.strip():
            print("README is already up to date; nothing to commit.")
            return 0
        git("add", "README.md", cwd=tempdir)
        git("-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit", "-m", "docs: update complete TODO list", cwd=tempdir)
        result = git("push", "origin", "HEAD:dev", cwd=tempdir)
        print(result.stdout)
        print(result.stderr)
    finally:
        git("worktree", "remove", "--force", tempdir, check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
