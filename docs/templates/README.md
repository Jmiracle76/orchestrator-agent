# Templates

Each template starts with a metadata header used by automation tooling.

Supported metadata fields:
- `doc_type`: document type (e.g., `requirements`, `research`, `planning`)
- `doc_format`: document format (e.g., `markdown`)
- `version`: format version (from the `doc_format` marker)

Example:
```md
<!-- meta:doc_type value="requirements" -->
<!-- meta:doc_format value="markdown" version="1.0" -->
```
