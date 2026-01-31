# CONFIGURATION
project_name=hydrustools
module_name=${project_name}

.PHONY: test
dev: venv
# 	(cd src && ../${VPYTHON} gui.py)
	${VPYTHON} ${SRC_ROOT}/launcher.py

.PHONY: release
release: exe
	mv -v "dist/hydrustools-launcher.exe" "dist/hydrustools-launcher-$(GIT_TAG).exe"

# IMPLEMENTATION

VPYTHON=venv/Scripts/python.exe

SRC_ROOT=.
MODULE_SRCS=$(wildcard ${SRC_ROOT}/*/*.py)
SCRIPT_SRCS=$(wildcard ${SRC_ROOT}/*.py)
# SCRIPT_SRCS=${SRC_ROOT}/gui.py

TARGET_EXES=\
	$(patsubst ${SRC_ROOT}/%.py,dist/${project_name}-%.exe,${SCRIPT_SRCS})

.PHONY: all
all: lint test exe

.PHONY: watch
watch:
	nodemon --watch hydrustools/ -e "py" --exec make dev

# Check
.PHONY: check
check: venv lint test

.PHONY: lint
lint: venv
# 	-${VPYTHON} -m mypy ${SRC_ROOT}/${module_name}
	-(cd src && ../${VPYTHON} -m mypy *.py)
	-vulture ${SRC_ROOT}/*.py

.PHONY: test
test: venv
	${VPYTHON} -m doctest ${SRC_ROOT}/*.py
	(cd src && ../${VPYTHON} -c "import ${module_name}; import doctest; doctest.testmod(${module_name})")

.PHONY: clean
clean:
	$(RM) -r venv/ \
		build/ \
		dist/ \
		.mypy_cache/ \
		${SRC_ROOT}/__pycache__ ${SRC_ROOT}/*/__pycache__

# Env
venv: requirements.txt
	python3 -m venv ./venv
	${VPYTHON} -m pip install -r requirements.txt
	${VPYTHON} -m pip install pyinstaller vulture mypy
	-${VPYTHON} -m mypy --install-types --non-interactive

# Build
.PHONY: exe
exe: venv ${TARGET_EXES}

dist/${project_name}-%.exe: ${SRC_ROOT}/%.py ${MODULE_SRCS}
	mkdir -p dist build
# 	cp icon.png build/
	${VPYTHON} -m PyInstaller \
		--name $(basename $(notdir $@)) \
		--paths src \
		--onefile \
		--console \
		--distpath dist \
		--workpath build \
		--specpath build \
		$<

# 		--icon "icon.png" \
# 		--add-data="icon.png:." \

# Get GIT_TAG from environment variable, fallback to git command if not set
GIT_TAG ?= $(shell git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0-dev")
