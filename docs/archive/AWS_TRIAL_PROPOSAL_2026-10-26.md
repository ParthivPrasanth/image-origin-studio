# Mumbai AWS trial proposal — 26 October 2026

> **Historical planning record.** The owner deployed the public site on 29
> October 2026 and later chose a **USD 20** planning ceiling. This document's
> USD 35 figures and “no resources” statements describe the earlier proposal;
> they are not the current cost limit or deployment status. Use the
> [deployment and operations guide](../DEPLOYMENT.md) and live AWS Billing for
> current decisions.

Status: **proposal for owner review, not a deployment or final AWS quote**. No
AWS resources have been created. This document completes the local architecture
and spending worksheet part of [Phase 3](AWS_IMPLEMENTATION_PLAN.md); exact
regional prices, account-specific service access, and the spending setup remain
launch gates.

## Owner inputs and trial boundary

- Preferred location: an India region. Use **Asia Pacific (Mumbai),
  `ap-south-1`**, for the first trial.
- On **29 October 2026**, the owner supplied AWS Billing screenshots showing a
  **Free plan**, **USD 100.00 credits remaining**, **183 days remaining**, and
  free access ending **29 April 2027** or when credits are depleted. This is
  screenshot evidence, not a live account connection or a guarantee that every
  proposed service/feature is enabled. The separate Credits page showed USD
  0.00 and no active credits. AWS directs Free-plan users to the plan widget
  for their balance and Paid-plan users to the Credits page, which explains
  why these displays need not match. The Billing cost summary failed to load
  in the screenshot, and no budget was configured. [AWS Free Tier tracking](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/tracking-free-tier-usage.html).
- The intended public run is **7–14 days**, starting when the cloud version is
  ready, possibly within the next one or two weeks. Stop and tear down after
  the trial rather than leave resources running for a full month.
