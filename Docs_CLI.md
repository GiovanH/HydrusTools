## CLI Utilities

### `launcher.py`

`usage: launcher.py {bubblegroup, convert_booru, lookup, todogroup}
`

```text
usage: launcher.py [-h] [--version] TOOL ...

positional arguments:
  TOOL        Main tool. Options: {bubblegroup, convert_booru, lookup,
              todogroup}

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit
```

### `bubblegroup`

```text
usage: launcher.py bubblegroup [-h] [--ignore-namespaces IGNORE_NAMESPACES]
                               [--min-size MIN_SIZE] [--max-size MAX_SIZE]
                               [--sort-on-attributes | --no-sort-on-attributes]
                               [--expand-groups | --no-expand-groups]
                               [--describe-moves] [--alias-tags]
                               [--add-not-tags] [--force] [--debug]
                               [query]

positional arguments:
  query                 Hydrus image query

options:
  -h, --help            show this help message and exit
  --ignore-namespaces IGNORE_NAMESPACES
  --min-size MIN_SIZE   :
  --max-size MAX_SIZE   :
  --sort-on-attributes, --no-sort-on-attributes
                        Include extra sorting attributes for audio/video, tag
                        count, etc
  --expand-groups, --no-expand-groups
                        Internal algorithm tweak
  --describe-moves
  --alias-tags
  --add-not-tags
  --force               Force groups to work even if there is no logical
                        division by dividing along arbitrary lines.
  --debug
```

### `convert_booru`

Convert booru between semantic and booru-formatted URLs, with different formatters used for different booru types, which are mapped to different server types.

This comes pre-supplied with a few common models but will also attempt to use existing configuration data to load booru models.
The currently implemented metadata sources are:
- Grabber (Known sites)
- Grabber (XML format)

This is the CLI utility. This file can also be used as a python library.

```text
usage: launcher.py convert_booru [-h] [-m LOAD_MODELS] ACTION ...

positional arguments:
  ACTION
    get_files           Get urls to files as a json list of strings.
    get_search          Get the URL for a search. Returns one URL joining all
                        tags.
    dump_models         Load all available models from useru context, then
                        write model info to models.json

options:
  -h, --help            show this help message and exit
  [-m | --load-models] LOAD_MODELS
                        Path to a models file. These models will be added to
                        the preinstalled models and any discovered models.
```

### `convert_booru get_files`

```text
usage: launcher.py convert_booru get_files [-h] [-g]
                                           domain file_ids [file_ids ...]

positional arguments:
  domain                Web domain of service
  file_ids              Numerical file IDs

options:
  -h, --help            show this help message and exit
  -g, --gallerydl-hints
                        Prepend output URLs with a gallerydl extractor prefix,
                        if known.
```

### `convert_booru get_search`

```text
usage: launcher.py convert_booru get_search [-h] [-g] domain tags [tags ...]

positional arguments:
  domain                Web domain of service
  tags

options:
  -h, --help            show this help message and exit
  -g, --gallerydl-hints
                        Prepend output URLs with a gallerydl extractor prefix,
                        if known.
```

### `convert_booru dump_models`

```text
usage: launcher.py convert_booru dump_models [-h]

options:
  -h, --help  show this help message and exit
```

### `lookup`

Use lookup plugins to merge discovered metadata into hydrus files. Takes a hydrus query and plugin list and merges metadata into hydrus according to passed options. Some plugins may have additional ini configuration.

Example invocations:
> lookup 'Saucenao' 'system:no urls AND system:limit=100'
> lookup 'grabberComMd5Plugin,grabberComPlugin' 'system:no urls AND system:limit=100'
> lookup 'all' '-character:* AND -series:* AND system:no urls'


```text
usage: launcher.py lookup [-h] [--min-count-local MIN_COUNT_LOCAL]
                          [--min-count-download MIN_COUNT_DOWNLOAD]
                          [--always-local-namespaces ALWAYS_LOCAL_NAMESPACES]
                          [--tag-namespace-whitelist TAG_NAMESPACE_WHITELIST]
                          [--blacklist-tags-from-local BLACKLIST_TAGS_FROM_LOCAL]
                          [--underscores-to-spaces | --no-underscores-to-spaces]
                          plugins query

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
          Number of times this tag must already exist in tag repo to be added.
          0 to allow all, -1 to deny all.
  [--mcd | --min-count-download] MIN_COUNT_DOWNLOAD
          Number of times this tag must already exist in tag repo to be added.
          0 to allow all, -1 to deny all.
  [--aln | --always-local-namespaces] ALWAYS_LOCAL_NAMESPACES
          Always apply these tags to the local tag repo regardless of count
  [--nsw | --tag-namespace-whitelist] TAG_NAMESPACE_WHITELIST
          Only add tags that lookup plugins report as having these namespaces
  [--btl | --blacklist-tags-from-local] BLACKLIST_TAGS_FROM_LOCAL
          Never allow these tags in the local tag repo regardless of count
  --underscores-to-spaces, --no-underscores-to-spaces
          Convert underscores to spaces in tags
```

Available plugins: 
hydrustools.lookup.e621.e621Plugin (e621)
hydrustools.lookup.grabbercom.grabberComMd5Plugin (Grabber by hash)
hydrustools.lookup.grabbercom.grabberComPlugin (Grabber by source)
hydrustools.lookup.saucenao.sauceNaoPlugin (Saucenao)

### `todogroup`

```text
usage: launcher.py todogroup [-h] [-d] [tags ...]

positional arguments:
  tags               List of tags. You can also provide an OR query and HT
                     will try to parse it into tags.

options:
  -h, --help         show this help message and exit
  -d, --descendants  Also collect any descendants of the supplied tags
```

