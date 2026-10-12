import json
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    CustomResource,
    aws_apigateway as apigateway,
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
    TARGET_TABLE_NAME,
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
        super().__init__(
            scope,
            construct_id,
            **kwargs,
        )

        # ---------------------------------------------------------
        # Environment configuration
        # ---------------------------------------------------------

        # Beta and Prod use separate physical resource names.
        suffix = (
            f"-{environment_name.lower()}"
            if environment_name
            else ""
        )

        # Beta and Prod also publish custom metrics into separate
        # CloudWatch namespaces.
        metric_namespace = (
            f"{METRIC_NAMESPACE}/{environment_name}"
            if environment_name
            else METRIC_NAMESPACE
        )

        # websites.json remains an infrastructure configuration file
        # for the original website-specific CloudWatch alarms.
        #
        # The runtime crawler target list is no longer loaded from this
        # file. Runtime targets are stored in DynamoDB and managed by
        # the Applied Project REST API.
        websites_path = (
            Path(__file__).parent
            / "resources"
            / WEBSITES_FILE
        )

        with open(
            websites_path,
            "r",
            encoding="utf-8",
        ) as websites_file:
            websites = json.load(
                websites_file
            )["websites"]

        # ---------------------------------------------------------
        # Applied Project - website target DynamoDB table
        # ---------------------------------------------------------

        # Stores the dynamic list of websites monitored by the crawler.
        # target_id is the partition key used by the CRUD API.
        #
        # Official AWS CDK DynamoDB documentation:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html
        target_table = dynamodb.Table(
            self,
            "WebsiteTargetTable",
            table_name=(
                f"{TARGET_TABLE_NAME}{suffix}"
            ),
            partition_key=dynamodb.Attribute(
                name="target_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=(
                dynamodb.BillingMode.PAY_PER_REQUEST
            ),
        )

                # ---------------------------------------------------------
        # Applied Project - initial target seeding
        # ---------------------------------------------------------

        # A small custom-resource Lambda places the original website
        # targets into DynamoDB when the environment is first deployed.
        #
        # Existing records are preserved, so later CRUD API changes are
        # not overwritten by normal stack deployments.
        #
        # AWS CloudFormation custom-resource documentation:
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-custom-resources.html
        target_seed_function = lambda_.Function(
            self,
            "TargetSeedFunction",
            function_name=(
                f"kartikey-target-seeder{suffix}"
            ),
            description=(
                "Seeds the initial website crawler targets "
                "into DynamoDB."
            ),
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="seedTargets.handler",
            code=lambda_.Code.from_asset(
                "kartikey/resources"
            ),
            timeout=Duration.seconds(60),
            environment={
                "TARGET_TABLE_NAME": (
                    target_table.table_name
                ),
            },
        )

        # The seeder only needs permission to add the initial target
        # records to this specific DynamoDB table.
        target_table.grant_write_data(
            target_seed_function
        )

        # Build the initial records from the same baseline configuration
        # used by the original website health monitor.
        initial_targets = [
            {
                "target_id": (
                    website["name"]
                    .lower()
                    .replace(" ", "-")
                ),
                "name": website["name"],
                "url": website["url"],
            }
            for website in websites
        ]

        # CloudFormation invokes this custom resource during deployment.
        # The service token tells CloudFormation which Lambda handles
        # Create, Update and Delete lifecycle events.
        initial_target_seed = CustomResource(
            self,
            "InitialTargetSeed",
            service_token=(
                target_seed_function.function_arn
            ),
            properties={
                "Targets": initial_targets,
            },
        )

        # Ensure DynamoDB exists before CloudFormation invokes the
        # seeder Lambda.
        initial_target_seed.node.add_dependency(
            target_table
        )


        # ---------------------------------------------------------
        # Website crawler Lambda
        # ---------------------------------------------------------

        # EventBridge invokes this Lambda on a schedule. The Lambda now
        # reads its target list from the DynamoDB target table.
        #
        # Official AWS CDK Lambda documentation:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html
        web_health_function = lambda_.Function(
            self,
            "WebHealthFunction",
            function_name=(
                f"{FUNCTION_NAME}{suffix}"
            ),
            description=FUNCTION_DESCRIPTION,
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="webHealth.handler",
            code=lambda_.Code.from_asset(
                "kartikey/resources"
            ),
            timeout=Duration.seconds(
                LAMBDA_TIMEOUT_SECONDS
            ),
            environment={
                "METRIC_NAMESPACE": metric_namespace,
                "TARGET_TABLE_NAME": (
                    target_table.table_name
                ),
            },
        )

        # Least privilege: the crawler only needs to read targets.
        target_table.grant_read_data(
            web_health_function
        )

        # CloudWatch custom metrics require PutMetricData permission.
        web_health_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData",
                ],
                resources=["*"],
            )
        )

        # ---------------------------------------------------------
        # Week 11 - Lambda version and live alias
        # ---------------------------------------------------------

        # current_version creates an immutable Lambda version.
        # CodeDeploy controls production traffic through the live alias.
        crawler_version = (
            web_health_function.current_version
        )

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

        # Official AWS CDK EventBridge documentation:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Rule.html
        schedule_rule = events.Rule(
            self,
            "WebHealthSchedule",
            description=(
                f"Runs the website crawler every "
                f"{SCHEDULE_MINUTES} minutes"
            ),
            schedule=events.Schedule.rate(
                Duration.minutes(
                    SCHEDULE_MINUTES
                )
            ),
        )

        # Scheduled traffic invokes the live alias rather than $LATEST.
        # This keeps EventBridge traffic under CodeDeploy control.
        schedule_rule.add_target(
            targets.LambdaFunction(
                crawler_alias
            )
        )

        # ---------------------------------------------------------
        # Existing DynamoDB alarm log
        # ---------------------------------------------------------

        # This table is separate from the Applied Project target table.
        # It stores alarm events received through SNS.
        alarm_table = dynamodb.Table(
            self,
            "AlarmLogTable",
            table_name=(
                f"{ALARM_TABLE_NAME}{suffix}"
            ),
            partition_key=dynamodb.Attribute(
                name="alarm_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=(
                dynamodb.BillingMode.PAY_PER_REQUEST
            ),
        )

        # ---------------------------------------------------------
        # Alarm logger Lambda
        # ---------------------------------------------------------

        alarm_logger_function = lambda_.Function(
            self,
            "AlarmLoggerFunction",
            function_name=(
                f"{ALARM_LOGGER_FUNCTION_NAME}"
                f"{suffix}"
            ),
            description=ALARM_LOGGER_DESCRIPTION,
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="alarmLogger.handler",
            code=lambda_.Code.from_asset(
                "kartikey/resources"
            ),
            timeout=Duration.seconds(
                ALARM_LOGGER_TIMEOUT_SECONDS
            ),
            environment={
                "ALARM_TABLE_NAME": (
                    alarm_table.table_name
                ),
            },
        )

        # The logger only needs write access to the alarm history table.
        alarm_table.grant_write_data(
            alarm_logger_function
        )

        # ---------------------------------------------------------
        # SNS alarm topic
        # ---------------------------------------------------------

        # CloudWatch alarms publish to SNS. SNS invokes the alarm logger
        # Lambda, which records the alarm event in DynamoDB.
        alarm_topic = sns.Topic(
            self,
            "WebsiteAlarmTopic",
            topic_name=(
                f"{ALARM_TOPIC_NAME}{suffix}"
            ),
            display_name=(
                "Kartikey Website Health Alarms"
                f"{f' - {environment_name}' if environment_name else ''}"
            ),
        )

        alarm_topic.add_subscription(
            sns_subscriptions.LambdaSubscription(
                alarm_logger_function
            )
        )

        # ---------------------------------------------------------
        # Applied Project - CRUD Lambda
        # ---------------------------------------------------------

        # Implements the business logic behind the public REST API.
        target_api_function = lambda_.Function(
            self,
            "TargetApiFunction",
            function_name=(
                f"kartikey-target-api{suffix}"
            ),
            description=(
                "Provides CRUD operations for website "
                "crawler targets."
            ),
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="targetApi.handler",
            code=lambda_.Code.from_asset(
                "kartikey/resources"
            ),
            timeout=Duration.seconds(30),
            environment={
                "TARGET_TABLE_NAME": (
                    target_table.table_name
                ),
                "METRIC_NAMESPACE": metric_namespace,
            },
        )

        # The API performs Create, Read, Update and Delete operations,
        # so it requires read/write access to the target table.
        target_table.grant_read_write_data(
            target_api_function
        )

        # The API publishes DynamoDB read/write duration metrics.
        target_api_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData",
                ],
                resources=["*"],
            )
        )

        # ---------------------------------------------------------
        # Applied Project - API Gateway REST API
        # ---------------------------------------------------------

        # Public REST API used to manage crawler targets.
        #
        # Official AWS CDK API Gateway documentation:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_apigateway/RestApi.html
        target_api = apigateway.RestApi(
            self,
            "WebsiteTargetApi",
            rest_api_name=(
                "Kartikey-Website-Targets-API"
                f"{suffix}"
            ),
            description=(
                "Public REST API for managing website "
                "crawler targets."
            ),
            deploy_options=(
                apigateway.StageOptions(
                    stage_name=(
                        environment_name.lower()
                        if environment_name
                        else "dev"
                    ),
                )
            ),
        )

        # Lambda proxy integration forwards the API Gateway request to
        # targetApi.handler, including method, path parameters and body.
        target_api_integration = (
            apigateway.LambdaIntegration(
                target_api_function
            )
        )

        # ---------------------------------------------------------
        # /targets collection
        # ---------------------------------------------------------

        targets_resource = (
            target_api.root.add_resource(
                "targets"
            )
        )

        # GET /targets -> list all targets.
        targets_resource.add_method(
            "GET",
            target_api_integration,
        )

        # POST /targets -> create a target.
        targets_resource.add_method(
            "POST",
            target_api_integration,
        )

        # ---------------------------------------------------------
        # /targets/{id} resource
        # ---------------------------------------------------------

        target_resource = (
            targets_resource.add_resource(
                "{id}"
            )
        )

        # GET /targets/{id} -> read one target.
        target_resource.add_method(
            "GET",
            target_api_integration,
        )

        # PUT /targets/{id} -> update one target.
        target_resource.add_method(
            "PUT",
            target_api_integration,
        )

        # DELETE /targets/{id} -> delete one target.
        target_resource.add_method(
            "DELETE",
            target_api_integration,
        )

        # CORS allows the public REST API to be called from browser-based
        # clients as well as command-line clients.
        targets_resource.add_cors_preflight(
            allow_origins=(
                apigateway.Cors.ALL_ORIGINS
            ),
            allow_methods=[
                "GET",
                "POST",
                "OPTIONS",
            ],
            allow_headers=[
                "Content-Type",
            ],
        )

        target_resource.add_cors_preflight(
            allow_origins=(
                apigateway.Cors.ALL_ORIGINS
            ),
            allow_methods=[
                "GET",
                "PUT",
                "DELETE",
                "OPTIONS",
            ],
            allow_headers=[
                "Content-Type",
            ],
        )

        # CloudFormation prints the base URL after deployment. This is
        # also useful for integration testing the deployed API.
        CfnOutput(
            self,
            "TargetApiUrl",
            value=target_api.url,
            description=(
                "Base URL for the website target CRUD API."
            ),
        )

        # ---------------------------------------------------------
        # CloudWatch dashboard
        # ---------------------------------------------------------

        dashboard = cloudwatch.Dashboard(
            self,
            "WebsiteHealthDashboard",
            dashboard_name=(
                f"{DASHBOARD_NAME}{suffix}"
            ),
        )

        availability_metrics = []
        latency_metrics = []

        # ---------------------------------------------------------
        # Website health metrics and alarms
        # ---------------------------------------------------------

        # These original website-specific alarms remain defined from the
        # infrastructure configuration in websites.json.
        for website in websites:
            website_name = website["name"]

            construct_name = (
                website_name.replace(
                    " ",
                    "",
                )
            )

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
                    f"{website_name}"
                    "-Availability-Alarm"
                    f"{suffix}"
                ),
                alarm_description=(
                    f"Alarm when {website_name} "
                    "is unavailable"
                ),
                metric=availability_metric,
                threshold=AVAILABILITY_THRESHOLD,
                evaluation_periods=(
                    EVALUATION_PERIODS
                ),
                comparison_operator=(
                    cloudwatch.ComparisonOperator
                    .LESS_THAN_THRESHOLD
                ),
                treat_missing_data=(
                    cloudwatch.TreatMissingData
                    .BREACHING
                ),
            )

            latency_alarm = cloudwatch.Alarm(
                self,
                f"{construct_name}LatencyAlarm",
                alarm_name=(
                    f"{website_name}"
                    "-Latency-Alarm"
                    f"{suffix}"
                ),
                alarm_description=(
                    f"Alarm when {website_name} "
                    f"latency exceeds "
                    f"{LATENCY_THRESHOLD_MS} "
                    "milliseconds"
                ),
                metric=latency_metric,
                threshold=LATENCY_THRESHOLD_MS,
                evaluation_periods=(
                    EVALUATION_PERIODS
                ),
                comparison_operator=(
                    cloudwatch.ComparisonOperator
                    .GREATER_THAN_THRESHOLD
                ),
                treat_missing_data=(
                    cloudwatch.TreatMissingData
                    .BREACHING
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

        # Original website health dashboard graphs.
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
                cloudwatch.TreatMissingData
                .NOT_BREACHING
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
                cloudwatch.TreatMissingData
                .NOT_BREACHING
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
                cloudwatch.TreatMissingData
                .NOT_BREACHING
            ),
        )

        # All operational alarms use the existing SNS notification path.
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

        # Shift 10% of crawler traffic to the new Lambda version.
        # After five healthy minutes, CodeDeploy shifts the remaining
        # traffic to the new version.
        #
        # If the crawler error alarm enters ALARM, or the deployment
        # fails/stops, CodeDeploy automatically rolls the alias back.
        #
        # Official AWS CDK CodeDeploy Lambda documentation:
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_codedeploy/LambdaDeploymentGroup.html
        codedeploy.LambdaDeploymentGroup(
            self,
            "CrawlerDeploymentGroup",
            alias=crawler_alias,
            deployment_group_name=(
                "Kartikey-Crawler-Deployment"
                f"{suffix}"
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
                title=(
                    "Crawler Invocations and Errors"
                ),
                left=[
                    invocation_metric,
                    error_metric,
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title=(
                    "Crawler Execution Duration"
                ),
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