- Proposed **USD 35 maximum trial spend before credits**, with alerts at USD
  10, 20, and 30. The operator checks cost daily and starts teardown at USD
  25 if a spike is developing. This threshold needs the owner's review before
  resources are created. [AWS Budgets alerts are not a hard spending
  cap](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

New AWS Free plans provide signup credit but can end after six months or when
credits are used; Paid plans can bill beyond available credits. The observed
Free-plan widget is the current account evidence; recheck it before launch and
during the trial. See [AWS account
plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
and [Free Tier tracking](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/tracking-free-tier-usage.html).

## Selected design

| Part | Trial resource | Purpose and limit |
| --- | --- | --- |
| Region | `ap-south-1` | Keep compute, private storage, metadata, and Cognito in Mumbai. |
| Compute | One Linux amd64 `t3.small` EC2 instance, 2 vCPU/2 GiB, with an IAM instance profile | Run the existing CPU Docker image. Begin with one API worker and a bounded request queue; verify on actual EC2 before opening public traffic. Set T3 CPU credits to **standard**, then monitor credit balance and latency; unlimited is the default and can add surplus-credit charges. |
| Disk | One 20 GiB gp3 root EBS volume | OS, container layers, and pinned model cache only. No retained original images on disk. Disable automatic snapshot/backup creation for this disposable trial. |
| Web | Reverse proxy on the instance, one public IPv4/Elastic IP, ports 80 and 443 only | Serve the built React app and `/api` from one HTTPS origin. Port 80 is for certificate validation and redirects. No ALB, NAT gateway, CloudFront, or separate frontend host. |
| Login | One Cognito user pool and public app client, authorization code + PKCE | Only History requires login. Guest analysis stays available without a saved record. Avoid SMS and paid messaging features. |
| Originals | One private S3 bucket with Block Public Access | Exact opted-in originals under opaque owner-scoped keys, never a public object URL. |
| Metadata | One DynamoDB on-demand Standard table | Owner-scoped saved result metadata, object key, expiry, delete state, and atomic quota accounting. No separate database server. |
| Logs/cost | Minimal application/instance logs, one AWS Budget | No original bytes, tokens, or private URLs in logs. Short log retention and daily cost review. |

Request/data flow: browser uploads to the API over HTTPS; the API runs the two
models synchronously and returns suggestions. A guest or a signed-in user with
saving off leaves no durable result. For an opted-in signed-in save, the API
validates the Cognito token, enforces the account/global limits, writes original
bytes to private S3 and result metadata to DynamoDB, and returns an owner-scoped
history ID. Reopen and delete always check the token's subject against the
record owner. EC2 accesses S3 and DynamoDB through a least-privilege **instance
role**, not stored access keys. No queue is planned because the measured local
path was synchronous; add one only if EC2 load results show a need.

The current [readiness checkpoint](AWS_READINESS_2026-10-26.md) ran the image
under a local 2 CPU/2 GiB limit and recorded a 547 MiB peak for a small sample.
That supports `t3.small` as a *trial starting size*, not a capacity guarantee.
The host must pass a fresh uncached startup, both-model parity, concurrent
uploads, and memory/CPU checks before public traffic. [AWS documents the
eligible EC2 instance choices for newer
accounts](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-launch-parameters.html)
and [T3 Unlimited's possible extra
charges](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-unlimited-mode.html).

### HTTPS and sign-in gate

Use an existing owner-controlled domain if available. If there is no domain,
try a Let's Encrypt certificate for the Elastic IP with automated renewal;
IP certificates last about **160 hours**, so renewal and a reboot check are
mandatory during a two-week trial. [Let's Encrypt IP certificate
announcement](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability),
[Certbot support](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html).
Cognito requires a pre-registered absolute **HTTPS** callback outside
localhost. Its documentation does not establish that an HTTPS IP callback will
work for this app, so test the full PKCE return flow before public launch.
If that test fails, choose a domain-backed HTTPS endpoint and reprice it;
do not run public login over HTTP. [Cognito callback
requirements](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-client-apps.html).

## Cost worksheet (USD, before promotional credits and tax)

Assumptions: one instance continuously on for 24 hours or 14 days; 20 GiB
gp3; one public IPv4; at most ten trial accounts, ten saved images and 50 MiB
per account, 500 MiB saved originals globally, 30-day maximum retention, and
modest guest traffic. Guest inference is limited by request controls, **not**
by the saved-image quota. Transfer and API request amounts are not known
until trial traffic is measured.

The EC2 and EBS rates below are deliberately **planning allowances, not
verified Mumbai prices**: USD 0.030 per instance-hour and USD 0.10 per
GiB-month for gp3. Verify the current `ap-south-1` Linux `t3.small` and gp3
prices in the AWS Pricing Calculator/account before launch. The public IPv4
rate is AWS's published USD 0.005/hour. [EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/),
[EBS pricing](https://aws.amazon.com/ebs/pricing/),
[public IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

| Item | 24 hours | 14 days | 30 days if teardown is missed | Basis |
| --- | ---: | ---: | ---: | --- |
| EC2 planning allowance | 0.72 | 10.08 | 21.60 | USD 0.030/hour, provisional |
| Public IPv4 | 0.12 | 1.68 | 3.60 | USD 0.005/hour, published |
| 20 GiB gp3 planning allowance | 0.07 | 0.93 | 2.00 | USD 0.10/GiB-month, provisional, 30-day accounting month |
| S3, DynamoDB, Cognito, and logs reserve | 0.36 | 5.00 | 10.00 | Planning reserve, **not** an AWS quote |
| Internet egress and incidental reserve | 0.21 | 3.00 | 6.00 | Planning reserve, **not** an AWS quote |
| **Planning envelope** | **1.48** | **20.69** | **43.20** | Before credits/tax; actual cost can differ |

There is no separate frontend, queue, load balancer, NAT gateway, or CDN line
because this design creates none. The 14-day envelope leaves about USD 14 of
headroom below the proposed USD 35 trial stop. A 30-day accidental run would
exceed that stop, which is why daily review and scheduled teardown matter.
S3 storage/requests, DynamoDB reads/writes/storage, Cognito active users,
CloudWatch/logging, and outbound transfer must be checked at their current
Mumbai rates and account-specific Free Tier/credit eligibility before launch:
[S3](https://aws.amazon.com/s3/pricing/),
[DynamoDB](https://aws.amazon.com/dynamodb/pricing/),
[Cognito](https://aws.amazon.com/cognito/pricing/).
Taxes, exchange-rate effects, and any service not listed are excluded. Do not
interpret unused promotional credits as an exemption from monitoring spend.

## Privacy, retention, and deletion

- Keep the existing opt-in behavior. No original is persisted for a guest or
  when saving is off. Disable `IOS_LOCAL_TEST_AUTH` on the public host.
- Retain saved originals and metadata for **at most 30 days**; trial teardown
  can delete them sooner. Enforce ten records and 50 MiB per account plus
  500 MiB globally, with the current upload-size limit enforced at the edge
  and in the API.
- S3 Block Public Access on all four settings; no public ACLs/policies. Use
  server-side encryption and scoped role permissions. [S3 private-access
  guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html).
- Expiry and user delete must deny API reads immediately, then remove S3 bytes
  and DynamoDB metadata with retry/reconciliation. The first cloud adapter
  uses an app sweep and a 32-day S3 lifecycle backstop. **Do not enable
  DynamoDB TTL** on its records: automatic deletion would bypass S3 cleanup
  and quota-counter updates. Disabling S3 versioning avoids old versions
  surviving ordinary deletes. Lifecycle deletion is asynchronous.
  [S3 lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html),
  [DynamoDB TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html).
- Avoid retained EBS snapshots, S3 replication, and backup copies for the
  disposable trial. Any newly added backup changes retention and cost and must
  be reviewed before launch.

## Launch gates in order

1. Recheck the Free-plan widget's USD **balance and expiry** immediately before
   launch. Confirm access to the selected services and features in Mumbai.
   The 29 October screenshot gives a starting balance/expiry, but does not
   establish live service access or a working cost breakdown. Trial resources
   still consume credits; avoid any action that upgrades the account plan.
2. Replace provisional EC2/EBS rates and service reserves with a timestamped
   Mumbai quote for this resource list; record taxes if applicable. Owner
   reviews the numeric USD 35 stop, alert thresholds, and teardown inventory.
3. Implement hosted Cognito login/token verification and S3/DynamoDB history
   adapters with the existing guest/save contracts, deletion, expiry, quota,
   ownership, and retry behavior. Keep locally working tests.
4. Provision through reproducible configuration with least-privilege IAM and
   tags identifying the trial; create the Budget before the compute host.
5. Before a public link, verify actual EC2 memory/CPU/latency, cold model
   cache, C2PA on original bytes, signed-in and guest flows, HTTPS renewal,
   private object access, 30-day/delete behavior, quotas, failure paths, and
   a one-day cost reading. Stop or downsize if the host or estimate fails.
6. Run for up to 14 days with daily cost/health checks. Tear down at end date,
   at USD 25 if spending accelerates, or at the USD 35 maximum even if the
   account still shows promotional credits.

## Teardown inventory and order

1. Record the last cost view and resource IDs; close/disable public ingress
   and stop the EC2 instance so new analyses and saves cannot start.
2. Use the app's delete path for test accounts and saved items; list S3 and
   DynamoDB directly to verify that no original or metadata is left. Resolve
   failed deletes, then empty and delete the S3 bucket (including any versions
   if versioning was ever enabled) and delete the DynamoDB table.
3. Delete the Cognito test users, app client/domain, and user pool. Delete the
   AWS Budget and any log groups/alarms created solely for the trial after
   exporting only non-sensitive operational evidence needed for the report.
4. Terminate EC2; check and delete any leftover EBS volume/snapshot, release
   the Elastic IP, remove the instance role/policies, reverse-proxy TLS
   configuration/secrets, security group, and any dedicated DNS record.
5. Inventory `ap-south-1` and other regions for remaining trial resources;
   verify Billing after its normal reporting delay and record final actual
   pre-credit and out-of-pocket cost. No resources should be left running.

## Decision and fallback

Primary: the single EC2 + Cognito + private S3 + DynamoDB design above. It
preserves the requested optional private History and makes deletion auditable.
If `t3.small` fails actual load or the estimated 14-day spend exceeds USD 35,
pause public launch and resize/reprice. If the IP certificate plus Cognito
callback cannot be made reliable, use an existing domain and reprice its DNS
and TLS path. A one-host local-history demo would be cheaper but would not
meet the durable private-history goal, so it is not the selected release.
