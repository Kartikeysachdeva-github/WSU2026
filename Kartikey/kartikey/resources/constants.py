# Application configuration
FUNCTION_NAME = "kartikey-web-health"
FUNCTION_DESCRIPTION = "Periodically checks websites and publishes health metrics"

# File containing the websites monitored by the Lambda
WEBSITES_FILE = "websites.json"

# CloudWatch configuration
METRIC_NAMESPACE = "Kartikey/WebsiteMonitoring"
AVAILABILITY_METRIC_NAME = "Availability"
LATENCY_METRIC_NAME = "Latency"
WEBSITE_DIMENSION_NAME = "Website"

# EventBridge schedule
SCHEDULE_MINUTES = 5

# Website request configuration
REQUEST_TIMEOUT_SECONDS = 10

# Lambda configuration
LAMBDA_TIMEOUT_SECONDS = 60

# CloudWatch metric period
METRIC_PERIOD_MINUTES = 5

# Alarm configuration
AVAILABILITY_THRESHOLD = 1
LATENCY_THRESHOLD_MS = 3000
EVALUATION_PERIODS = 1

# CloudWatch dashboard
DASHBOARD_NAME = "Kartikey-Website-Health-Dashboard"