PORT ?= 50000
CONFIG ?= ./configs/sample-configs/ds-sample-config01.xml
CONFIG_DIR ?= TestConfigs

.PHONY: help setup test lint run trace bench ref plots report export gantt summary

help:
	@echo "make setup   - chmod +x the ds-* binaries (once per checkout)"
	@echo "make test    - run the unit tests"
	@echo "make lint    - run ruff (pip install ruff)"
	@echo "make run     - run the client once against CONFIG (default: sample config 01)"
	@echo "make trace   - same as run, also writing every scheduling decision to trace.txt"
	@echo "make bench   - run the full marking harness (needs ds-server)"
	@echo "make ref     - regenerate reference results with ds-client (slow)"
	@echo "make plots   - draw charts from results/*.json into diagrams/"
	@echo "make report  - results broken down by workload type"
	@echo "make export  - write RESULTS.md from results/*.json"
	@echo "make gantt LOG=run.log OUT=diagrams/run.mmd - Gantt chart from a ds-server log"
	@echo "make summary LOG=run.log - waiting/execution/turnaround summary of a ds-server log"

setup:
	chmod +x ds-server ds-client ds-mermaid

test:
	python3 -m pytest tests -q

lint:
	python3 -m ruff check .

run:
	./ds-server -n -p $(PORT) -v brief -c $(CONFIG) & \
	sleep 2; python3 client.py --stats; wait

trace:
	./ds-server -n -p $(PORT) -v brief -c $(CONFIG) & \
	sleep 2; python3 client.py --stats --trace trace.txt; wait

bench:
	python3 ds_test.py "python3 client.py" -n -p $(PORT) -c $(CONFIG_DIR)

ref:
	python3 ref_results.py -c $(CONFIG_DIR)

plots:
	python3 plot_results.py

report:
	python3 workload_report.py

export:
	python3 export_results.py

gantt:
	python3 make_gantt.py $(LOG) -o $(OUT)

summary:
	python3 log_summary.py $(LOG)
