import sys

from hydrustools.utils import htlogging


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

    # @staticmethod
    # def gui():
    #     gui.main()

    @staticmethod
    def lookup():
        import hydrustools.cli.lookup
        hydrustools.cli.lookup.main()

    @staticmethod
    def convert_booru():
        import hydrustools.utils.convert_booru
        hydrustools.utils.convert_booru.main()

    @staticmethod
    def todogroup():
        import hydrustools.cli.todogroup
        hydrustools.cli.todogroup.main()

    @staticmethod
    def bubblegroup():
        import hydrustools.cli.bubblegroup
        hydrustools.cli.bubblegroup.main()


def tryRun(cmd):
    if cmd in SubModules._allModules():
        getattr(SubModules, cmd)()
    else:
        print(f"Command {cmd!r} not supported. Options are: {SubModules._allModules()}")
        print("Invoke with (venv) ./HydrusTools [module] or")
        print("Invoke with (venv) python3 launcher.py [module] (dev)")

if __name__ == '__main__':
    htlogging.configure_logging()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        sys.argv.pop(0)

        sys.exit(tryRun(cmd))

    else:
        from hydrustools import gui
        sys.exit(gui.main())