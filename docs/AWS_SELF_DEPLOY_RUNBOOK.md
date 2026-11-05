# Self-managed Mumbai trial deployment

**Status update, 29 October 2026:** the owner used this approach for a public
deployment and confirmed the HTTPS site, both models, Cognito sign-in, and one
History save. See the [maintained deployment guide](DEPLOYMENT.md) for current
status and remaining checks. This runbook retains the manual setup and teardown
procedure for the small Mumbai deployment; some prelaunch instructions below
describe the sequence that was planned, not independently verified host state.
Keep AWS credentials, account IDs, private key material, and private originals
out of Git. The public site address appears in the README.

## What each service does

| Service | Job |
| --- | --- |
| EC2 `t3.small` | Runs the CPU inference API and serves the website. |
| EBS gp3 | Holds the operating system, image, and model cache during the trial. |
| S3 | Stores only original image bytes when a signed-in user opts to save. |
| DynamoDB | Stores saved result metadata, ownership, expiry, delete state, and quota counters. |
| Cognito | Signs in users who want private History; guests can analyze without it. |
| AWS Budgets | Emails cost warnings; it does **not** stop spending automatically. |

The application uses one same-origin HTTPS endpoint. There is no load balancer,
queue, NAT gateway, CDN, database server, or permanent access key in the
selected trial. The EC2 instance role supplies S3/DynamoDB credentials to the
container through IMDSv2. The public site must not expose port 8001.

## 0. Record prices and decide the launch limit

