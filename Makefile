# CONFIGURATION
project_name=hydrustools
module_name=${project_name}

.PHONY: dev
dev: venv
# 	(cd src && ../${VPYTHON} gui.py)
	${VPYTHON} ${SRC_ROOT}/launcher.py

.PHONY: release
release: exe
	mv -v "dist/hydrustools.exe" "dist/hydrustools-$(GIT_TAG).exe"

# IMPLEMENTATION

VPYTHON=venv/Scripts/python.exe

SRC_ROOT=.
MODULE_SRCS=$(shell find ${project_name} -type f -name '*.py')
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
check: venv lint test

.PHONY: docs
docs: Docs_Tools.md Docs_CLI.md

Docs_Tools.md: venv autodoc.py launcher.py ${MODULE_SRCS}
	${VPYTHON} autodoc.py tools > $@

Docs_CLI.md: venv autodoc.py launcher.py ${MODULE_SRCS}
	${VPYTHON} autodoc.py cli > $@

.PHONY: lint
lint: venv
# 	-${VPYTHON} -m mypy ${SRC_ROOT}/${module_name}
	-${VPYTHON} -m mypy *.py
	-vulture ${SRC_ROOT}/*.py

.PHONY: test
test: venv
	${VPYTHON} -m doctest ${SRC_ROOT}/*.py
	${VPYTHON} -c "import ${module_name}; import doctest; doctest.testmod(${module_name})"
	${VPYTHON} -m unittest

.PHONY: clean
clean:
	$(RM) -r venv/ \
		build/ \
		dist/ \
		.mypy_cache/ \
		${SRC_ROOT}/__pycache__ ${SRC_ROOT}/*/__pycache__

# Env
venv: venv/pyvenv.cfg
venv/pyvenv.cfg: requirements.txt
	python3 -m venv ./venv
	${VPYTHON} -m pip install -r requirements.txt
	${VPYTHON} -m pip install pyinstaller vulture mypy
	-${VPYTHON} -m mypy --install-types --non-interactive
# 	-${VPYTHON} -m mypy --install-types

# Build
.PHONY: exe
exe: venv ${TARGET_EXES}

dist/${project_name}.exe: ${SRC_ROOT}/launcher.py ${MODULE_SRCS} ${SCRIPT_SRCS} ${HOOK_SRCS} Makefile
	mkdir -p dist build
# 	cp icon.png build/
	${VPYTHON} -m PyInstaller \
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

# Get GIT_TAG from environment variable, fallback to git command if not set
GIT_TAG ?= $(shell git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0-dev")
