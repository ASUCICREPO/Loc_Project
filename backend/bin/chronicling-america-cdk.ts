#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { ChroniclingAmericaStack } from "../lib/chronicling-america-stack";

const app = new cdk.App();

// Get context parameters
const projectName =
  app.node.tryGetContext("projectName") || "chronicling-america-pipeline";
const dataBucketName = app.node.tryGetContext("dataBucketName");
const bedrockModelId =
  app.node.tryGetContext("bedrockModelId") ||
  "anthropic.claude-3-5-sonnet-20241022-v2:0";

new ChroniclingAmericaStack(app, "LOCstack", {
  projectName,
  dataBucketName,
  bedrockModelId,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || "us-west-2",
  },
  description:
    "Historical newspaper data extraction pipeline with Bedrock and Neptune (v2)",
});

app.synth();
