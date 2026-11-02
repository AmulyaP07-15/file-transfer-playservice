# CHANGES

## Service code

No service code was changed. I did not edit any of the Go programs
(transfer-server, transfer-frontend, transfer-client), the Dockerfiles, or the
Terraform files that define the stack. I ran every experiment against the
service exactly as it is in the fork, so all of the behavior in the README is
the service's own, not something I introduced.

## What I added

Everything I wrote lives under midterm-mastery/ and is only for testing. It does
not run inside the deployed service.

- scripts, the test file maker, the local start and stop helpers, a small smoke
  test tool, and the chart maker for Experiments 1 and 2.
- exp1-loss, exp2-size, exp3-load, the experiment runners, the Locust load file
  and shape, the chart makers, and the data and charts each run produced.
- aws, helpers to upload the test files to S3 and to smoke test the deployed
  gateway.

## One configuration file

I created terraform/terraform.tfvars with my own S3 bucket name, because the
deploy needs it and the bucket name in the repo belongs to someone else. This is
configuration, not a code change, and the file is gitignored.

## Experiment choices worth noting

These are not changes to the service, but I changed two defaults in my own test
setup while running, and I want to be clear about why.

- Experiment 1 loss levels. I used 0, 1, 2, 3, 5 and 10 percent instead of a
  coarser set, because a first look showed the 1 MB file dies somewhere below 5
  percent. The finer low levels caught the real cliff between 1 and 2 percent.
- Experiment 3 file size. I load tested with the 10 KB file instead of 100 KB.
  On AWS the 100 KB file only succeeds about a third of the time at a single
  request, so a load test with it would just show baseline failure instead of
  the effect of load. The 10 KB file is reliable at a single request, so load
  stayed the real variable.
