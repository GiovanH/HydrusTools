import argparse
import importlib.metadata
import sys
from functools import partial

import hydrustools.cli.bubblegroup
import hydrustools.cli.lookup
import hydrustools.cli.todogroup
import hydrustools.utils.convert_booru
from hydrustools.utils import htlogging
from hydrustools.utils.argparse_formatter import HTApFmtCls

DIST_NAME = 'hydrustools'

try:
    version = importlib.metadata.version(DIST_NAME)
except importlib.metadata.PackageNotFoundError:
    version = "dev"


def get_parser():
    parser = argparse.ArgumentParser(
        formatter_class=HTApFmtCls
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {version}')

    # Submodules
    subparsers = parser.add_subparsers(dest="tool", metavar="TOOL")
    subparsers.required = True
    subparsers.help = "Main tool. Options: {%(choices)s}"

    # Alternate subparsers.add_parser factory
    compact_parser = partial(subparsers.add_parser, formatter_class=HTApFmtCls)

    hydrustools.cli.bubblegroup.define_parser(compact_parser("bubblegroup"))
    hydrustools.utils.convert_booru.define_parser(compact_parser("convert_booru"))
    hydrustools.cli.lookup.define_parser(compact_parser("lookup"))
    hydrustools.cli.todogroup.define_parser(compact_parser("todogroup"))

    # Usage. argparse does this for `choices` but not subparsers!
    subparsers_fmt = "{" + ', '.join(subparsers._name_parser_map.keys()) + "}"
    parser.usage = f"{parser.prog} {subparsers_fmt}"

    return parser

def main():
    htlogging.configure_logging()

    if len(sys.argv) > 1:
        parser = get_parser()
        args = parser.parse_args()
        args.func(args)

    else:
        from hydrustools import gui
        sys.exit(gui.main())

if __name__ == '__main__':
    main()
