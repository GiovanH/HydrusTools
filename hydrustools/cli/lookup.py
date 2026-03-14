
import argparse
import logging
import pprint
from functools import partial

from hydrustools import htlogging
from hydrustools.component import querylang
from hydrustools.lookup.registry import MetadataActions, get_plugins, postprocessSuggestions

from .. import logic
from ..util import timer

plugin_registry = get_plugins()

logger: logging.Logger

def apply_actions(actions: MetadataActions, image: logic.FileMetadata | None = None):
    file_id = actions.file_id

    # TODO: If image passed, apply the actions there also

    if actions.add_downloader_tags and len(actions.add_downloader_tags) > 0:
        logger.info(f"Adding {len(actions.add_downloader_tags)} tags")
        logic.client.add_tags(
            file_ids=[file_id],
            service_keys_to_tags={
                logic.downloader_tags_service_key: actions.add_downloader_tags
            } # type: ignore
        )

    if actions.add_tags and len(actions.add_tags) > 0:
        logger.info(f"Adding {len(actions.add_tags)} tags")
        logic.client.add_tags(
            file_ids=[file_id],
            service_keys_to_tags={
                logic.local_tags_service_key: actions.add_tags
            } # type: ignore
        )

    if actions.add_urls and len(actions.add_urls or []) > 0:
        logger.info(f"Adding {len(actions.add_urls)} source urls")
        logic.client.associate_url(file_ids=[file_id], urls_to_add=actions.add_urls)

        if image:
            # TODO: This doesn't apply url transformations like hydrus does
            image['known_urls'].extend(actions.add_urls)

    if actions.add_notes:
        raise NotImplementedError()


def get_tag_cache() -> dict[str, int]:
    tag_count_cache = {}
    all_tags = logic.search_tags_re("*", subpattern=None)
    all_tags_set = {ti.value for ti in all_tags}
    tag_count_cache = {ti.value: ti.count for ti in all_tags}

    sibling_resp = logic.get_sibling_ideal_targets([*all_tags_set])

    all_relationships: dict[str, logic.SiblingInfo] = {
        **{
            s: si
            for si in
            sibling_resp
            for s in si.siblings
        }
    }

    for tag, si in all_relationships.items():
        ideal = si.ideal_tag

        # Quick and dirty, not completely accurate
        # Would need to loop multiple times and make sure each sibling group shared a pool, etc
        if tag_count_cache.get(ideal) != tag_count_cache.get(tag):
            total = tag_count_cache.get(ideal, 0) + tag_count_cache.get(tag, 0)
            tag_count_cache[tag] = total
            tag_count_cache[ideal] = total

    return tag_count_cache

class formatter(argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    pass

def main():
    global logger
    logger = logging.getLogger(__name__)

    logic.init_client()

    plugin_repr_list = [
        f"{k} ({v.name})"
        for k, v in plugin_registry.items()
    ]

    nl = "\n"
    parser = argparse.ArgumentParser(
        usage="lookup PLUGINS QUERY [FLAGS]...",
        description="""Use lookup plugins to merge discovered metadata into hydrus files. Takes a hydrus query and plugin list and merges metadata into hydrus according to passed options. Some plugins may have additional ini configuration.

Example invocations:
> lookup 'Saucenao' 'system:no urls AND system:limit=100'
> lookup 'grabberComMd5Plugin,grabberComPlugin' 'system:no urls AND system:limit=100'
> lookup 'all' '-character:* AND -series:* AND system:no urls'
""",
        epilog=f"Available plugins: \n{nl.join(plugin_repr_list)}",
        formatter_class=partial(formatter, max_help_position=10)
    )
    parser.add_argument("plugins", help="Comma-separated unordered set of plugins to use, or 'all'.")
    parser.add_argument("query", help="Hydrus image query")

    parser.add_argument("--min-count-local", type=int, default=20,
        help="Number of times this tag must already exist in tag repo to be added")
    parser.add_argument("--min-count-download", type=int, default=1,
        help="Number of times this tag must already exist in tag repo to be added")

    parser.add_argument("--creator-always-local",
        action=argparse.BooleanOptionalAction, default=True,
        help="Always include creator: tags regardless of count")
    parser.add_argument("--character-always-local",
        action=argparse.BooleanOptionalAction, default=True,
        help="Always include character: tags regardless of count")
    parser.add_argument("--downloader-tags",
        action=argparse.BooleanOptionalAction, default=False,
        help="Move all downloader tags to info-only")
    parser.add_argument("--underscores-to-spaces",
        action=argparse.BooleanOptionalAction, default=True,
        help="Convert underscores to spaces in tags")

    args = parser.parse_args()

    selected_plugins = args.plugins.split(',')

    logger.info(f"Querying hydrus {args.query!r}...")
    resp = logic.client.search_files(
        tags=querylang.parse_sl_query(args.query) # type: ignore
    )
    matching_files = resp['file_ids']

    logic.client.add_popup(
        "lookup",
        files_label=repr(args.query),
        file_ids=matching_files
    )

    plugin_list = []
    for plugin_key, plugin in sorted(plugin_registry.items(), key=lambda t: t[1].priority):
        if selected_plugins == ['all']:
            plugin_list.append(plugin)
        elif any(plugin.name == s for s in selected_plugins) or any(plugin_key.endswith(suffix) for suffix in selected_plugins):
            logger.debug("%s has suffix in %s", plugin_key, selected_plugins)
            plugin_list.append(plugin)

    logger.info("Plugin list: %s from %s", plugin_list, selected_plugins)

    logger.info("Populating tag data...")
    tag_cache: dict | None = None # get_tag_cache()

    # TODO: Plugins don't have information provided by previous plugins in the same run

    for image_id in matching_files:
        metadata: list[logic.FileMetadata] = logic.client.get_file_metadata(file_ids=[image_id], include_notes=True)['metadata']
        for image in metadata:
            for plugin in plugin_list:
                match = plugin.match(image)
                logger.debug("%s %s %s", image["file_id"], plugin, match)
                if match:
                    try:
                        with timer(f"{plugin.name}: get suggestions"):
                            actions = plugin.suggest(image, print)
                    except Exception:
                        logger.exception(f"Error running plugin {plugin} on image {image['file_id']}")
                        continue

                    assert actions

                    if not actions.has_any():
                        continue

                    tag_cache = tag_cache or get_tag_cache()

                    actions = postprocessSuggestions(
                        actions,
                        tags_min_count_local=args.min_count_local,
                        tags_min_count_download=args.min_count_download,
                        tag_count_cache=tag_cache,

                        creator_tags_always_local=args.creator_always_local,
                        character_tags_always_local=args.character_always_local,

                        no_downloader_tags=(not args.downloader_tags),
                        underscores_to_spaces=args.underscores_to_spaces,
                    )


                    remaining = actions.remaining_for(image)

                    if not remaining.has_any():
                        continue

                    logger.info(pprint.pformat(remaining))

                    apply_actions(remaining, image)

                    # os.exit()



if __name__ == '__main__':
    htlogging.configure_logging()
    main()