
import argparse
import functools
import logging
import pprint

from hydrustools.utils.argparse_formatter import HTApFmtClsVerb

from ..lookup.registry import LookupSettings, MetadataActions, get_plugins, postprocessSuggestions
from ..utils import htlogging, hydrus, querylang
from ..utils.util import timer

plugin_registry = get_plugins()

logger: logging.Logger

def apply_actions(actions: MetadataActions, image: hydrus.FileMetadata | None = None):
    file_id = actions.file_id

    # TODO: If image passed, apply the actions there also

    if actions.add_downloader_tags and len(actions.add_downloader_tags) > 0:
        logger.info(f"Adding {len(actions.add_downloader_tags)} tags")
        hydrus.client.add_tags(
            file_ids=[file_id],
            service_keys_to_tags={
                hydrus.downloader_tags_service_key: actions.add_downloader_tags
            }
        )

    if actions.add_tags and len(actions.add_tags) > 0:
        logger.info(f"Adding {len(actions.add_tags)} tags")
        hydrus.client.add_tags(
            file_ids=[file_id],
            service_keys_to_tags={
                hydrus.local_tags_service_key: actions.add_tags
            }
        )

    if actions.add_urls and len(actions.add_urls or []) > 0:
        logger.info(f"Adding {len(actions.add_urls)} source urls")
        hydrus.client.associate_url(file_ids=[file_id], urls_to_add=actions.add_urls)

        if image:
            # TODO: This doesn't apply url transformations like hydrus does
            image['known_urls'].extend(actions.add_urls)

    if actions.add_notes:
        all_notes = functools.reduce(lambda acc, d: {**acc, **d}, actions.add_notes)
        logger.info(f"Adding notes {all_notes}")
        hydrus.client.set_notes(
            file_id=file_id,
            notes=all_notes,
            merge_cleverly=True,
            extend_existing_note_if_possible=True
        )
        # raise NotImplementedError()


def get_tag_cache() -> dict[str, int]:
    logger.info("Populating tag data (to make postprocessing decisions)...")
    tag_count_cache = {}
    all_tags = hydrus.search_tags_re("*", subpattern=None)
    all_tags_set = {ti.value for ti in all_tags}
    tag_count_cache = {ti.value: ti.count for ti in all_tags}

    sibling_resp = hydrus.get_relationship_info([*all_tags_set])

    all_relationships: dict[str, hydrus.RelationshipInfo] = {
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

def main():
    global logger
    logger = logging.getLogger(__name__)

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
        formatter_class=HTApFmtClsVerb
    )
    parser.add_argument("plugins", help="Comma-separated unordered set of plugins to use, or 'all'.")
    parser.add_argument("query", help="Hydrus image query")

    parser_overrides = parser.add_argument_group('Config Overrides', 'Overrides for specific postprocessing parameters. Default values come from your INI configuration under "[Lookup]".')

    parser_overrides.add_argument("--min-count-local", "--mcl",
        type=int, default=LookupSettings.min_count_local,
        help="Number of times this tag must already exist in tag repo to be added. 0 to allow all, -1 to deny all.")
    parser_overrides.add_argument("--min-count-download", "--mcd",
        type=int, default=LookupSettings.min_count_download,
        help="Number of times this tag must already exist in tag repo to be added. 0 to allow all, -1 to deny all.")

    parser_overrides.add_argument("--always-local-namespaces", "--aln",
        default=','.join(LookupSettings.always_local_namespaces),
        help="Always apply these tags to the local tag repo regardless of count")
    parser_overrides.add_argument("--tag-namespace-whitelist", "--nsw",
        default=','.join(LookupSettings.tag_namespace_whitelist),
        help="Only add tags that lookup plugins report as having these namespaces")
    parser_overrides.add_argument("--blacklist-tags-from-local", "--btl",
        default=','.join(LookupSettings.blacklist_tags_from_local),
        help="Never allow these tags in the local tag repo regardless of count")
    parser_overrides.add_argument("--underscores-to-spaces",
        action=argparse.BooleanOptionalAction,
        default=LookupSettings.underscores_to_spaces,
        help="Convert underscores to spaces in tags")

    args = parser.parse_args()

    if args.min_count_local == -1:
        args.min_count_local = None
    if args.min_count_download == -1:
        args.min_count_local = None

    hydrus.init_client()

    selected_plugins: list[str] = args.plugins.split(',')
    always_local_namespaces: list[str] = args.always_local_namespaces.split(',')
    tag_namespace_whitelist: list[str] | None = [f for f in args.tag_namespace_whitelist.split(',') if f] or None
    blacklist_tags_from_local: list[str] = args.always_local_namespaces.split(',')


    logger.info(f"Querying hydrus {args.query!r}...")
    resp = hydrus.client.search_files(
        tags=querylang.parse_sl_query(args.query)
    )
    matching_files = resp['file_ids']

    hydrus.client.add_popup(
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

    tag_cache: dict | None = None # get_tag_cache()

    for image_id in matching_files:
        metadata: list[hydrus.FileMetadata] = hydrus.client.get_file_metadata(file_ids=[image_id], include_notes=True)['metadata']
        for image in metadata:
            matched = False
            for plugin in plugin_list:
                match = plugin.match(image)
                logger.debug("%s %s %s", image["file_id"], plugin, match)
                if match:
                    matched = True
                    try:
                        with timer(f"{plugin.name}: get suggestions"):
                            actions = plugin.suggest(image, print)
                    except Exception:
                        logger.exception(f"Error running plugin {plugin} on image {image['file_id']}")
                        continue

                    assert actions

                    logger.debug("Pre-postprocess %s", pprint.pformat(actions))
                    if not actions.has_any():
                        continue

                    if not tag_cache:
                        tag_cache = get_tag_cache()

                    actions = postprocessSuggestions(
                        actions,
                        tags_min_count_local=args.min_count_local,
                        tags_min_count_download=args.min_count_download,
                        tag_count_cache=tag_cache,

                        always_local_namespaces=always_local_namespaces,

                        tag_namespace_whitelist=tag_namespace_whitelist,
                        blacklist_tags_from_local=blacklist_tags_from_local,
                        # no_downloader_tags=(not args.maybe_to_downloader),
                        underscores_to_spaces=args.underscores_to_spaces,
                    )

                    # logger.debug("Postprocessed %s", pprint.pformat(actions))

                    remaining = actions.remaining_for(image)

                    if not remaining.has_any():
                        logger.debug("Remaining does not have any, %s", pprint.pformat(remaining))
                        continue

                    logger.info(pprint.pformat(remaining))

                    apply_actions(remaining, image)

            if not matched:
                logger.info(f"No plugin matches for {image['file_id']}")



if __name__ == '__main__':
    htlogging.configure_logging()
    main()