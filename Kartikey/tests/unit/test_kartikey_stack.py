import aws_cdk as cdk
import pytest
from aws_cdk import assertions

from kartikey.kartikey_stack import KartikeyStack


@pytest.fixture
def beta_template():
    app = cdk.App()

    stack = KartikeyStack(
        app,
        "BetaTest",
        environment_name="Beta",
    )

    return assertions.Template.from_stack(stack)


def test_monitor_configuration(beta_template):
    functions = beta_template.find_resources(
        "AWS::Lambda::Function"
    )

    web_health_functions = [
        resource
        for resource in functions.values()
        if resource["Properties"].get("FunctionName")
        == "kartikey-web-health-beta"
    ]

    assert len(web_health_functions) == 1

    properties = web_health_functions[0]["Properties"]

    assert properties["Runtime"] == "python3.13"
    assert properties["Handler"] == "webHealth.handler"

    environment = properties["Environment"]["Variables"]

    assert (
        environment["METRIC_NAMESPACE"]
        == "Kartikey/WebsiteMonitoring/Beta"
    )


def test_schedule_invokes_monitor(beta_template):
    rules = beta_template.find_resources(
        "AWS::Events::Rule"
    )

    assert len(rules) >= 1

    scheduled_rules = [
        resource
        for resource in rules.values()
        if "ScheduleExpression" in resource["Properties"]
    ]

    assert len(scheduled_rules) == 1

    rule_properties = scheduled_rules[0]["Properties"]

    assert rule_properties["State"] == "ENABLED"
    assert len(rule_properties["Targets"]) == 1


def test_alarm_table_schema(beta_template):
    tables = beta_template.find_resources(
        "AWS::DynamoDB::Table"
    )

    assert len(tables) == 2

    alarm_tables = [
        resource["Properties"]
        for resource in tables.values()
        if resource["Properties"].get("TableName")
        == "Kartikey-Website-Alarm-Logs-beta"
    ]

    assert len(alarm_tables) == 1

    alarm_table = alarm_tables[0]

    assert alarm_table["BillingMode"] == "PAY_PER_REQUEST"

    assert {
        "AttributeName": "alarm_id",
        "KeyType": "HASH",
    } in alarm_table["KeySchema"]

    assert {
        "AttributeName": "timestamp",
        "KeyType": "RANGE",
    } in alarm_table["KeySchema"]

def test_target_table_schema(beta_template):
    tables = beta_template.find_resources(
        "AWS::DynamoDB::Table"
    )

    target_tables = [
        resource["Properties"]
        for resource in tables.values()
        if resource["Properties"].get("TableName")
        == "Kartikey-Website-Targets-beta"
    ]

    assert len(target_tables) == 1

    target_table = target_tables[0]

    assert target_table["BillingMode"] == "PAY_PER_REQUEST"

    assert target_table["KeySchema"] == [
        {
            "AttributeName": "target_id",
            "KeyType": "HASH",
        }
    ]

    assert target_table["AttributeDefinitions"] == [
        {
            "AttributeName": "target_id",
            "AttributeType": "S",
        }
    ]

def test_logger_uses_correct_table(beta_template):
    functions = beta_template.find_resources(
        "AWS::Lambda::Function"
    )

    logger_functions = [
        resource
        for resource in functions.values()
        if resource["Properties"].get("Handler")
        == "alarmLogger.handler"
    ]

    assert len(logger_functions) == 1

    logger = logger_functions[0]["Properties"]

    variables = logger["Environment"]["Variables"]

    assert "ALARM_TABLE_NAME" in variables


def test_sns_subscription_targets_logger(beta_template):
    subscriptions = beta_template.find_resources(
        "AWS::SNS::Subscription"
    )

    assert len(subscriptions) == 1

    subscription = next(iter(subscriptions.values()))
    properties = subscription["Properties"]

    assert properties["Protocol"] == "lambda"
    assert "TopicArn" in properties
    assert "Endpoint" in properties


