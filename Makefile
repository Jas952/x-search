APP_NAME = check_x_bot

.PHONY: run build test lint lint-fix staticcheck

run:
	go run ./cmd/app

build:
	go build -o bin/$(APP_NAME) ./cmd/app

test:
	go test ./...

lint:
	golangci-lint run ./...

staticcheck:
	staticcheck ./...
