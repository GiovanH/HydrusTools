import sys
from typing import DefaultDict
from hydrustools import gui
from hydrustools.component.toolwindow import ToolWindow
import textwrap

problems = []

duplicates = DefaultDict(list)

for group, items in gui.MENU.items():
    print(f"{group}", file=sys.stderr)
    print(f"## {group}\n")

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
            print(f"### {label}\n")
            print(body)
            print()

for body, labels in duplicates.items():
    if len(labels) > 1:
        problems.append(f"Duplicate docs (copy-pasted?) {labels} {textwrap.shorten(body, width=70)}")

if len(problems) > 0:
    print("\nProblems!\n", file=sys.stderr)
    for p in problems:
        print(p, file=sys.stderr)
