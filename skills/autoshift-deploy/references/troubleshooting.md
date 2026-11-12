# Troubleshooting a deployment

Match the symptom, confirm the cause with the check, then apply the fix.

| Symptom | Cause | Check | Fix |
|---|---|---|---|
| Argo CD instance phase `Failed`, `initContainers[1].image: Required value`; only dex and redis pods | GitOps bootstrapped before ACM, so the PolicyGenerator image lookup was empty | `oc get argocd -n openshift-gitops -o jsonpath='{.items[0].status}'` | Wait for `deploy/acm-cli-downloads` in `open-cluster-management`, re-run the GitOps `helm upgrade --install` |
| ACM bootstrap release `failed`, no MultiClusterHub | Its Job ran before the MultiClusterHub CRD existed | `oc get csv -n open-cluster-management`; `oc get mch -A` | Once the CSV is `Succeeded`, re-run the ACM `helm upgrade --install` |
| Application Synced, policies exist, nothing installs | Cluster not in a cluster set the values define, so no labels are stamped | `oc get managedcluster local-cluster --show-labels` shows no `autoshift.io/*` | Phase 4: label the cluster set |
| `oc get application <name>` says NotFound | ACM also serves an `applications` kind in another group | | Use `application.argoproj.io` |
| Render error naming the release or policy namespace | Application or release name over 11 characters | | Shorten the name |
| `Git/source mode requires policyGenerator: true` | Values turned the plugin off in git mode | | Leave `config.gitops.policyGenerator` enabled for source installs |
| Operator CSV `UnsupportedOperatorGroup` | OwnNamespace-only operator installed without `targetNamespaces` | `oc get csv -n <ns>` | A policy bug: report it upstream with the operator name |
| Ingress ClusterOperator Degraded, `LoadBalancerPending`, on a cloud hub | `metallb` enabled where a cloud load balancer exists | `oc get metallb -A` | Remove `metallb` from values, `oc delete metallb metallb -n metallb-system`, then touch the `router-default` Service so the cloud controller restores its status |
| Many Applications `Unknown`, sync times out | The repo-server is too small to render every policy in time | `oc adm top pods -n openshift-gitops` | Raise `config.gitops.infra.repo` resource limits in values; patching the Argo CD CR directly is reverted |
| Policy stuck `Pending` | Dependency not yet Compliant, or placed on different clusters | `oc describe policy <name> -n policies-<app>` | Wait for or fix the dependency; a cross-placement dependency never resolves |
| Policy Compliant but the change is not on the cluster | The replicated copy carries old content | Compare `oc get policy <ns>.<name> -n <cluster> -o yaml` with the root | `oc delete policy <policy-ns>.<name> -n <cluster>` to force re-creation |
| `assisted-image-service` CrashLoopBackOff, `no space left on device` | The default OS image catalog outgrew the image storage volume | | Raise `config.acm.provisioning.imageStorageSize` (100Gi or more) or filter `osImages` in config |
| Storage-dependent policies waiting a long time | OpenShift Data Foundation still converging | `oc get storagecluster -A` | Wait; with `hub.yaml` the first convergence can take about an hour. A storage Machine stuck `Provisioned` with no node can be deleted so its MachineSet replaces it |

Useful reads, all read-only:

```bash
oc get policy -n local-cluster | grep -v Compliant
oc get application.argoproj.io -n openshift-gitops | grep -vE 'Synced\s+Healthy'
oc logs -n open-cluster-management deploy/grc-policy-propagator --tail=100
oc get placementdecision -n policies-<app>
```
