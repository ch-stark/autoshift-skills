AUTOSHIFT_REPO ?= $(abspath ../autoshiftv2)
export AUTOSHIFT_REPO

.PHONY: test validate mutations parse acm-drift sync triggers evals

test: validate mutations parse ## Free, offline checks: run before every change

validate: ## Spec, links, shared copies, ACM baseline and functions, cited AutoShift paths, style, eval layout
	python3 tests/validate.py --autoshift "$(AUTOSHIFT_REPO)"

mutations: ## Prove each validate check catches a planted defect
	python3 -m unittest tests/test_validate.py

parse: ## Eval fixtures parse under the hub and local template passes
	cd tests/parsecheck && go run . ../../shared/acm-functions.tsv $$(find ../../skills -path '*/evals/*/files/*' -name '*.yaml')

acm-drift: ## Compare ACM at REF (default main, the next release) with shared/acm-baseline.yaml (network); UPDATE=1 rewrites the baseline
	python3 tests/acm_drift.py --ref $(or $(REF),main) $(if $(UPDATE),--update)

sync: ## Copy shared/ references into the skills that carry them
	tests/sync-shared.sh

triggers: ## Trigger evals through the Claude Code CLI (billed): SKILL=autoshift-review to limit
	@: > .eval-kubeconfig
	KUBECONFIG=$(CURDIR)/.eval-kubeconfig python3 tests/run_triggers.py $(if $(SKILL),--skill $(SKILL))

evals: ## Behavior evals for one skill through the Claude Code CLI (billed): SKILL=... required, RUNS=n, CASE=<one case name or a * glob>; --case takes one value and no [ ] classes
	@test -n "$(SKILL)" || (echo "set SKILL=autoshift-review|autoshift-author|autoshift-deploy" && exit 1)
	@: > .eval-kubeconfig
	cd skills/$(SKILL) && KUBECONFIG=$(CURDIR)/.eval-kubeconfig claude plugin eval . \
	  --allow-tools Write Edit Bash --scaffold --trust-plugin --no-publish --runs $(or $(RUNS),1) --threshold 0 $(if $(CASE),--case $(CASE))
