import os
import sys
import textwrap
from collections import defaultdict

import launcher
from hydrustools import gui
from hydrustools.component.toolwindow import ToolWindow

problems = []

duplicates = defaultdict(list)

if 'tools' in sys.argv:
    for group, items in gui.MENU.items():
        print(f"{group}", file=sys.stderr)
        printed_header = False

        for entry in items:
            label = entry.label
            command = entry.command

            print(f"{group} > {label}", file=sys.stderr)

            body: str = ""
            if isinstance(command, type) and issubclass(command, ToolWindow):
                helptype = "[f1help]"
                body = command.helpstr
            elif callable(command):
                helptype = "[docstr]"
                if command.__doc__ is None:
                    problems.append(f"Missing docstring for {label!r} {command}")
                    continue
                body = command.__doc__
            elif command is None:
                helptype = "none"
                body = "Not yet implemented."
            else:
                raise NotImplementedError(command)

            duplicates[body].append(label)
            duplicates[label].append(command)
            if "TODO" in body.upper():
                problems.append(f"Help for {label} is unfinished! {textwrap.shorten(body, width=40)}")

            print(f"  {helptype} {textwrap.shorten(body, width=70)}", file=sys.stderr)
            if body:
                if not printed_header:
                    print(f"## {group}\n")
                    printed_header = True

                print(f"### {label}\n")
                print(body)
                print()


if 'cli' in sys.argv:
    print("CLI Utilities", file=sys.stderr)
    print("## CLI Utilities\n")
    for launcher_module in launcher.SubModules._allModules():
        print(f"  {launcher_module}", file=sys.stderr)
        print(f"### `{launcher_module}`\n")
        print(f"`./HydrusTools {launcher_module}` (compiled)  ")
        print(f"`(venv) python3 launcher.py {launcher_module}` (dev)  ")
        print()

        sys.argv = [launcher_module, '--help']
        os.environ['COLUMNS'] = '110'

        print("```text")
        try:
            getattr(launcher.SubModules, launcher_module)()
        except SystemExit:
            pass
        print("```\n")


for body, labels in duplicates.items():
    if len(labels) > 1:
        problems.append(f"Duplicate docs (copy-pasted?) {labels} {textwrap.shorten(body, width=70)}")

if len(problems) > 0:
    print("\nProblems!\n", file=sys.stderr)
    for p in problems:
        print(p, file=sys.stderr)
