import sys

import charset_normalizer  # For pyinstaller+requests

from hydrustools import gui


class SubModules():
    # Container class so we know what methods/options exist
    # This is all just to implement _allModules.

    @classmethod
    def _allModules(cls):
        return [c for c in dir(cls) if not c.startswith('_')]

    @classmethod
    def help(cls):
        print("HydrusTools launcher.")
        print("With no arguments, launches the GUI.")
        print("Other available scripts:")
        print(cls._allModules())

    @staticmethod
    def gui():
        gui.main()

    @staticmethod
    def lookup():
        import hydrustools.cli.lookup
        hydrustools.cli.lookup.main()

def tryRun(cmd):
    if cmd in SubModules._allModules():
        getattr(SubModules, cmd)()
    else:
        print(f"Command {cmd!r} not supported. Options are: {SubModules._allModules()}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        sys.argv.pop(0)

        sys.exit(tryRun(cmd))

    else:
        sys.exit(gui.main())