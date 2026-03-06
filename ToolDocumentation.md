## Tag Management

### Tag Manager

Bulk search and edit tags.

Tag Query searches the tag list, regex refinment filters further.

AND/OR opens search page for all images with the selected tags.

"Map Siblings to Namespace" prompts for a namespace, then gives you an importable clipboard setting that will add the ideal sibling {namespace}:{tag} for each selected {tag}.

"Delete selected tag" removes all occurrences of the selected tags from all images.
    

### Image Inspector

Manually tag images and edit metadata.

First, select a group of images with the image search window. You can edit the current selection by clicking "Pick Images".

Focus the text entry field under "Add Tags" for fully-automatic operation:

Left/Right: Navigate
F5: Refresh all metadata
Ctrl-E: Toggle archive/inbox
Ctrl-D: Toggle trashed
Return: DWIM

Adjust Do What I Mean behavior using the checkboxes on the right-hand panel.

Type in the box to fuzzy-search for tags. Tag changes autosave if Autosave is checked, otherwise you will need to click Save, or use a DWIM action.

Fuzzy-search notes:
Tags
If tagname is attached to the image, "-tagname" will remove it.


### Tree Visualizer

Not yet implemented.

### Localize (Swapped) Character Names

The find_localchars macro searches all known character: tags for names that appear in different orders. It will group these by Series and collate them in a SiblingAdderWindow. Select the ideal version and the SiblingAdderWindow will export a relationship set.
    

## Tag Relationships

### Flatten Tab Siblings

Flatten tag siblings.

Select the specific relationships to flatten and click the flatten button to commit changes.

In effect, this finds all images with the source tag directly specified and replaces that with the ideal tag as defined by the sibling relationship.

Presearch searches Hydrus for tags (* will only work if specified in the tag repo settings). Refinement filters that list to only tags matching the given expression. Presearch is fastest!
    

### Find Implicit Parents

Find Implicit Parents

Some tags have logical implications that are already captured in the data but aren't added as automatic parent relationships yet. This detects those. It's designed to find characters that are almost always found in a specific series, but it can be used with other namespaces as well.

Parent prefix filter is the tag prefix defining the kind of parent being searched for. Recommendations must have this prefix, and tags that already have a parent with this prefix are considered categorized already.

Child tag query is the search for child tags to examine. Since this is a search, you can include ":*" if your API supports it.

Minimum count is the minimum number of times an orphan tag needs to appear to be considered. You can use this to filter out infrequent tags to speed up search time.

Parent factor defines how much more common a parent tag needs to be than other parent tags to be considered a match. Any potential parent tag needs to be this factor larger than other matching parent tags to be considered.

### Detect Tags' Namespaced Equivalents

Macro: Search for tags that are also present in a namespace and suggest adding sibling relationships for them.
    

### Parent Series from Character Parens

Not yet implemented.

## Search

### Regex Note Search

Search the contents of notes.

Note title specifies the title of the note to search.
This will also try to match "incremented" titles caused by metadata merge, so "filename" also matches "filename (1)", etc.

Search pattern specifies the regular expression used. By default this has to match the start of the string, but the partial option will try to find the pattern anywhere in the note body.

Once the search is complete, results are sent to Hydrus in a notification. Click the button in Hydrus to open the page with search results.
    

## Metadata Lookup

### Image Metadata Lookup

Similar to the Image Inspector, but looks up image metadata based on lookup plugins.

Heavy work-in-progress

### Extract Creator Tags from Notes


    

### Import Downloader Tags In Local Repo

Not yet implemented.

### Extract Tags from Note Regex

Not yet implemented.

## Filename Macros

### Extract page numbers from filename note

Macro: Searches filename and filepath notes for something that looks like a page number, then proposes adding the appropriate page: tag.
    

## Unsorted and WIP

### Relationship Tree Browser

Work in progress. Browse tag relationships.

### Mail Rules

Not yet implemented.

### Synchronize Alternate Meta (WIP)

Interactively synchronize metadata between alternate images.

An automatic search will gather image sets whose tags don't all already match each other in the column on the left.

Select a set to preview the images. This will load a combined set of tags into the central editor interface, which you can modify before merging if desired.

Clicking merge will add the specified tags to all images in the set.
    

