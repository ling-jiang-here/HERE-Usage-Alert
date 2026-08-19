Excellent choice. If you're starting today, I would not build a traditional "scheduled CSV report" solution. Instead, I would build an AI-Driven Usage Intelligence Platform on top of the HERE Usage API.

The goal is not only to answer"What was yesterday's usage?", but also:

Detect anomalies automatically
Predict end-of-month consumption
Explain root causes using AI
Generate executive reports automatically
Alert the right teams before overages occur
Create a natural-language chatbot for usage investigation

The HERE Usage API and Usage Reports provide the data foundation for this approach.

Target Architecture
Plain Text
1
HERE Usage API
2
|
3
v
4
Azure Data Factory
5
(or GitHub Actions)
6
|
7
v
8
Azure Data Lake Storage
9
|
10
+-------------------+
11
| |
12
v v
13
Databricks Azure AI Foundry
14
(Data Processing) (LLM Analysis)
15
| |
16
+----------+--------+
17
|
18
v
19
Usage Intelligence Layer
20
|
21
+-------------+-------------+
22
| |
23
v v
24
Power BI Teams Copilot Bot
25
Dashboard Natural Language Q&A
26
|
27
v
28
Automated Reports
Show more lines
Phase 1 - Foundation (Weeks 1-2)
Objectives

Build a reliable data pipeline.

Deliverables
Data Retrieval

Use HERE Usage API to collect:

Daily usage
Weekly usage
Monthly usage

Group data by:

App ID
Feature ID
Project
Billing Tag

Supported usage dimensions are available through HERE Cost Management Usage services.

Storage

Recommended:

Plain Text
1
Azure Data Lake Gen2
Show more lines

Why:

Cheap
Scalable
AI-ready
Native Microsoft ecosystem
Data Model
Plain Text
1
Date
2
Organization
3
Project
4
AppID
5
Feature
6
Transactions
7
Cost
8
BillingTag
Show more lines

Store raw and curated layers.

Plain Text
1
Bronze
2
Silver
3
Gold
Show more lines

following modern lakehouse practices.

Phase 2 - Operational Dashboard (Weeks 2-4)
Power BI Dashboard

Create:

Executive Page

KPIs:

Plain Text
1
Total Transactions
2
Daily Change %
3
Monthly Forecast
4
Top Cost Driver
5
Top AppID
Show more lines
Operations Page

Charts:

Daily consumption
Feature usage trends
Usage by AppID
Hourly pattern
Cost trend
Investigations Page
Plain Text
1
Top 20 Consumers
2
Top Growth Features
3
Failed APIs
4
Abnormal Applications
Show more lines
Phase 3 - AI-Powered Anomaly Detection (Weeks 4-6)

This is where the project becomes modern.

Traditional Rules
Plain Text
1
Current Usage > Average × 1.5
Show more lines

This catches basic spikes.

Machine Learning Layer

Use:

Plain Text
1
Azure Databricks
2
MLflow
3
Prophet
4
Isolation Forest
5
XGBoost
Show more lines

Detect:

Unexpected growth
New consumption pattern
Service abuse
Key leakage
Infinite loops

Example:

Plain Text
1
Normal Daily Routing Usage
2
 
3
15K
4
18K
5
20K
6
17K
7
19K
8
 
9
Detected
10
 
11
150K
12
 
13
=> Anomaly Score 0.97
14
 
Show more lines
Phase 4 - Generative AI Investigation (Weeks 6-8)

This is the cutting-edge layer.

Azure OpenAI / GPT

Instead of showing charts only:

Generate findings.

Example output:

Plain Text
1
Root Cause Analysis
2
 
3
Traffic API usage increased 237%
4
between 15-Aug and 16-Aug.
5
 
6
95% of the traffic originated from:
7
 
8
AppID:
9
fleet-prod-asia
10
 
11
Possible causes:
12
 
13
1. New rollout
14
2. Increased polling frequency
15
3. API retry storm
16
 
17
Recommended Actions:
18
 
19
- Review release records
20
- Verify cache behavior
21
- Validate retry policies
Show more lines

AI creates summaries automatically from HERE usage data.

Phase 5 - Predictive Forecasting

Use:

Plain Text
1
Azure ML
2
Databricks
3
Time Series Models
Show more lines

Forecast:

End-of-month usage
Contract consumption
Budget burn rate

Example:

Plain Text
1
Current Month Forecast
2
 
3
Traffic API
4
 
5
Actual:
6
2.1M
7
 
8
Forecast:
9
3.8M
10
 
11
Contract Limit:
12
3.0M
13
 
14
Risk:
15
HIGH
Show more lines

This provides intervention time before overages.

Phase 6 - Teams Copilot Agent

A very attractive capability for leadership teams.

Build a Copilot Studio agent.

Users ask:

Plain Text
1
Which application consumed the most
2
transactions last week?
Show more lines
Plain Text
1
Why did Routing API usage increase?
Show more lines
Plain Text
1
Show anomalies during August.
Show more lines

