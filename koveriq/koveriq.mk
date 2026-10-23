# KoverIQ targets, included from the root Makefile.
#
#   make koveriq-vendor   fetch + verify the pinned gsap.min.js (needs network once)
#   make koveriq-test     unit tests for the koveriq package (no browser, no network)
#   make koveriq-lint     `hyperframes lint` over every style x format with all kinds
#   make golden           deterministic golden: build, lint, snapshot x3, render, ffprobe

.PHONY: koveriq-vendor koveriq-test koveriq-lint golden

koveriq-vendor: ensure-venv
	@$(RUN_PYTHON) -c "from koveriq.vendor import verified_gsap; verified_gsap()" 2>/dev/null \
		&& echo "==> gsap.min.js present and verified" \
		|| $(RUN_PYTHON) -m koveriq.vendor fetch

koveriq-test: ensure-venv
	$(RUN_PYTHON) -m pytest koveriq/tests -q

koveriq-lint: ensure-venv koveriq-vendor
	KOVERIQ_HF_LINT=1 $(RUN_PYTHON) -m pytest koveriq/tests/test_hyperframes_lint.py -q

golden: ensure-venv koveriq-vendor
	@command -v ffprobe >/dev/null || { echo "ffprobe is required"; exit 1; }
	@command -v npx >/dev/null || { echo "node/npx is required"; exit 1; }
	time $(RUN_PYTHON) -m koveriq.golden $(GOLDEN_ARGS)
