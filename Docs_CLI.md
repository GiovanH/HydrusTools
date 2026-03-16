## CLI Utilities

### `bubblegroup`

`./HydrusTools bubblegroup` (compiled)  
`(venv) python3 launcher.py bubblegroup` (dev)  

```text
usage: bubblegroup [-h] [--ignore-namespaces IGNORE_NAMESPACES] [--min-size MIN_SIZE] [--max-size MAX_SIZE]
                   [--debug]
                   query

WIP!

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

`./HydrusTools help` (compiled)  
`(venv) python3 launcher.py help` (dev)  

```text
HydrusTools launcher.
With no arguments, launches the GUI.
Other available scripts:
['bubblegroup', 'help', 'lookup']
```
### `lookup`

`./HydrusTools lookup` (compiled)  
`(venv) python3 launcher.py lookup` (dev)  

```text
usage: lookup PLUGINS QUERY [FLAGS]...

Use lookup plugins to merge discovered metadata into hydrus files. Takes a hydrus query and plugin list and merges metadata into hydrus according to passed options. Some plugins may have additional ini configuration.

Example invocations:
> lookup 'Saucenao' 'system:no urls AND system:limit=100'
> lookup 'grabberComMd5Plugin,grabberComPlugin' 'system:no urls AND system:limit=100'
> lookup 'all' '-character:* AND -series:* AND system:no urls'

positional arguments:
  plugins
          Comma-separated unordered set of plugins to use, or 'all'.
  query   Hydrus image query

options:
  -h, --help
          show this help message and exit

Config Overrides:
  Overrides for specific postprocessing parameters. Default values come from your INI configuration under "[Lookup]".

  [--mcl | --min-count-local] MIN_COUNT_LOCAL
          Number of times this tag must already exist in tag repo to be added (default: 20)
  [--mcd | --min-count-download] MIN_COUNT_DOWNLOAD
          Number of times this tag must already exist in tag repo to be added (default: 1)
  [--aln | --always-local-namespaces] ALWAYS_LOCAL_NAMESPACES
          Always apply these tags to the local tag repo regardless of count (default:
          creator,character,title,series,rating)
  [--nsw | --tag-namespace-whitelist] TAG_NAMESPACE_WHITELIST
          Only add tags that lookup plugins report as having these namespaces (default: )
  [--btl | --blacklist-tags-from-local] BLACKLIST_TAGS_FROM_LOCAL
          Always apply these tags to the local tag repo regardless of count (default: anthro,balls,butt)
  --underscores-to-spaces, --no-underscores-to-spaces
          Convert underscores to spaces in tags (default: True)

Available plugins: 
hydrustools.lookup.e621.e621Plugin (e621)
hydrustools.lookup.grabbercom.grabberComMd5Plugin (Grabber by hash)
hydrustools.lookup.grabbercom.grabberComPlugin (Grabber by source)
hydrustools.lookup.saucenao.sauceNaoPlugin (Saucenao)
```
