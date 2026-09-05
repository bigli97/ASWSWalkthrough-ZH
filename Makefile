PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
.DEFAULT_GOAL := help
.PHONY: help setup extract pending assemble preview build check pdf
help:
	@echo "make setup 安装依赖；make preview 本地预览；make build 构建；make pdf 导出 PDF"
setup:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements.txt
extract:
	$(PY) scripts/site.py extract
pending:
	$(PY) scripts/site.py pending
assemble:
	$(PY) scripts/site.py assemble
preview:
	$(PY) scripts/site.py preview
build:
	$(PY) scripts/site.py build
check:
	$(PY) scripts/site.py check
pdf:
	$(PY) scripts/site.py pdf
