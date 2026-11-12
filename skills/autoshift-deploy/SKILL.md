---
name: autoshift-deploy
description: Walk someone through deploying AutoShift onto their own OpenShift hub, step by step, tailored to their environment, which may be connected or disconnected, cloud or bare metal, a single hub or hub of hubs, and installed from source or an OCI release. It works out their environment, builds their values, bootstraps Red Hat Advanced Cluster Management and OpenShift GitOps in the right order, installs AutoShift, assigns clusters and verifies. Use when someone wants to install, set up, bootstrap, try out or demo AutoShift, or asks how to get it running on their cluster, even if they never say "deploy".
license: Apache-2.0
compatibility: Needs oc logged in to the target hub as cluster-admin, helm 3.14 or later, and git for a source install. OpenShift 4.20 or later on the hub.
metadata:
  version: "0.1.0"
---

# Deploy AutoShift, walked through

You are guiding a person, not running a script. Explain each step in a sentence before doing it,
show the exact command, and confirm before anything that changes the cluster. Each phase ends with
a check that proves it worked. If a check fails, stop and diagnose with
[troubleshooting](references/troubleshooting.md) before moving on.

Follow the documented flow. Do not invent a variant of it. If the person's checkout has
`docs/quickstart.md`, it wins where it disagrees with this skill, except for the policy namespace
noted in phase 6.

## Phase 0: learn the environment

Ask these together, offering the recommended answer first. Skip any you can already answer from
the conversation or from the cluster.

1. **Install method.** Source (git, from upstream or their fork), for development and getting
   started; or OCI release, for production and pinned versions.
2. **Purpose.** Smoke test or demo, a real evaluation, or production. This decides the profile and
   whether a development-only Helm install of AutoShift itself is acceptable.
3. **Topology.** One hub, a hub with managed clusters, or a hub of hubs.
4. **Hub platform.** AWS, Azure or GCP, versus bare metal, vSphere, compact or single node.
5. **Network.** Connected, or disconnected with a mirror registry.
6. **Where their values live.** In-repo profiles (fine for a sandbox), a fork, or their own values
   repository (recommended for production).

Then run the preflight read-only checks and report what you found:

```bash
oc whoami && oc whoami --show-server
oc get clusterversion version -o jsonpath='{.status.desired.version}{"\n"}'
oc auth can-i '*' '*' --all-namespaces
oc get infrastructure cluster -o jsonpath='{.status.platformStatus.type}{"\n"}'
oc get nodes -o wide
oc get csv -A 2>/dev/null | grep -Ei 'advanced-cluster-management|gitops'
oc get application.argoproj.io -A 2>/dev/null
helm version --short
```

Confirm the version is 4.20 or later, the user is cluster-admin, and the platform matches what they
said. An existing ACM or GitOps install changes phase 2; an existing AutoShift Application means this
is an upgrade, not an install, so stop and ask.

## Phase 1: choose and prepare values

Pick a profile with [profiles](references/profiles.md) and explain the choice, including what it
provisions. The rules that prevent the most damage:

- Never enable `metallb` on a cloud hub. It clears the cloud load balancer status of the default
  router and degrades ingress.
- `hub.yaml` creates real capacity (infrastructure and storage nodes, OpenShift Data Foundation).
  Check quota first. `hub-minimal.yaml` is a smoke test only: it places a small fraction of the
  policies, so it says little about correctness.
- Every hub clusterset needs `gitops: 'true'`.
- Credentials never go in values. Create the Secrets on the cluster and reference them.
- Choose an Application name of 11 characters or fewer; the policy namespace is
  `policies-<name>`.

For their own values (a fork or values repository), start from the closest profile, keep labels and
config in block YAML, and check every label key against
`autoshift/values/clustersets/_example.yaml`: a misspelled key renders fine and does nothing.
Render before installing:

```bash
helm template autoshift ./autoshift -f <global.yaml> -f <clusterset.yaml> [-f <cluster.yaml>] >/dev/null
```

