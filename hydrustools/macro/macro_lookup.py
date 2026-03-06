
import argparse
import logging
import pprint
from requests.exceptions import HTTPError

from hydrustools import htlogging
from hydrustools.lookup.registry import MetadataActions, get_plugins, postprocessSuggestions

from .. import logic

plugin_registry = get_plugins()
print("Plugins", plugin_registry)

logger: logging.Logger

def apply_actions(actions: MetadataActions):
    file_id = actions.file_id

    if len(actions.add_downloader_tags or []) > 0:
        logger.info(f"Adding {len(actions.add_downloader_tags)} tags")
        logic.client.add_tags(
            file_ids=[file_id],
            service_keys_to_tags={
                logic.downloader_tags_service_key: actions.add_downloader_tags
            }
        )
        acted = True

    if len(actions.add_tags or []) > 0:
        logger.info(f"Adding {len(actions.add_tags)} tags")
        logic.client.add_tags(
            file_ids=[file_id],
            service_keys_to_tags={
                logic.local_tags_service_key: actions.add_tags
            }
        )
        acted = True

    if len(actions.add_urls or []) > 0:
        logger.info(f"Adding {len(actions.add_urls)} source urls")
        logic.client.associate_url(file_ids=[file_id], urls_to_add=actions.add_urls)
        acted = True


def get_tag_cache():
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

if __name__ == '__main__':
    htlogging.configure_logging()
    logger = logging.getLogger(__name__)

    print("Init")
    logic.init_client()

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--min-count-local", type=int, default=20)
    parser.add_argument("--min-count-download", type=int, default=1)
    parser.add_argument("--creator-always-local", action="store_true", default=True)
    parser.add_argument("--character-always-local", action="store_true", default=True)
    parser.add_argument("--no-downloader-tags", action="store_true")
    parser.add_argument("--underscores_to_spaces", action="store_true", default=True)

    args = parser.parse_args()

    print("Cache...")
    tag_cache = get_tag_cache()

    print("Query...")
    resp = logic.client.search_files(
        tags=args.query.split(' AND ') # type: ignore
    )
    matching_files = resp['file_ids']

    logic.client.add_popup(
        "lookup",
        files_label="Files",
        file_ids=matching_files
    )

    for image_id in matching_files:
        metadata: list[logic.FileMetadata] = logic.client.get_file_metadata(file_ids=[image_id], include_notes=True)['metadata']
        for image in metadata:
            for plugin in sorted(plugin_registry.values(), key=lambda p: p.priority):
                match = plugin.match(image)
                print(image["file_id"], plugin, match)
                if match:
                    try:
                        actions = plugin.suggest(image, print)
                    except Exception as e:
                        print("Error with", plugin, e)
                        continue

                    assert actions

                    actions = postprocessSuggestions(
                        actions,
                        tags_min_count_local=args.min_count_local,
                        tags_min_count_download=args.min_count_download,
                        tag_count_cache=tag_cache,

                        creator_tags_always_local=args.creator_always_local,
                        character_tags_always_local=args.character_always_local,

                        no_downloader_tags=args.no_downloader_tags,
                        underscores_to_spaces=args.underscores_to_spaces,
                    )

                    pprint.pprint(actions)

                    apply_actions(actions)

                    # os.exit()

