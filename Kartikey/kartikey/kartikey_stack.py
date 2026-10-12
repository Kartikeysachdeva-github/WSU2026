import json
from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_codedeploy as codedeploy,
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

        # ---------------------------------------------------------
        # Website crawler Lambda
        # ---------------------------------------------------------

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

        web_health_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )

        # ---------------------------------------------------------
        # Week 11 - Lambda Version and Alias
        # ---------------------------------------------------------

        # current_version creates an immutable Lambda version.
        # CodeDeploy will manage traffic to this version through
        # the live alias.
        crawler_version = web_health_function.current_version

        crawler_alias = lambda_.Alias(
            self,
            "CrawlerLiveAlias",
            alias_name="live",
            version=crawler_version,
            description=(
                "Live version of the website health crawler."
            ),
        )

        # ---------------------------------------------------------
        # EventBridge schedule
        # ---------------------------------------------------------

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

        # Invoke the live alias rather than $LATEST.
        # This ensures scheduled traffic passes through the
        # CodeDeploy-controlled alias.
        schedule_rule.add_target(
            targets.LambdaFunction(crawler_alias)
        )

        # ---------------------------------------------------------
        # DynamoDB alarm log
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # Alarm logger Lambda
        # ---------------------------------------------------------

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

        alarm_table.grant_write_data(alarm_logger_function)

        # ---------------------------------------------------------
        # SNS alarm topic
        # ---------------------------------------------------------

        alarm_topic = sns.Topic(
            self,
            "WebsiteAlarmTopic",
            topic_name=f"{ALARM_TOPIC_NAME}{suffix}",
            display_name=(
                f"Kartikey Website Health Alarms"
                f"{f' - {environment_name}' if environment_name else ''}"
            ),
        )

        alarm_topic.add_subscription(
            sns_subscriptions.LambdaSubscription(
                alarm_logger_function
            )
        )

        # ---------------------------------------------------------
        # CloudWatch dashboard
        # ---------------------------------------------------------

        dashboard = cloudwatch.Dashboard(
            self,
            "WebsiteHealthDashboard",
            dashboard_name=f"{DASHBOARD_NAME}{suffix}",
        )

        availability_metrics = []
        latency_metrics = []

        # ---------------------------------------------------------
        # Website health metrics and alarms
        # ---------------------------------------------------------

        for website in websites:
            website_name = website["name"]
            construct_name = website_name.replace(" ", "")

            availability_metric = cloudwatch.Metric(
                namespace=metric_namespace,
                metric_name=AVAILABILITY_METRIC_NAME,
                dimensions_map={
                    WEBSITE_DIMENSION_NAME: website_name,
                },
                period=Duration.minutes(
                    METRIC_PERIOD_MINUTES
                ),
                statistic="Minimum",
                label=website_name,
            )

            latency_metric = cloudwatch.Metric(
                namespace=metric_namespace,
                metric_name=LATENCY_METRIC_NAME,
                dimensions_map={
                    WEBSITE_DIMENSION_NAME: website_name,
                },
                period=Duration.minutes(
                    METRIC_PERIOD_MINUTES
                ),
                statistic="Average",
                label=website_name,
            )

            availability_metrics.append(
                availability_metric
            )

            latency_metrics.append(
                latency_metric
            )

            availability_alarm = cloudwatch.Alarm(
                self,
                f"{construct_name}AvailabilityAlarm",
                alarm_name=(
                    f"{website_name}-Availability-Alarm"
                    f"{suffix}"
                ),
                alarm_description=(
                    f"Alarm when {website_name} "
                    f"is unavailable"
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
                    f"{website_name}-Latency-Alarm"
                    f"{suffix}"
                ),
                alarm_description=(
                    f"Alarm when {website_name} latency "
                    f"exceeds {LATENCY_THRESHOLD_MS} "
                    f"milliseconds"
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

            availability_alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(
                    alarm_topic
                )
            )

            latency_alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(
                    alarm_topic
                )
            )

        # Website health graphs.
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

        # ---------------------------------------------------------
        # Week 11 - crawler operational monitoring
        # ---------------------------------------------------------

        invocation_metric = (
            web_health_function.metric_invocations(
                period=Duration.minutes(5),
                statistic="Sum",
            )
        )

        error_metric = (
            web_health_function.metric_errors(
                period=Duration.minutes(5),
                statistic="Sum",
            )
        )

        duration_metric = (
            web_health_function.metric_duration(
                period=Duration.minutes(5),
                statistic="Average",
            )
        )

        throttle_metric = (
            web_health_function.metric_throttles(
                period=Duration.minutes(5),
                statistic="Sum",
            )
        )

        # ---------------------------------------------------------
        # Crawler operational alarms
        # ---------------------------------------------------------

        crawler_error_alarm = cloudwatch.Alarm(
            self,
            "CrawlerErrorAlarm",
            alarm_name=(
                f"Kartikey-Crawler-Errors{suffix}"
            ),
            alarm_description=(
                "Alarm when the website crawler Lambda "
                "reports errors."
            ),
            metric=error_metric,
            threshold=1,
            evaluation_periods=1,
            comparison_operator=(
                cloudwatch.ComparisonOperator
                .GREATER_THAN_OR_EQUAL_TO_THRESHOLD
            ),
            treat_missing_data=(
                cloudwatch.TreatMissingData.NOT_BREACHING
            ),
        )

        crawler_duration_alarm = cloudwatch.Alarm(
            self,
            "CrawlerDurationAlarm",
            alarm_name=(
                f"Kartikey-Crawler-Duration{suffix}"
            ),
            alarm_description=(
                "Alarm when average crawler execution "
                "time exceeds 30 seconds."
            ),
            metric=duration_metric,
            threshold=30000,
            evaluation_periods=1,
            comparison_operator=(
                cloudwatch.ComparisonOperator
                .GREATER_THAN_THRESHOLD
            ),
            treat_missing_data=(
                cloudwatch.TreatMissingData.NOT_BREACHING
            ),
        )

        crawler_throttle_alarm = cloudwatch.Alarm(
            self,
            "CrawlerThrottleAlarm",
            alarm_name=(
                f"Kartikey-Crawler-Throttles{suffix}"
            ),
            alarm_description=(
                "Alarm when the crawler Lambda "
                "is throttled."
            ),
            metric=throttle_metric,
            threshold=1,
            evaluation_periods=1,
            comparison_operator=(
                cloudwatch.ComparisonOperator
                .GREATER_THAN_OR_EQUAL_TO_THRESHOLD
            ),
            treat_missing_data=(
                cloudwatch.TreatMissingData.NOT_BREACHING
            ),
        )

        # Send operational alarms through the same SNS path.
        crawler_error_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(
                alarm_topic
            )
        )

        crawler_duration_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(
                alarm_topic
            )
        )

        crawler_throttle_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(
                alarm_topic
            )
        )

        # ---------------------------------------------------------
        # Week 11 - CodeDeploy canary deployment
        # ---------------------------------------------------------

        # CodeDeploy shifts 10% of traffic to the new version.
        # If the deployment remains healthy for five minutes,
        # the remaining traffic is shifted to the new version.
        #
        # If the error alarm enters ALARM or the deployment
        # fails/stops, CodeDeploy automatically rolls the alias
        # back to the previous Lambda version.
        codedeploy.LambdaDeploymentGroup(
            self,
            "CrawlerDeploymentGroup",
            alias=crawler_alias,
            deployment_group_name=(
                f"Kartikey-Crawler-Deployment{suffix}"
            ),
            deployment_config=(
                codedeploy.LambdaDeploymentConfig
                .CANARY_10_PERCENT_5_MINUTES
            ),
            alarms=[
                crawler_error_alarm,
            ],
            auto_rollback=(
                codedeploy.AutoRollbackConfig(
                    deployment_in_alarm=True,
                    failed_deployment=True,
                    stopped_deployment=True,
                )
            ),
        )

        # ---------------------------------------------------------
        # Operational dashboard widgets
        # ---------------------------------------------------------

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Crawler Invocations and Errors",
                left=[
                    invocation_metric,
                    error_metric,
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Crawler Execution Duration",
                left=[
                    duration_metric,
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Crawler Throttles",
                left=[
                    throttle_metric,
                ],
                width=12,
            ),
        )