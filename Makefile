# CONFIGURATION
project_name=hydrustools
module_name=${project_name}

.PHONY: dev
dev:
	uv run python ${SRC_ROOT}/launcher.py

.PHONY: devdebug
devdebug:
	LOGLEVEL=DEBUG uv run python ${SRC_ROOT}/launcher.py

.PHONY: release
release: exe
	mv -v "dist/${project_name}.exe" "dist/${project_name}-$(GIT_TAG).exe"

.PHONY: git_tag
git_tag:
	git tag $(PYP_VER)

# IMPLEMENTATION

# Get GIT_TAG from environment variable, fallback to git command if not set
GIT_TAG ?= $(shell git describe --tags --abbrev=0 2>/dev/null || echo snapshot-$(date +'%Y-%m-%d'))

# Get expected version/tag from pyproject
PYP_VER = $(shell sed -n 's/^version = "\([^"]*\)".*/\1/p' pyproject.toml)

SRC_ROOT=.
MODULE_SRCS=$(wildcard ${project_name}/**/*.py ${project_name}/*.py)
SCRIPT_SRCS=$(wildcard ${SRC_ROOT}/*.py)
HOOK_SRCS=$(wildcard ${SRC_ROOT}/hooks/*)
# SCRIPT_SRCS=${SRC_ROOT}/gui.py

TARGET_EXES=\
	dist/${project_name}.exe
# 	$(patsubst ${SRC_ROOT}/%.py,dist/${project_name}-%.exe,${SCRIPT_SRCS})

.PHONY: all
all: lint test exe

.PHONY: watch
watch:
	nodemon --watch ${module_name}/ -e "py" --exec make dev

# Check
.PHONY: check
check: lint test

.PHONY: docs
docs: Docs_Tools.md Docs_CLI.md

Docs_Tools.md: autodoc.py launcher.py ${MODULE_SRCS}
	HTDOCS=true uv run python autodoc.py tools > $@

Docs_CLI.md: autodoc.py launcher.py ${MODULE_SRCS}
	HTDOCS=true uv run python autodoc.py cli > $@

.PHONY: lint
lint:
	-uv run --with python -m mypy --install-types --non-interactive --check-untyped-defs --follow-untyped-imports ${SCRIPT_SRCS}
	-uv run --with vulture ${SCRIPT_SRCS} ${MODULE_SRCS}

.PHONY: test
test:
	uv run python -m doctest ${SRC_ROOT}/*.py
	uv run python -c "import ${module_name}; import doctest; doctest.testmod(${module_name})"
	uv run python -m unittest

.PHONY: clean
clean:
	$(RM) -r .venv/ \
		build/ \
		dist/ \
		.mypy_cache/ \
		${SRC_ROOT}/__pycache__ ${SRC_ROOT}/*/__pycache__

# Build
.PHONY: exe
exe: ${TARGET_EXES}

dist/${project_name}.exe: ${SRC_ROOT}/launcher.py ${MODULE_SRCS} ${SCRIPT_SRCS} ${HOOK_SRCS} Makefile
	mkdir -p dist build
# 	cp icon.png build/
	uv run --with pyinstaller python -m PyInstaller \
		--name $(basename $(notdir $@)) \
		--paths src \
		--onefile \
		--console \
		--additional-hooks-dir=hooks \
		--hiddenimport charset_normalizer \
		--distpath dist \
		--workpath build \
		--specpath build \
		$<

# 		--icon "icon.png" \
# 		--add-data="icon.png:." \