def test_all_alarms_use_beta_metrics_and_topic(beta_template):
    """
    Week 11 monitoring test.

    The Beta environment contains:

    - 6 website health alarms:
      3 availability + 3 latency

    - 3 crawler operational alarms:
      Errors + Duration + Throttles

    All alarms must notify the Beta SNS topic.
    """

    alarms = beta_template.find_resources(
        "AWS::CloudWatch::Alarm"
    )

    topics = beta_template.find_resources(
        "AWS::SNS::Topic"
    )

    topic_id = next(iter(topics))

    # Six website alarms + three operational alarms.
    assert len(alarms) == 9

    website_alarm_count = 0
    crawler_alarm_count = 0

    for alarm in alarms.values():
        properties = alarm["Properties"]

        # Every alarm must notify the environment's SNS topic.
        assert {"Ref": topic_id} in properties["AlarmActions"]

        # Existing website metrics are synthesized using a
        # Metrics array and our environment-specific namespace.
        if "Metrics" in properties:
            metric = (
                properties["Metrics"][0]
                ["MetricStat"]
                ["Metric"]
            )

            assert metric["Namespace"] == (
                "Kartikey/WebsiteMonitoring/Beta"
            )

            website_alarm_count += 1

        # Week 11 crawler operational alarms use the standard
        # AWS/Lambda namespace.
        else:
            assert properties["Namespace"] == "AWS/Lambda"

            assert properties["MetricName"] in {
                "Errors",
                "Duration",
                "Throttles",
            }

            crawler_alarm_count += 1

    assert website_alarm_count == 6
    assert crawler_alarm_count == 3


def test_beta_and_prod_names_do_not_overlap():
    """
    Beta and Prod must use separate physical resources.

    Both stacks are created before either one is synthesized so
    the CDK construct tree is not modified after synthesis.
    """

    app = cdk.App()

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

    beta_functions = beta.find_resources(
        "AWS::Lambda::Function"
    )

    prod_functions = prod.find_resources(
        "AWS::Lambda::Function"
    )

    beta_function_names = {
        resource["Properties"]["FunctionName"]
        for resource in beta_functions.values()
        if "FunctionName" in resource["Properties"]
    }

    prod_function_names = {
        resource["Properties"]["FunctionName"]
        for resource in prod_functions.values()
        if "FunctionName" in resource["Properties"]
    }

    assert beta_function_names.isdisjoint(
        prod_function_names
    )

    beta_tables = beta.find_resources(
        "AWS::DynamoDB::Table"
    )

    prod_tables = prod.find_resources(
        "AWS::DynamoDB::Table"
    )

    beta_table_names = {
        resource["Properties"]["TableName"]
        for resource in beta_tables.values()
    }

    prod_table_names = {
        resource["Properties"]["TableName"]
        for resource in prod_tables.values()
    }

    assert beta_table_names.isdisjoint(
        prod_table_names
    )

    beta_topics = beta.find_resources(
        "AWS::SNS::Topic"
    )

    prod_topics = prod.find_resources(
        "AWS::SNS::Topic"
    )

    beta_topic_names = {
        resource["Properties"]["TopicName"]
        for resource in beta_topics.values()
    }

    prod_topic_names = {
        resource["Properties"]["TopicName"]
        for resource in prod_topics.values()
    }

    assert beta_topic_names.isdisjoint(
        prod_topic_names
    )

    beta_dashboards = beta.find_resources(
        "AWS::CloudWatch::Dashboard"
    )

    prod_dashboards = prod.find_resources(
        "AWS::CloudWatch::Dashboard"
    )

    beta_dashboard_names = {
        resource["Properties"]["DashboardName"]
        for resource in beta_dashboards.values()
    }

    prod_dashboard_names = {
        resource["Properties"]["DashboardName"]
        for resource in prod_dashboards.values()
    }

    assert beta_dashboard_names.isdisjoint(
        prod_dashboard_names
    )