The agent:

Queries Power BI semantic model
Retrieves usage data
Uses GPT reasoning
Produces an explanation

No dashboard navigation required.

Phase 7 - Intelligent Alerting

Instead of simple threshold alerts, build AI-based alerts.

HERE supports usage alerts and notifications.

Severity Levels
P1
Plain Text
1
300% increase
Show more lines

Immediate Teams message.

P2
Plain Text
1
150% increase
Show more lines

Email + Teams.

P3
Plain Text
1
Monthly forecast exceeds budget
Show more lines

Weekly management report.

Alert Channels
Microsoft Teams
Outlook
ServiceNow
Azure Monitor
Webhook
Phase 8 - Executive AI Reporting

Every Monday morning:

AI generates:

Plain Text
1
HERE Weekly Usage Intelligence Report
Show more lines

Sections:

Executive Summary
Plain Text
1
Usage up 18%
2
 
3
Main reason:
4
Traffic API growth
5
 
Show more lines
Top Consumers
Plain Text
1
1. Fleet-App
2
2. Navigator-App
3
3. Dispatch-App
Show more lines
Risks
Plain Text
1
Routing forecast exceeds budget
2
by 12%
3
 
Show more lines
Recommendations
Plain Text
1
Enable result caching
2
 
3
Reduce polling interval
Show more lines

Send automatically:

Outlook email
Teams channel
SharePoint PDF archive
Recommended Microsoft Technology Stack (2026)
Layer	TechnologyIngestion	HERE Usage API
Orchestration	Azure Data Factory
Storage	Azure Data Lake Gen2
Processing	Azure Databricks
AI/LLM	Azure OpenAI
Forecasting	Azure ML
Dashboard	Power BI
Agent	Copilot Studio
Alerts	Azure Monitor + Teams
Governance	Microsoft Purview
Success Metrics

After deployment, the solution should achieve:

100% automated usage collection
Daily anomaly detection
Monthly forecast accuracy > 90%
Alert latency < 15 minutes
Executive report generation < 5 minutes
Natural-language investigation through Copilot

This turns the basic HERE Usage Report capability into an AI-powered FinOps and API Consumption Intelligence platform, aligning with current Microsoft Copilot, Azure AI, lakehouse, and agentic-AI trends while leveraging HERE's Usage API and Alert capabilities as the authoritative data source.

Provide your feedback on BizChat
Sources
You said:
Microsoft Azure is not free. I want a free solution.
Copilot said:

If your goal is free (or nearly free) and still follows modern AI trends, I would avoid Azure, Databricks, Power BI Premium, and Copilot Studio altogether.

A practical approach is to build a"GitHub + Python + Open Source AI" solution.

Recommended Free Architecture
Plain Text
1
HERE Usage API
2
|
3
v
4
GitHub Actions (Scheduler)
5
|
6
v
7
Python Analysis
8
|
9
+--> CSV History
10
|
11
+--> Anomaly Detection
12
|
13
+--> AI Summary
14
|
15
+--> Email / Teams Webhook
16
|
17
v
18
GitHub Pages Dashboard
Show more lines

Cost:

Plain Text
1
$0
Show more lines

for small-to-medium workloads.

Option A: GitHub Actions + HERE Usage API

GitHub Actions can run on a schedule:

YAML
1
daily at 08:00
2
weekly on Monday
3
monthly on day 1
Show more lines

The workflow:

Call HERE Usage API.
Download usage data.
Save CSV files.
Compare with historical values.
Generate report.
Send email or Teams alert.

HERE provides Usage API and CSV-based reporting capabilities for retrieving usage by organization, app, feature, project, and billing tag.

Advantages:

Free
No server
Source controlled
Easy to maintain
Option B: Anomaly Detection Using Open Source AI

Instead of simple threshold checks:

Plain Text
1
Usage > 150%
Show more lines

use machine learning.

Python libraries:

Plain Text
1
scikit-learn
2
Prophet
3
PyOD
Show more lines

Example:

Plain Text
1
Normal:
2
1000
3
1200
4
1100
5
1300
6
 
7
Current:
8
12000
Show more lines

Model flags:

Plain Text
1
Anomaly Score = 0.99
Show more lines

This is much more intelligent than fixed thresholds.

Option C: Local LLM for AI Analysis

Instead of Azure OpenAI:

Use:

Plain Text
1
Ollama
2
Llama 3.3
3
Qwen 3
4
Gemma
5
Mistral
Show more lines

All free.

Sample prompt:

Plain Text
1
Analyze the following HERE API
2
usage data.
3
 
4
Find:
5
 
6
- Abnormal spikes
7
- Most expensive APIs
8
- Likely root causes
9
- Recommended actions
10
 
Show more lines

Generated result:

Plain Text
1
Routing API increased
2
276% compared with
3
30-day baseline.
4
 