Disconnected: read [disconnected](references/disconnected.md) now, before bootstrapping.

## Phase 2: bootstrap ACM, then GitOps

Order matters for a source install: the GitOps chart reads its PolicyGenerator image from ACM's
`acm-cli-downloads` Deployment when it renders. Use ACM first for OCI too, so there is one order.

Source:

```bash
helm upgrade --install advanced-cluster-management advanced-cluster-management
oc rollout status deploy/acm-cli-downloads -n open-cluster-management --timeout=15m
helm upgrade --install openshift-gitops openshift-gitops -f policies/stable/openshift-gitops/values.yaml
```

OCI (`VERSION` pins the release):

```bash
helm upgrade --install advanced-cluster-management oci://quay.io/autoshift/bootstrap/advanced-cluster-management \
  --version "$VERSION" --create-namespace --wait --timeout 15m
helm upgrade --install openshift-gitops oci://quay.io/autoshift/bootstrap/openshift-gitops \
  --version "$VERSION" --create-namespace --wait --timeout 10m
```

Check, once each, rather than polling in a loop:

```bash
oc get mch -A                         # Running takes about 10 minutes; Installing is fine to continue
oc get argocd -A                      # the infra instance exists
oc get pods -n openshift-gitops       # repo-server shows 2/2 in source mode (plugin sidecar)
```

Either bootstrap release can fail on a first run because its Job races the operator. Re-running the
same `helm upgrade --install` once the operator's CSV is `Succeeded` is the fix; see troubleshooting.

## Phase 3: install AutoShift

Production installs an Argo CD Application, so AutoShift manages itself through GitOps. Build it
from [applications](references/applications.md) for their method and values location, show it, and
apply it after they confirm.

For a quick demo from a working copy, `helm upgrade --install autoshift ./autoshift -n
openshift-gitops -f ...` is acceptable. Say that it is for development only and that policy
templates still come from git, not from the working copy.

## Phase 4: assign clusters to cluster sets

Nothing is placed until clusters are in a cluster set the values define. This step is easy to miss:

```bash
oc label managedcluster local-cluster cluster.open-cluster-management.io/clusterset=<hub-set> --overwrite
oc label managedcluster <spoke> cluster.open-cluster-management.io/clusterset=<managed-set> --overwrite
```

This is the ACM cluster set label, not an `autoshift.io/*` label; AutoShift labels are never set by
hand. For declarative, GitOps-managed assignment, `config.clusterSet` in a per-cluster values file
does the same through the `cluster-set-assignment` policy.

## Phase 5: verify

```bash
APP=<application-name>
oc get application.argoproj.io "$APP" -n openshift-gitops
oc get application.argoproj.io -n openshift-gitops
oc get managedcluster local-cluster --show-labels | tr ',' '\n' | grep -c autoshift.io
oc get policy -n "policies-$APP"
oc get policy -n local-cluster
```

Success is: the Application Synced, `autoshift.io/*` labels stamped on `local-cluster`, and
replicated policies in `local-cluster` converging toward Compliant. Set expectations: with
`hub.yaml`, storage gates many policies and the first full convergence can take about an hour.
Judge by replicated policies in the cluster namespace, not by root policy counts.

## Phase 6: hand over

Summarize what was installed, the Application name and policy namespace (`policies-<app>`), the
values files in use, and anything still converging. Point to the next steps that fit them: adding
managed clusters, a values repository, OCI upgrades. If `docs/quickstart.md` in their checkout tells
them to check `open-cluster-policies`, tell them the real namespace is `policies-<app>`.

## Conduct

- Confirm before every command that creates, changes or deletes cluster state.
- Never read or print Secret contents. Ask the person to create Secrets themselves and verify only
  that they exist.
- After a wait-producing step, check once and report; do not block in watch loops.
- Never commit or push to their repositories unless asked; show the files and the commands.
