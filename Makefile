dir = $(shell pwd)

.PHONY: open
open:
	@cursor $(dir)

.PHONY: init validate apply list layer-validate layer-create
init:
	vm-config init $(ARGS)

validate:
	vm-config validate $(ARGS)

apply:
	vm-config apply $(ARGS)

list:
	vm-config list $(ARGS)

layer-validate:
	vm-config layer validate $(ARGS)

layer-create:
	vm-config layer create $(ARGS)