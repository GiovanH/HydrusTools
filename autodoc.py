import argparse
import os
import sys
import textwrap
from collections import defaultdict

import launcher
from hydrustools import gui
from hydrustools.component.toolwindow import ToolWindow

problems = []

duplicates = defaultdict(list)

def print_full_help(parser: argparse.ArgumentParser, prefix: str = "") -> None:
    label = prefix if prefix else parser.prog

    epilog = None

    print(f"### `{label}`\n")
    # Print strings as text outside the --help invocation
    if parser.usage:
        print(f"`{parser.format_usage()}`" + "\n")
        parser.usage = None
    if parser.description:
        print(parser.description + "\n")
        parser.description = None
    if parser.epilog:
        epilog = parser.epilog
        parser.epilog = None

    print("```text")
    parser.print_help()
    print("```\n")

    if epilog:
        print(epilog + "\n")

    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for sub_name, sub_parser in action.choices.items():
            child_prefix = f"{prefix} {sub_name}".strip() if prefix else sub_name
            print_full_help(sub_parser, prefix=child_prefix)

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
    sys.argv = ["launcher.py"]
    parser = launcher.get_parser()

    print("CLI Utilities", file=sys.stderr)
    print("## CLI Utilities\n")
    print_full_help(parser)


for body, labels in duplicates.items():
    if len(labels) > 1:
        problems.append(f"Duplicate docs (copy-pasted?) {labels} {textwrap.shorten(body, width=70)}")

if len(problems) > 0:
    print("\nProblems!\n", file=sys.stderr)
    for p in problems:
        print(p, file=sys.stderr)