Before creating any billable resource, fill a copy of this worksheet using the
[AWS Pricing Calculator](https://calculator.aws/) or current `ap-south-1`
console prices. The [proposal's figures](archive/AWS_TRIAL_PROPOSAL_2026-10-26.md)
are allowances, not a Mumbai quote.

| Line | Exact Mumbai rate or estimate to record |
| --- | --- |
| Linux `t3.small`, standard CPU credits, 336 hours maximum | ___ |
| 20 GiB gp3 EBS for 14 days | ____ |
| One public IPv4 for 14 days | ____ |
| S3: at most 500 MiB originals, requests, download/egress | ____ |
| DynamoDB on-demand reads/writes/storage; estimate for 10 test accounts and 100 records | ____ |
| Cognito Lite/Essentials; estimate for 10 active users, no SMS | ____ |
| Logs, budget, taxes, and contingency | ____ |
| **14-day total before credits/tax as applicable** | **____** |

The owner's later planning ceiling is **USD 20 before credits**, superseding
the original USD 35 proposal. Check actual usage and remaining headroom in AWS
Billing before continuing the deployed trial. In AWS Billing,
recheck the Free-plan balance and its expiry. The 29 October screenshot showed
USD 100 and an end date of 29 April 2027, but the live balance may change.
Create or verify **one USD 20 cost budget** with email alerts before the limit,
for example at absolute USD 5, 10, and 15, plus a forecast alert if useful.
The available deployment record does not confirm that a budget was created.
Choose **unblended costs** so the
alerts reflect resource usage before credits; net unblended costs subtract
credits and could stay at zero during this trial. A budget can have several alerts;
notifications may lag actual usage. Do not upgrade the account plan just to
follow this guide. [AWS Budgets pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/),
[alert thresholds](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-action-configure.html),
[reporting delay](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

Stop here if the live quote exceeds the accepted limit, the Free plan blocks a
required service, or the owner has not reviewed the final service/cost list.

## 1. Prepare private storage and identity in the AWS console

Stay in **Asia Pacific (Mumbai), `ap-south-1`** for every regional service.
Record generated names/IDs in a private operator note, never in this repo.

1. **S3:** Create one uniquely named bucket for originals. Enable all four
   Block Public Access settings, keep ACLs disabled and versioning off, and
   use default SSE-S3 encryption. Add an expiration rule for the `originals/`
   prefix at **32 days** as a backup cleanup. The API enforces 30-day access
   expiry and deletes S3 bytes itself. Do not enable replication.
2. **DynamoDB:** Create one Standard table with string partition key `pk` and
   string sort key `sk`. Choose on-demand capacity. Leave TTL **disabled**:
   automatic record removal would bypass S3 deletion and the transactional
   quota counters. Leave point-in-time recovery/backups off for this disposable
   trial, after accepting that saved test history will not be recoverable.
3. **IAM:** Create an EC2 instance role with a custom policy copied from
   [`infra/iam-policy.json.template`](../infra/iam-policy.json.template).
   Replace `__BUCKET_NAME__`, `__TABLE_NAME__`, and `__ACCOUNT_ID__` with the
   actual values. Attach only this role to the trial instance. It permits
   original-object operations under `originals/` and the required actions on
   the one DynamoDB table. No local AWS access key is placed on the instance.

S3 lifecycle and DynamoDB TTL are asynchronous. The application checks expiry
before reads and retries deletion. [S3 expiration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html),
[DynamoDB TTL behavior](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html).

## 2. Create one EC2 host

1. Launch **Ubuntu Server 24.04 LTS x86_64** on a `t3.small`, with a **20 GiB
   gp3** root disk that deletes on termination. Set T3 credit mode to
   **standard** to avoid surplus-credit charges. Use an EC2 key pair whose
   private key stays only on your PC.
2. Attach the role from step 1. Require **IMDSv2** and set its response hop
   limit to **2** so the Docker container can obtain role credentials. [AWS
   container IMDS guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-IMDS-new-instances.html).
3. Security group: SSH port 22 **only from your current IP**, HTTP 80 and
   HTTPS 443 from public clients; no inbound port 8001. Use one Elastic IP so
   the HTTPS address and Cognito callback remain stable. Record the IP and
   instance ID. Do not add an ALB or NAT gateway.
4. Log in over SSH. Install Docker, Nginx, Python virtual-environment support,
   and cron using Ubuntu packages. Create `/var/www/image-origin-studio` for
   the static build and ACME challenge files. On a fresh Ubuntu host:

   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io nginx python3-venv cron
   sudo systemctl enable --now docker nginx cron
   sudo mkdir -p /var/www/image-origin-studio
   ```

5. **Cognito:** Now that you know the stable Elastic IP, create one user pool
   for email/password sign-in, with email verification, self-registration
   enabled, and no SMS. The 10-user worksheet figure is an estimate, not an
   enforced registration cap. Create a public app client **without a client
   secret**. Enable authorization code grant, PKCE, and `openid` scope. Add a
   Cognito hosted domain. Register the exact site root as both callback and
   sign-out URL: `https://PUBLIC_IP/`, including the trailing slash. Record
   the pool ID, client ID, region, and full `https://...` Cognito domain.
   Test the callback configuration before inviting users. [Cognito callback
   rules](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-client-apps.html).

## 3. Build on your PC and transfer

From the repository root in PowerShell, with Docker Desktop and frontend
dependencies installed:

```powershell
.\scripts\package_aws_trial.ps1 -OutputDirectory .local/aws-trial-bundle-1
```

The script builds the frontend and API image, then writes an ignored bundle
containing `image-origin-api.tar`, `dist/`, and a manifest with the archive
SHA-256. It fails rather than overwriting an existing bundle. Check that the
manifest's `working_tree_dirty` value is understood; record the exact source
state used for the public trial. The Docker archive is large, so transfer may
take time.

Copy the tar, `dist/`, manifest, and Nginx templates to the EC2 user's home
directory over SSH/SCP. For an Ubuntu AMI, run these on your PC after replacing
the key path and public IP:

```powershell
$key = "C:\path\to\trial-key.pem"
$hostIp = "PUBLIC_IP"
$bundle = ".local\aws-trial-bundle-1"
scp -i $key "$bundle\image-origin-api.tar" "$bundle\manifest.json" "ubuntu@${hostIp}:~/"
scp -i $key -r "$bundle\dist" "ubuntu@${hostIp}:~/"
scp -i $key infra\nginx-bootstrap.conf infra\nginx-https.conf.template "ubuntu@${hostIp}:~/"
```

On the host, verify the tar SHA-256 against `manifest.json`, then install the
provided [`nginx-bootstrap.conf`](../infra/nginx-bootstrap.conf). It serves
only certificate challenges on port 80 and otherwise returns 404. Only
unlink the default site on this fresh, dedicated trial host:

```bash
python3 -c 'import hashlib,json,pathlib; expected=json.loads(pathlib.Path("manifest.json").read_text())["image_tar_sha256"]; f=open("image-origin-api.tar","rb"); actual=hashlib.file_digest(f,"sha256").hexdigest(); f.close(); assert actual == expected, "Image archive checksum mismatch"; print("Image archive checksum OK")'
sudo unlink /etc/nginx/sites-enabled/default
sudo cp ~/nginx-bootstrap.conf /etc/nginx/conf.d/image-origin-studio.conf
sudo nginx -t && sudo systemctl reload nginx
sudo docker load -i ~/image-origin-api.tar
sudo mkdir -p /var/www/image-origin-studio
sudo cp -a ~/dist/. /var/www/image-origin-studio/
```

Use an instance role rather than environment variables holding AWS keys. Run
the API image bound to loopback and set these **non-secret** values from step 1:

```bash
sudo docker run -d --name image-origin-api --restart unless-stopped \
  --cpus=2 --memory=1500m \
  -p 127.0.0.1:8001:8001 \
  -e IOS_HISTORY_BACKEND=aws \
  -e IOS_AWS_REGION=ap-south-1 \
  -e IOS_S3_BUCKET=YOUR_BUCKET_NAME \
  -e IOS_DYNAMODB_TABLE=YOUR_TABLE_NAME \
  -e IOS_COGNITO_REGION=ap-south-1 \
  -e IOS_COGNITO_USER_POOL_ID=YOUR_POOL_ID \
  -e IOS_COGNITO_CLIENT_ID=YOUR_PUBLIC_CLIENT_ID \
  -e IOS_COGNITO_DOMAIN=https://YOUR_COGNITO_DOMAIN \
  image-origin-studio:aws-trial
```

Leave `IOS_LOCAL_TEST_AUTH` unset. Check `sudo docker logs image-origin-api`
and `curl http://127.0.0.1:8001/api/health`. The first model request needs
outbound access to download pinned weights; prewarm it privately before
opening public traffic. A health response alone does not prove model readiness.
If the container cannot get role credentials, recheck IMDSv2 hop limit 2 and
the attached instance role. If the 1.5 GiB container limit fails, stop and
reprice a larger host before opening the public site.

## 4. Enable HTTPS and test login

For an **IP address** with no domain, use Let's Encrypt's short-lived IP
certificate with Certbot **5.4 or newer**. The current tested command shape
uses `--preferred-profile shortlived --webroot --ip-address PUBLIC_IP` with
webroot `/var/www/image-origin-studio`; first use `--staging`, then request a
trusted certificate without it. Certbot does not automatically install IP
certificates into Nginx. [Let's Encrypt's IP guide](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html).
One reproducible install is a root-owned Python venv with pinned Certbot
`5.8.0` under `/opt/ios-certbot`:

```bash
sudo python3 -m venv /opt/ios-certbot
sudo /opt/ios-certbot/bin/pip install certbot==5.8.0
sudo /opt/ios-certbot/bin/certbot certonly --staging --cert-name ios-staging --preferred-profile shortlived \
  --webroot --webroot-path /var/www/image-origin-studio --ip-address PUBLIC_IP
sudo /opt/ios-certbot/bin/certbot certonly --cert-name PUBLIC_IP --preferred-profile shortlived \
  --webroot --webroot-path /var/www/image-origin-studio --ip-address PUBLIC_IP
```

Replace `PUBLIC_IP` before running. The trusted certificate lasts six days.
Delete the temporary staging lineage after the trusted certificate works:
`sudo /opt/ios-certbot/bin/certbot delete --cert-name ios-staging`.
Configure renewal at least every six hours with a deploy hook that
reloads Nginx; for this fresh Ubuntu host, a root cron entry can run
`/opt/ios-certbot/bin/certbot renew --quiet --deploy-hook 'systemctl reload nginx'`.
Run `sudo /opt/ios-certbot/bin/certbot renew --dry-run` and inspect the timer
or cron logs before launch. If you use a domain,
use its normal certificate path and register that domain's exact HTTPS root
with Cognito instead.

Replace `__PUBLIC_HOST__` in
[`nginx-https.conf.template`](../infra/nginx-https.conf.template) with the
Elastic IP or domain, install it as the Nginx site, run `sudo nginx -t`, then
reload Nginx. On the host, one way to make the replacement is
`sed 's/__PUBLIC_HOST__/PUBLIC_IP/g' ~/nginx-https.conf.template | sudo tee /etc/nginx/conf.d/image-origin-studio.conf >/dev/null`, after replacing `PUBLIC_IP`
in the command. It serves the React build, proxies `/api` only to loopback,
limits uploads to 11 MiB at the edge, and rate limits API requests. Confirm
`https://PUBLIC_HOST/` loads with a trusted certificate and that HTTP
redirects to HTTPS. The OAuth code flow requires this exact origin; an IP
callback is a **live compatibility gate** and must be tested end to end. If
Cognito rejects it, use an owner-controlled domain and reprice DNS/TLS before
public launch.

## 5. Public-release checks and daily operation

Before sharing the URL, verify on the actual host:

- Guest analysis works without login and creates no saved record. Both pinned
  models produce the expected output on known local parity images; inspect
  cold start, CPU credit balance, memory, and two concurrent requests.
- Hosted sign-in returns to the site; a signed-in user can choose Save, reopen
  exact original bytes, view C2PA on those original bytes, and delete the item.
- A second account cannot list, fetch, download, or delete the first account's
  items. Check the 10-item/50 MiB owner limits and 500 MiB shared limit.
- Expired/deleting items deny reads immediately; S3 bytes and Dynamo metadata
  disappear after successful cleanup. Test a deliberate failure/retry path.
- Certificate auto-renewal, Nginx config, Docker restart, and Budget email
  alerts work. Review actual pre-credit usage and remaining Free-plan balance
  daily; budget notifications can lag.

Keep the trial to the agreed end date, originally planned as **14 days maximum**.
If spend accelerates toward USD 20 or reaches that ceiling, stop public use and
start teardown. If performance, privacy,
or HTTPS/login checks fail, close ingress and fix them before reopening.

## 6. Teardown on the trial end date

Close public ingress and stop the API first. Delete test users' saved items
through the application, then verify S3 originals and Dynamo rows directly.
Empty/delete the bucket, delete the table, Cognito user pool/domain/client,
Budget, log resources, instance, any leftover EBS disk/snapshot, Elastic IP,
IAM role/policy, security group, and dedicated DNS record. Check other regions
for accidentally created trial resources. Recheck Billing after its reporting
delay and record actual pre-credit and out-of-pocket costs. The full teardown
inventory is in the [trial proposal](archive/AWS_TRIAL_PROPOSAL_2026-10-26.md).
