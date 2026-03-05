# =============================================================================
# Joiner — Makefile
# =============================================================================
# Usage:
#   make deploy-consumer        Deploy webhook_consumer to AWS Lambda
#   make deploy-verification    Deploy webhook_verification to AWS Lambda
#   make deploy-authorizer      Deploy signature_authorizer to AWS Lambda
#   make deploy-all             Deploy all lambdas
#   make test                   Run unit tests
#   make lint                   Run ruff + mypy
#   make clean                  Remove build artifacts
# =============================================================================

# ---------------------------------------------------------------------------
# Config — override via env or CLI: make deploy-consumer REGION=sa-east-1
# ---------------------------------------------------------------------------
REGION          ?= us-east-1
CONSUMER_NAME   ?= meta-webhook-consumer
VERIFY_NAME     ?= meta-callback-verify
AUTHORIZER_NAME ?= meta-signature-verify

CONSUMER_DIR    := lambdas/webhook_consumer
VERIFY_DIR      := lambdas/webhook_verification
AUTHORIZER_DIR  := lambdas/signature_authorizer

BUILD_DIR       := .build
PYTHON          := python3

.PHONY: all deploy-consumer deploy-verification deploy-authorizer deploy-all \
        test lint clean _build-consumer _build-verification _build-authorizer

# ---------------------------------------------------------------------------
# Deploy — webhook_consumer
# ---------------------------------------------------------------------------
deploy-consumer: _build-consumer
	@echo "🚀 Deploying $(CONSUMER_NAME) to Lambda ($(REGION))..."
	aws lambda update-function-code \
		--function-name $(CONSUMER_NAME) \
		--zip-file fileb://$(BUILD_DIR)/consumer.zip \
		--region $(REGION)
	@echo "✅ $(CONSUMER_NAME) deployed."

_build-consumer:
	@echo "📦 Building webhook_consumer..."
	rm -rf $(BUILD_DIR)/consumer
	mkdir -p $(BUILD_DIR)/consumer
	pip install requests boto3 \
		-t $(BUILD_DIR)/consumer \
		--upgrade \
		--quiet
	cp -r $(CONSUMER_DIR)/joiner_bot $(BUILD_DIR)/consumer/
	cp $(CONSUMER_DIR)/lambda_function.py $(BUILD_DIR)/consumer/
	cd $(BUILD_DIR)/consumer && zip -r ../consumer.zip . \
		-x "*.pyc" -x "*/__pycache__/*" -x "*.dist-info/*" -x "*.egg-info/*"
	@echo "📦 consumer.zip ready. Size: $$(du -sh $(BUILD_DIR)/consumer.zip | cut -f1)"

# ---------------------------------------------------------------------------
# Deploy — webhook_verification
# ---------------------------------------------------------------------------
deploy-verification: _build-verification
	@echo "🚀 Deploying $(VERIFY_NAME) to Lambda ($(REGION))..."
	aws lambda update-function-code \
		--function-name $(VERIFY_NAME) \
		--zip-file fileb://$(BUILD_DIR)/verification.zip \
		--region $(REGION)
	@echo "✅ $(VERIFY_NAME) deployed."

_build-verification:
	@echo "📦 Building webhook_verification..."
	rm -rf $(BUILD_DIR)/verification
	mkdir -p $(BUILD_DIR)/verification
	pip install boto3 \
		-t $(BUILD_DIR)/verification \
		--upgrade \
		--quiet
	cp $(VERIFY_DIR)/lambda_function.py $(BUILD_DIR)/verification/
	cd $(BUILD_DIR)/verification && zip -r ../verification.zip . \
		-x "*.pyc" -x "*/__pycache__/*" -x "*.dist-info/*"
	@echo "📦 verification.zip ready."

# ---------------------------------------------------------------------------
# Deploy — signature_authorizer
# ---------------------------------------------------------------------------
deploy-authorizer: _build-authorizer
	@echo "🚀 Deploying $(AUTHORIZER_NAME) to Lambda ($(REGION))..."
	aws lambda update-function-code \
		--function-name $(AUTHORIZER_NAME) \
		--zip-file fileb://$(BUILD_DIR)/authorizer.zip \
		--region $(REGION)
	@echo "✅ $(AUTHORIZER_NAME) deployed."

_build-authorizer:
	@echo "📦 Building signature_authorizer..."
	rm -rf $(BUILD_DIR)/authorizer
	mkdir -p $(BUILD_DIR)/authorizer
	pip install boto3 \
		-t $(BUILD_DIR)/authorizer \
		--upgrade \
		--quiet
	cp $(AUTHORIZER_DIR)/lambda_function.py $(BUILD_DIR)/authorizer/
	cd $(BUILD_DIR)/authorizer && zip -r ../authorizer.zip . \
		-x "*.pyc" -x "*/__pycache__/*" -x "*.dist-info/*"
	@echo "📦 authorizer.zip ready."

# ---------------------------------------------------------------------------
# Deploy all
# ---------------------------------------------------------------------------
deploy-all: deploy-consumer deploy-verification deploy-authorizer
	@echo "🎉 All lambdas deployed."

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
test:
	@echo "🧪 Running tests..."
	$(PYTHON) -m pytest tests/ -v

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------
lint:
	@echo "🔍 Running ruff..."
	$(PYTHON) -m ruff check lambdas/ tests/
	@echo "🔍 Running mypy..."
	$(PYTHON) -m mypy lambdas/webhook_consumer/lambda_function.py \
		lambdas/webhook_consumer/joiner_bot/

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf $(BUILD_DIR)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "✅ Clean done."
