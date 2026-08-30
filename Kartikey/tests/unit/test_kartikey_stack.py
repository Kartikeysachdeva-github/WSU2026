import aws_cdk as core
import aws_cdk.assertions as assertions

from kartikey.kartikey_stack import KartikeyStack

# example tests. To run these tests, uncomment this file along with the example
# resource in kartikey/kartikey_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = KartikeyStack(app, "kartikey")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