5
Most traffic originates from:
6
 
7
app-prod-routing
8
 
9
Possible causes:
10
 
11
- production rollout
12
- retry storm
13
- missing cache
14
 
15
Recommendation:
16
 
17
review deployment logs.
Show more lines

This gives you GPT-style explanations without a cloud AI bill.

Option D: Free Dashboard

Instead of Power BI:

Grafana

Free and widely used.

Dashboard pages:

Executive
Daily usage
Monthly trend
Forecast
Engineering
By App ID
By Feature
By Project
Anomalies
Top spikes
Risk score
Option E: Teams Notifications

Send alerts directly to Teams.

Create an Incoming Webhook and send messages such as:

Plain Text
1
🚨 HERE Usage Alert
2
 
3
Feature:
4
Routing
5
 
6
Current:
7
152,341
8
 
9
Average:
10
48,901
11
 
12
Increase:
13
211%
14
 
15
Confidence:
16
High
Show more lines

No licensing cost.

Option F: AI Weekly Report

Every Monday:

GitHub Action runs:

Plain Text
1
1. Fetch data
2
2. Detect anomalies
3
3. Generate charts
4
4. Ask local LLM for summary
5
5. Email report
Show more lines

Example output:

Plain Text
1
Weekly HERE Usage Intelligence
2
 
3
Summary
4
 
5
Total usage increased 12%.
6
 
7
Main contributor:
8
 
9
Traffic API
10
 
11
Abnormal events:
12
 
13
Routing API
14
+220%
15
 
16
Forecast:
17
 
18
Current trend suggests
19
monthly usage will exceed
20
average by 18%.
Show more lines
Recommended Stack (100% Free)
Component	TechnologyScheduler	GitHub Actions
Storage	GitHub Repo CSV Files
Analysis	Python
ML	scikit-learn
Forecast	Prophet
Dashboard	Grafana Community
AI	Ollama + Qwen/Llama
Notification	Teams Webhook
Source Control	GitHub
My Recommendation

As a support engineer, I would build Phase 1 like this:

Plain Text
1
HERE Usage API
2
↓
3
GitHub Actions (daily)
4
↓
5
Python script
6
↓
7
Anomaly detection
8
↓
9
Teams notification
10
↓
11
Weekly AI report
Show more lines

You can get a working MVP in 1-2 days, with zero Azure cost, while still incorporating modern AI capabilities through local LLMs and machine-learning-based anomaly detection.

Provide your feedback on BizChat
Sources
You said:
what is MVP?
Copilot said:

MVP stands for Minimum Viable Product.

In your case, it means building the smallest solution that delivers real value, before investing time in advanced AI features.

For your HERE Usage Monitoring project

An MVP would include only the essentials:

Plain Text
1
HERE Usage API
2
↓
3
GitHub Action (daily schedule)
4
↓
5
Python Script
6
↓
7
Detect abnormal usage
8
↓
9
Send Teams notification
Show more lines
What the MVP does

Every day:

Query HERE Usage API.
Retrieve yesterday's usage.
Compare with the previous 30-day average.
Identify anomalies.
Generate a simple report.
Send results to Teams or Email.

Example:

Plain Text
1
HERE Usage Report
2
 
3
Date: 2026-08-18
4
 
5
Routing API
6
Yesterday: 125,000
7
30-day Average: 35,000
8
 
9
Increase: +257%
10
 
11
Status: ANOMALY
12
 
13
Top App ID:
14
fleet-prod-app
15
 
Show less
What is NOT included in the MVP

To keep it simple and free, do not build these initially:

❌ Grafana dashboards

❌ LLM integration (Ollama/Llama)

❌ Forecasting models

❌ Root cause analysis

❌ Chatbot

❌ Monthly executive reports

Phase 2 (After MVP Works)

Add a dashboard:

Plain Text
1
HERE Usage API
2
↓
3
GitHub Actions
4
↓
5
Python
6
↓
7
SQLite Database
8
↓
9
Grafana Dashboard
Show more lines

Now you can visualize:

Daily trends
Most-used APIs
Top App IDs
Historical consumption
Phase 3 (AI Version)

Add a local LLM:

Plain Text
1
Python Analysis
2
↓
3
Ollama + Qwen
4
↓
5
AI-generated Summary
Show more lines

Example output:

Routing API usage increased 257% compared to the historical baseline. Most traffic originated from fleet-prod-app. A recent deployment or retry storm may be responsible. Review application logs and API call patterns.

Suggested Roadmap

Week 1 (MVP)

HERE Usage API integration
GitHub Actions scheduler
CSV history storage
Teams alerts

Week 2

Historical trend analysis
Weekly report generation

Week 3

Grafana dashboard

Week 4

Local AI summaries using Ollama

As a support engineer, I'd start with the Week 1 MVP. It's likely less than 500 lines of Python, costs $0, and already solves the main problem of automatically finding abnormal HERE API consumption.