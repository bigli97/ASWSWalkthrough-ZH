PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
.DEFAULT_GOAL := help
.PHONY: help setup extract pending assemble preview build check pdf publish
help:
	@echo "make setup 安装依赖；make preview 本地预览；make build 构建；make pdf 导出 PDF；make publish 校验并发布"
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
publish:
	$(PY) scripts/site.py sync-readme
	$(PY) scripts/site.py sync-homepage
	$(MAKE) check
	$(MAKE) build
	git add -A
	@if git diff --cached --quiet; then \
		echo "没有需要发布的文件。"; \
	else \
		git commit -m "发布已审核中文攻略" && git push; \
	fi
