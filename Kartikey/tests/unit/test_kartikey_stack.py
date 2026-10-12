import aws_cdk as cdk
from aws_cdk import assertions
import pytest

from kartikey.kartikey_stack import KartikeyStack


# Official CDK assertions reference:
# https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.assertions/README.html
@pytest.fixture
def beta_template():
    # Synthesis checks infrastructure locally without deploying it.
    app = cdk.App()
    stack = KartikeyStack(
        app,
        "TestBeta",
        environment_name="Beta",
    )
    return assertions.Template.from_stack(stack)


def test_monitor_configuration(beta_template):
    # The monitor must publish metrics to the Beta namespace.
    beta_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "kartikey-web-health-beta",
            "Runtime": "python3.13",
            "Handler": "webHealth.handler",
            "Timeout": 60,
            "Environment": {
                "Variables": {
                    "METRIC_NAMESPACE":
                        "Kartikey/WebsiteMonitoring/Beta",
                }
            },
        },
    )


def test_schedule_invokes_monitor(beta_template):
    # Check the five-minute schedule and its actual Lambda target.
    functions = beta_template.find_resources(
        "AWS::Lambda::Function",
        {"Properties": {"FunctionName": "kartikey-web-health-beta"}},
    )
    monitor_id = next(iter(functions))

    beta_template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "ScheduleExpression": "rate(5 minutes)",
            "State": "ENABLED",
            "Targets": assertions.Match.array_with([
                assertions.Match.object_like({
                    "Arn": {"Fn::GetAtt": [monitor_id, "Arn"]},
                })
            ]),
        },
    )


def test_alarm_table_schema(beta_template):
    # The logger needs the expected keys and on-demand billing.
    beta_template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "Kartikey-Website-Alarm-Logs-beta",
            "BillingMode": "PAY_PER_REQUEST",
            "KeySchema": [
                {"AttributeName": "alarm_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
        },
    )


def test_logger_uses_correct_table(beta_template):
    # Check that the table reference is passed to the logger.
    tables = beta_template.find_resources("AWS::DynamoDB::Table")
    table_id = next(iter(tables))

    beta_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "kartikey-alarm-logger-beta",
            "Handler": "alarmLogger.handler",
            "Environment": {
                "Variables": {
                    "ALARM_TABLE_NAME": {"Ref": table_id},
                }
            },
        },
    )


def test_sns_subscription_targets_logger(beta_template):
    # Alarm messages must reach this environment's logger.
    topics = beta_template.find_resources("AWS::SNS::Topic")
    topic_id = next(iter(topics))
    loggers = beta_template.find_resources(
        "AWS::Lambda::Function",
        {"Properties": {"FunctionName": "kartikey-alarm-logger-beta"}},
    )
    logger_id = next(iter(loggers))

    beta_template.has_resource_properties(
        "AWS::SNS::Subscription",
        {
            "Protocol": "lambda",
            "TopicArn": {"Ref": topic_id},
            "Endpoint": {"Fn::GetAtt": [logger_id, "Arn"]},
        },
    )


def test_all_alarms_use_beta_metrics_and_topic(beta_template):
    # Check all six alarms rather than only one example.
    alarms = beta_template.find_resources("AWS::CloudWatch::Alarm")
    topics = beta_template.find_resources("AWS::SNS::Topic")
    topic_id = next(iter(topics))

    assert len(alarms) == 6

    for alarm in alarms.values():
        properties = alarm["Properties"]
        metric = properties["Metrics"][0]["MetricStat"]["Metric"]

        assert properties["AlarmName"].endswith("-beta")
        assert metric["Namespace"] == "Kartikey/WebsiteMonitoring/Beta"
        assert properties["AlarmActions"] == [{"Ref": topic_id}]
        assert properties["TreatMissingData"] == "breaching"

        if metric["MetricName"] == "Availability":
            assert properties["Threshold"] == 1
            assert properties["ComparisonOperator"] == "LessThanThreshold"
        else:
            assert metric["MetricName"] == "Latency"
            assert properties["Threshold"] == 3000
            assert properties["ComparisonOperator"] == "GreaterThanThreshold"


def test_beta_and_prod_names_do_not_overlap():
    # Both environments must coexist in the same account.
    app = cdk.App()

    # Create both stacks before synthesis.
    beta_stack = KartikeyStack(
        app,
        "BetaTest",
        environment_name="Beta",
    )

    prod_stack = KartikeyStack(
        app,
        "ProdTest",
        environment_name="Prod",
    )

    beta = assertions.Template.from_stack(beta_stack)
    prod = assertions.Template.from_stack(prod_stack)

    beta_template = beta.to_json()
    prod_template = prod.to_json()

    beta_names = set()
    prod_names = set()

    # Collect explicitly named AWS resources from both stacks.
    name_properties = [
        "FunctionName",
        "TableName",
        "TopicName",
        "AlarmName",
        "DashboardName",
        "Name",
    ]

    for resource in beta_template["Resources"].values():
        properties = resource.get("Properties", {})
        for property_name in name_properties:
            if property_name in properties:
                value = properties[property_name]
                if isinstance(value, str):
                    beta_names.add(value)

    for resource in prod_template["Resources"].values():
        properties = resource.get("Properties", {})
        for property_name in name_properties:
            if property_name in properties:
                value = properties[property_name]
                if isinstance(value, str):
                    prod_names.add(value)

    assert beta_names.isdisjoint(prod_names)