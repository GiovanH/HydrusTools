PYTHON=py -3

exec_targets=\
	HydrusTools.exe

PY_SRCS=$(wildcard hydrustools/*.py)
PY_ENTRYPOINT=launcher.py
MODULE_NAME=hydrustools

all: exe

.PHONY: test
test:
	${PYTHON} sort.py --base test

.PHONY: watch
watch:
	nodemon --watch hydrustools/ -e "py" --exec ${PYTHON} launcher.py

.PHONY: lint
lint: requirements
	-python3 -m mypy $(PY_SRCS)
	-vulture $(PY_SRCS)

requirements: requirements.txt
	${PYTHON} -m pip install -r requirements.txt
	touch requirements

clean:
	$(RM) -r __pycache__
	$(RM) -r build
	$(RM) -r dist/
	$(RM) -r litedist/
	$(RM) -r bin/

exe: requirements $(addprefix bin/,${exec_targets})

bin/HydrusTools.exe: $(PY_SRCS)
	mkdir -p bin
	${PYTHON} -m PyInstaller \
		--onefile \
		--console \
		--distpath bin \
		--workpath build \
		--specpath build \
		--collect-submodules ${MODULE_NAME} \
		--name $(notdir $@) \
		${PY_ENTRYPOINT}

	# --add-data="icon.png:." \

.PHONY: all clean exe doc mods