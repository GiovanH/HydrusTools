## CLI Utilities

### `bubblegroup`

`python3 launcher.py bubblegroup`

```text
usage: bubblegroup [-h] [--ignore-namespaces IGNORE_NAMESPACES] [--min-size MIN_SIZE] [--max-size MAX_SIZE]
                   [--debug]
                   query

positional arguments:
  query                 Hydrus image query

options:
  -h, --help            show this help message and exit
  --ignore-namespaces IGNORE_NAMESPACES
  --min-size MIN_SIZE
  --max-size MAX_SIZE
  --debug
```
### `help`

`python3 launcher.py help`

```text
HydrusTools launcher.
With no arguments, launches the GUI.
Other available scripts:
['bubblegroup', 'help', 'lookup']
```
### `lookup`

`python3 launcher.py lookup`

```text
usage: lookup [-h] [--min-count-local MIN_COUNT_LOCAL] [--min-count-download MIN_COUNT_DOWNLOAD]
              [--creator-always-local | --no-creator-always-local]
              [--character-always-local | --no-character-always-local]
              [--downloader-tags | --no-downloader-tags]
              [--underscores-to-spaces | --no-underscores-to-spaces]
              plugins query

positional arguments:
  plugins
          Comma-separated unordered set of plugins to use, or 'all'.
  query   Hydrus image query

options:
  -h, --help
          show this help message and exit
  --min-count-local MIN_COUNT_LOCAL
          Number of times this tag must already exist in tag repo to be added (default: 20)
  --min-count-download MIN_COUNT_DOWNLOAD
          Number of times this tag must already exist in tag repo to be added (default: 1)
  --creator-always-local, --no-creator-always-local
          Always include creator: tags regardless of count (default: True)
  --character-always-local, --no-character-always-local
          Always include characters: tags regardless of count (default: True)
  --downloader-tags, --no-downloader-tags
          Move all downloader tags to info-only (default: False)
  --underscores-to-spaces, --no-underscores-to-spaces
          Convert underscores to spaces in tags (default: True)

Available plugins: 
hydrustools.lookup.e621.e621Plugin
hydrustools.lookup.grabbercom.grabberComMd5Plugin
hydrustools.lookup.grabbercom.grabberComPlugin
hydrustools.lookup.saucenao.sauceNaoPlugin
```
