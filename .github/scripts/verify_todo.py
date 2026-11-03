import re
import subprocess

TITLE = "### 📝 Complete TODO List"
README_RE = re.compile(r"^- \[ \] \*\*(?P<path>.*?):(?P<line>\d+)\*\* - (?P<text>.*)$")
TODO_RE = re.compile(r"^\s*#\s*TODO\b\s*:?\s*(?P<text>.*?)\s*$")


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def parse_entries(readme):
    assert readme.count(TITLE) == 1, "TODO title is missing or duplicated"
    start = readme.index(TITLE) + len(TITLE)
    end = readme.index("\n\n## ", start)
    entries = []
    for line in readme[start:end].splitlines():
        if not line.strip():
            continue
        match = README_RE.match(line)
        assert match, f"Bad TODO line: {line}"
        entries.append((match.group("path"), int(match.group("line")), match.group("text")))
    return entries, start, end


def replace_todos(readme, entries):
    _, start, end = parse_entries(readme)
    lines = [f"- [ ] **{path}:{line}** - {text}" for path, line, text in entries]
    return readme[:start] + "\n\n" + "\n".join(lines) + readme[end:]


dev_readme = git("show", "origin/dev:README.md")
previous_readme = git("show", "7463fefd0f55ae2ba0b919e06527588022893495:README.md")
entries, _, _ = parse_entries(dev_readme)
assert len(entries) == 215, f"Expected 215 entries, got {len(entries)}"
keys = [(path, line) for path, line, _ in entries]
assert keys == sorted(keys), "TODO entries are not sorted by path and line"
assert len(keys) == len(set(keys)), "Duplicate path:line entries found"
assert replace_todos(previous_readme, entries) == dev_readme, "Changes outside the TODO section"

for path in ["luffy/deepscaler/utils.py", "luffy/verl/verl/protocol.py"]:
    scanned = []
    for line_number, line in enumerate(git("show", f"origin/dev:{path}").splitlines(), 1):
        match = TODO_RE.match(line)
        if match:
            scanned.append((path, line_number, match.group("text")))
    documented = sorted((p, line, text) for p, line, text in entries if p == path)
    assert documented == scanned, f"README does not match dev TODO scan for {path}"

removed = [
    ("luffy/deepscaler/utils.py", 45, "Implement OpenAI API client initialization"),
    ("luffy/deepscaler/utils.py", 46, "Add proper authentication handling"),
    ("luffy/deepscaler/utils.py", 47, "Implement exponential backoff retry logic for rate limits"),
    ("luffy/deepscaler/utils.py", 48, "Add comprehensive error handling for different API errors"),
    ("luffy/deepscaler/utils.py", 49, "Implement response parsing and validation"),
    ("luffy/verl/verl/protocol.py", 114, "Implement batch dimension folding for efficient processing"),
    ("luffy/verl/verl/protocol.py", 115, "Add validation for batch size compatibility"),
    ("luffy/verl/verl/protocol.py", 116, "Handle edge cases where batch_size is not divisible by new_batch_size"),
    ("luffy/verl/verl/protocol.py", 131, "Implement batch dimension unfolding functionality"),
    ("luffy/verl/verl/protocol.py", 132, "Add support for variable batch dimensions"),
    ("luffy/verl/verl/protocol.py", 134, "Handle non-tensor batch data reshaping properly"),
]
assert all(item not in entries for item in removed), "A completed TODO was not removed"
changed_files = git("diff", "--name-only", "7463fefd0f55ae2ba0b919e06527588022893495", "origin/dev").splitlines()
assert changed_files == ["README.md"], f"Unexpected dev changes: {changed_files}"
print("VERIFICATION PASSED: 215 sorted entries, correct line numbers, only README.md changed, title unchanged.")
for path, line, text in entries:
    if path in {"luffy/deepscaler/utils.py", "luffy/verl/verl/protocol.py"}:
        print(f"  {path}:{line} - {text}")
