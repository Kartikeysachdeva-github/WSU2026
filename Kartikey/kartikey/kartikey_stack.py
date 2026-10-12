import json
from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
)
from constructs import Construct

from .resources.constants import (
    ALARM_LOGGER_DESCRIPTION,
    ALARM_LOGGER_FUNCTION_NAME,
    ALARM_LOGGER_TIMEOUT_SECONDS,
    ALARM_TABLE_NAME,
    ALARM_TOPIC_NAME,
    AVAILABILITY_METRIC_NAME,
    AVAILABILITY_THRESHOLD,
    DASHBOARD_NAME,
    EVALUATION_PERIODS,
    FUNCTION_DESCRIPTION,
    FUNCTION_NAME,
    LAMBDA_TIMEOUT_SECONDS,
    LATENCY_METRIC_NAME,
    LATENCY_THRESHOLD_MS,
    METRIC_NAMESPACE,
    METRIC_PERIOD_MINUTES,
    SCHEDULE_MINUTES,
    WEBSITES_FILE,
    WEBSITE_DIMENSION_NAME,
)


class KartikeyStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment_name: str = "",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Beta and Prod use separate resource names and metrics.
        # An empty environment name keeps the original deployment names.
        suffix = (
            f"-{environment_name.lower()}"
            if environment_name
            else ""
        )
        metric_namespace = (
            f"{METRIC_NAMESPACE}/{environment_name}"
            if environment_name
            else METRIC_NAMESPACE
        )

        websites_path = (
            Path(__file__).parent / "resources" / WEBSITES_FILE
        )

        with open(
            websites_path,
            "r",
            encoding="utf-8",
        ) as websites_file:
            websites = json.load(websites_file)["websites"]

        # Official AWS CDK Python API v2 reference:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html
        web_health_function = lambda_.Function(
            self,
            "WebHealthFunction",
            function_name=f"{FUNCTION_NAME}{suffix}",
            description=FUNCTION_DESCRIPTION,
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="webHealth.handler",
            code=lambda_.Code.from_asset("kartikey/resources"),
            timeout=Duration.seconds(LAMBDA_TIMEOUT_SECONDS),
            environment={
                "METRIC_NAMESPACE": metric_namespace,
            },
        )

        # Official AWS CDK Python API v2 reference:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/PolicyStatement.html
        web_health_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )

        # Official AWS CDK Python API v2 references:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Rule.html
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Schedule.html
        schedule_rule = events.Rule(
            self,
            "WebHealthSchedule",
            description=(
                f"Runs the website crawler every "
                f"{SCHEDULE_MINUTES} minutes"
            ),
            schedule=events.Schedule.rate(
                Duration.minutes(SCHEDULE_MINUTES)
            ),
        )

        # Official AWS CDK Python API v2 reference:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events_targets/LambdaFunction.html
        schedule_rule.add_target(
            targets.LambdaFunction(web_health_function)
        )

        # Official AWS CDK Python API v2 references:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Attribute.html
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/BillingMode.html
        alarm_table = dynamodb.Table(
            self,
            "AlarmLogTable",
            table_name=f"{ALARM_TABLE_NAME}{suffix}",
            partition_key=dynamodb.Attribute(
                name="alarm_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Official AWS CDK Python API v2 reference:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html
        alarm_logger_function = lambda_.Function(
            self,
            "AlarmLoggerFunction",
            function_name=f"{ALARM_LOGGER_FUNCTION_NAME}{suffix}",
            description=ALARM_LOGGER_DESCRIPTION,
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="alarmLogger.handler",
            code=lambda_.Code.from_asset("kartikey/resources"),
            timeout=Duration.seconds(
                ALARM_LOGGER_TIMEOUT_SECONDS
            ),
            environment={
                "ALARM_TABLE_NAME": alarm_table.table_name,
            },
        )

        # Allow this logger to write to its own environment's table.
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html
        alarm_table.grant_write_data(alarm_logger_function)

        # Official AWS CDK Python API v2 reference:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns/Topic.html
        alarm_topic = sns.Topic(
            self,
            "WebsiteAlarmTopic",
            topic_name=f"{ALARM_TOPIC_NAME}{suffix}",
            display_name=(
                f"Kartikey Website Health Alarms"
                f"{f' - {environment_name}' if environment_name else ''}"
            ),
        )

        # Send alarm notifications to the DynamoDB logger.
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns_subscriptions/LambdaSubscription.html
        alarm_topic.add_subscription(
            sns_subscriptions.LambdaSubscription(
                alarm_logger_function
            )
        )

        # Official AWS CDK Python API v2 reference:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Dashboard.html
        dashboard = cloudwatch.Dashboard(
            self,
            "WebsiteHealthDashboard",
            dashboard_name=f"{DASHBOARD_NAME}{suffix}",
        )

        availability_metrics = []
        latency_metrics = []

        for website in websites:
            website_name = website["name"]
            construct_name = website_name.replace(" ", "")

            # Read metrics from this environment's namespace.
            # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Metric.html
            availability_metric = cloudwatch.Metric(
                namespace=metric_namespace,
                metric_name=AVAILABILITY_METRIC_NAME,
                dimensions_map={
                    WEBSITE_DIMENSION_NAME: website_name,
                },
                period=Duration.minutes(METRIC_PERIOD_MINUTES),
                statistic="Minimum",
                label=website_name,
            )

            latency_metric = cloudwatch.Metric(
                namespace=metric_namespace,
                metric_name=LATENCY_METRIC_NAME,
                dimensions_map={
                    WEBSITE_DIMENSION_NAME: website_name,
                },
                period=Duration.minutes(METRIC_PERIOD_MINUTES),
                statistic="Average",
                label=website_name,
            )

            availability_metrics.append(availability_metric)
            latency_metrics.append(latency_metric)

            # Official AWS CDK Python API v2 reference:
            # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Alarm.html
            availability_alarm = cloudwatch.Alarm(
                self,
                f"{construct_name}AvailabilityAlarm",
                alarm_name=(
                    f"{website_name}-Availability-Alarm{suffix}"
                ),
                alarm_description=(
                    f"Alarm when {website_name} is unavailable"
                ),
                metric=availability_metric,
                threshold=AVAILABILITY_THRESHOLD,
                evaluation_periods=EVALUATION_PERIODS,
                comparison_operator=(
                    cloudwatch.ComparisonOperator
                    .LESS_THAN_THRESHOLD
                ),
                treat_missing_data=(
                    cloudwatch.TreatMissingData.BREACHING
                ),
            )

            latency_alarm = cloudwatch.Alarm(
                self,
                f"{construct_name}LatencyAlarm",
                alarm_name=(
                    f"{website_name}-Latency-Alarm{suffix}"
                ),
                alarm_description=(
                    f"Alarm when {website_name} latency exceeds "
                    f"{LATENCY_THRESHOLD_MS} milliseconds"
                ),
                metric=latency_metric,
                threshold=LATENCY_THRESHOLD_MS,
                evaluation_periods=EVALUATION_PERIODS,
                comparison_operator=(
                    cloudwatch.ComparisonOperator
                    .GREATER_THAN_THRESHOLD
                ),
                treat_missing_data=(
                    cloudwatch.TreatMissingData.BREACHING
                ),
            )

            # Notify this environment's SNS topic.
            # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch_actions/SnsAction.html
            availability_alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(alarm_topic)
            )

            latency_alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(alarm_topic)
            )

        # Official AWS CDK Python API v2 reference:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/GraphWidget.html
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Website Availability",
                left=availability_metrics,
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Website Latency",
                left=latency_metrics,
                width=12,
            ),
        )