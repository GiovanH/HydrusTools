import argparse
from functools import partial
import os

class HTArgparseFormatterDoc(argparse.RawDescriptionHelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            metavar, = self._metavar_formatter(action, default)(1)
            return metavar

        else:
            parts = []

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend(action.option_strings)

            # if the Optional takes a value, format is:
            #    -s ARGS, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)
                if len(action.option_strings) > 1:
                    parts.append(f"[{' | '.join(sorted(action.option_strings, key=len))}] {args_string}")
                else:
                    for option_string in action.option_strings:
                        parts.append('%s %s' % (option_string, args_string))

            return ', '.join(parts)

class HTArgparseFormatter(HTArgparseFormatterDoc, argparse.ArgumentDefaultsHelpFormatter):
    pass

HTApFmtCls: type[argparse.HelpFormatter]

# Don't write current development setting state to docs
if os.environ.get('htdocs'):
    HTApFmtCls = HTArgparseFormatterDoc
else:
    HTApFmtCls = HTArgparseFormatter

HTApFmtClsVerb = partial(HTApFmtCls, max_help_position=10)