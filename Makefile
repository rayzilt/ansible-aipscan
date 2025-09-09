lint:
	uv run ansible-lint

test: DISTRO ?= ubuntu2204
test: TAGS ?= all
test: DESTROY ?= always
test:
	# This is the full test sequence with molecule including all steps:
	# - dependency
	# - cleanup
	# - destroy
	# - syntax
	# - create
	# - prepare
	# - converge
	# - idempotence
	# - side_effect
	# - verify
	# - cleanup
	# - destroy
	MOLECULE_DISTRO=$(DISTRO) uv run molecule test --destroy=$(DESTROY) -- --tags=$(TAGS)

pytest: ARGS ?=
pytest:
	uv run pytest -- $(ARGS)
