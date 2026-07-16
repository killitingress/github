SHELL := /bin/sh

PANDOC ?= pandoc
DOCS_DIR := docs/confluence

MARKDOWN_FILES := $(shell find $(DOCS_DIR) -type f -name '*.md' -print | sort)
DOCX_FILES := $(MARKDOWN_FILES:.md=.docx)

.DEFAULT_GOAL := docs

.PHONY: docs check-pandoc list-docs clean-docs

## Erstellt fuer jede Markdown-Datei unter docs/confluence/ eine Word-Datei.
docs: $(DOCX_FILES)
	@printf 'Erstellt: %s Word-Datei(en) unter %s/\n' "$(words $(DOCX_FILES))" "$(DOCS_DIR)"

check-pandoc:
	@command -v "$(PANDOC)" >/dev/null 2>&1 || { \
		printf 'Fehler: pandoc wurde nicht gefunden. Bitte pandoc installieren oder PANDOC=/pfad/zu/pandoc setzen.\n' >&2; \
		exit 1; \
	}

$(DOCS_DIR)/%.docx: $(DOCS_DIR)/%.md | check-pandoc
	$(PANDOC) \
		--from=gfm \
		--to=docx \
		--standalone \
		--metadata=lang:de-DE \
		--resource-path="$(dir $<):$(DOCS_DIR):." \
		--output="$@" \
		"$<"

## Zeigt alle Quell- und Zieldateien an.
list-docs:
	@$(foreach source,$(MARKDOWN_FILES),printf '%s -> %s\n' '$(source)' '$(source:.md=.docx)';)

## Entfernt ausschliesslich die generierten Word-Dateien.
clean-docs:
	rm -f $(DOCX_FILES)
